import csv
import hashlib
import io
import json
import os
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from flask import Blueprint, current_app, request
from werkzeug.utils import secure_filename

from applications.common.utils.http import fail_api, success_api
from applications.extensions import db
from applications.models.model_rank import ModelProject, ModelRecord
from applications.models.dataset_model import Dataset, DatasetImage, DatasetClass
from applications.services.remote_models import (
    class_metrics_generation_status, configured_servers, download_candidate, get_server,
    launch_class_metrics_generation, public_server, scan_server, validated_model_path
)

model_rank_api = Blueprint('model_rank_api', __name__, url_prefix='/api/model-rank')
_lock = threading.Lock()
_diagnosis_jobs = {}
_diagnosis_jobs_lock = threading.Lock()
ALLOWED_MODEL_EXTENSIONS = {'.pt', '.pth', '.pdparams', '.onnx'}
METRIC_KEYS = ('precision', 'recall', 'map50', 'map5095', 'box_loss', 'cls_loss', 'dfl_loss', 'epochs')
DIAGNOSIS_TYPES = ('tp', 'fn', 'fp', 'class_error', 'localization', 'duplicate',
                   'low_confidence', 'dense_miss', 'small_miss')
CSV_COLUMN_ALIASES = {
    'precision': ('metrics/precision(B)', 'metrics/precision', 'precision'),
    'recall': ('metrics/recall(B)', 'metrics/recall', 'recall'),
    'map50': ('metrics/mAP50(B)', 'metrics/mAP50', 'mAP50', 'map50'),
    'map5095': ('metrics/mAP50-95(B)', 'metrics/mAP50-95', 'mAP50-95', 'map5095'),
    'box_loss': ('train/box_loss', 'box_loss'),
    'cls_loss': ('train/cls_loss', 'cls_loss'),
    'dfl_loss': ('train/dfl_loss', 'dfl_loss')
}


def _root():
    path = os.path.join(current_app.static_folder, 'model_library')
    os.makedirs(path, exist_ok=True)
    return path


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_json(value, fallback):
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _model_detail_from_form(form, current=None):
    current = current or {}
    config = _safe_json(form.get('training_config', current.get('training_config', {})), {})
    if not isinstance(config, dict):
        raise ValueError('训练配置必须是 JSON 对象')
    raw_tags = _safe_json(form.get('tags', current.get('tags', [])), [])
    if isinstance(raw_tags, str):
        raw_tags = [item.strip() for item in raw_tags.split(',')]
    if not isinstance(raw_tags, list):
        raise ValueError('标签必须是数组或逗号分隔文本')
    return {
        'training_config': config,
        'dataset_version': str(form.get('dataset_version', current.get('dataset_version', ''))).strip()[:120],
        'notes': str(form.get('notes', current.get('notes', ''))).strip()[:2000],
        'tags': [str(item).strip()[:40] for item in raw_tags if str(item).strip()][:30],
        'weight_hash': current.get('weight_hash', '')
    }


def _box_iou(left, right):
    try:
        lx1, ly1, lx2, ly2 = map(float, left[:4])
        rx1, ry1, rx2, ry2 = map(float, right[:4])
    except (TypeError, ValueError):
        return 0.0
    intersection = max(0, min(lx2, rx2) - max(lx1, rx1)) * max(0, min(ly2, ry2) - max(ly1, ry1))
    union = max(0, lx2-lx1) * max(0, ly2-ly1) + max(0, rx2-rx1) * max(0, ry2-ry1) - intersection
    return round(intersection / union, 6) if union else 0.0


def _bounded_detection(value, width, height):
    value = dict(value or {})
    box = value.get('bbox', [])
    if len(box) >= 4 and width > 0 and height > 0:
        x1, y1, x2, y2 = map(float, box[:4])
        value['bbox'] = [max(0, min(width, min(x1, x2))), max(0, min(height, min(y1, y2))),
                         max(0, min(width, max(x1, x2))), max(0, min(height, max(y1, y2)))]
    return value


def _same_detection_class(left, right):
    left_id, right_id = left.get('class_id'), right.get('class_id')
    if left_id is not None and right_id is not None:
        return int(left_id) == int(right_id)
    left_name = str(left.get('class', left.get('class_name', ''))).strip()
    right_name = str(right.get('class', right.get('class_name', ''))).strip()
    return left_name == right_name


def _diagnose_image(item, image_url, model_id):
    width, height = float(item.get('width') or 0), float(item.get('height') or 0)
    ground_truth = [_bounded_detection(value, width, height) for value in (item.get('ground_truth', item.get('groundTruth', [])) or [])]
    predictions = [_bounded_detection(value, width, height) for value in (item.get('predictions', []) or [])]
    samples, matched_ground_truth, matched_predictions, matches = [], set(), set(), {}
    pairs = sorted(((gt_index, pred_index, _box_iou(gt.get('bbox', []), pred.get('bbox', [])))
                    for gt_index, gt in enumerate(ground_truth)
                    for pred_index, pred in enumerate(predictions)), key=lambda value: value[2], reverse=True)
    for gt_index, pred_index, iou in pairs:
        if iou < .1:
            break
        if gt_index in matched_ground_truth or pred_index in matched_predictions:
            continue
        matched_ground_truth.add(gt_index)
        matched_predictions.add(pred_index)
        matches[gt_index] = (pred_index, iou)
    for gt_index, gt in enumerate(ground_truth):
        gt_box = gt.get('bbox', [])
        pred_index, iou = matches.get(gt_index, (-1, 0))
        pred = predictions[pred_index] if pred_index >= 0 else None
        area = 0
        if len(gt_box) >= 4 and width and height:
            area = max(0, float(gt_box[2])-float(gt_box[0])) * max(0, float(gt_box[3])-float(gt_box[1])) / (width*height)
        if pred is None or iou < .1:
            kind = 'small_miss' if area and area < .01 else ('dense_miss' if len(ground_truth) >= 15 else 'fn')
        elif iou < .5:
            kind = 'localization'
        elif not _same_detection_class(pred, gt):
            kind = 'class_error'
        elif float(pred.get('confidence', 1) or 0) < .25:
            kind = 'low_confidence'
        else:
            kind = 'tp'
        samples.append({'id': uuid.uuid4().hex[:12], 'model_id': model_id, 'image': image_url, 'width': width, 'height': height,
                        'image_name': item.get('image', ''), 'type': kind, 'class_name': str(gt.get('class', gt.get('class_name', '未知'))),
                        'confidence': pred.get('confidence') if pred else None, 'iou': iou,
                        'ground_truth': gt, 'prediction': pred})
    for index, pred in enumerate(predictions):
        if index in matched_predictions:
            continue
        confidence = float(pred.get('confidence', 0) or 0)
        if confidence < .25:
            continue
        overlaps = [_box_iou(pred.get('bbox', []), gt.get('bbox', [])) for gt in ground_truth]
        duplicate = any(_same_detection_class(pred, predictions[other]) and
                        _box_iou(pred.get('bbox', []), predictions[other].get('bbox', [])) >= .7
                        for other in matched_predictions)
        kind = 'duplicate' if duplicate else 'fp'
        samples.append({'id': uuid.uuid4().hex[:12], 'model_id': model_id, 'image': image_url, 'width': width, 'height': height,
                        'image_name': item.get('image', ''), 'type': kind, 'class_name': str(pred.get('class', pred.get('class_name', '未知'))),
                        'confidence': pred.get('confidence'), 'iou': max(overlaps or [0]), 'ground_truth': None,
                        'prediction': pred})
    return samples


def _set_diagnosis_job(key, **values):
    with _diagnosis_jobs_lock:
        state = _diagnosis_jobs.setdefault(key, {})
        state.update(values)


def _diagnostics_path(project_id, model_id):
    directory = os.path.join(_root(), project_id, 'diagnostics', model_id)
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, 'samples.json')


def _save_diagnostics_file(project_id, model_id, samples, metadata=None):
    path = _diagnostics_path(project_id, model_id)
    temporary = path + '.tmp'
    payload = {'metadata': metadata or {}, 'samples': samples}
    with open(temporary, 'w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False, separators=(',', ':'))
    os.replace(temporary, path)
    return path


def _diagnostics_summary(samples, metadata=None):
    metadata = metadata or {}
    counts = {kind: sum(1 for sample in samples if sample.get('type') == kind) for kind in DIAGNOSIS_TYPES}
    return {**metadata, 'sample_count': len(samples), 'counts': counts,
            'classes': sorted({str(sample.get('class_name')) for sample in samples if sample.get('class_name')}),
            'storage': 'file', 'uploaded_at': datetime.now().isoformat(timespec='seconds')}


def _normalize_diagnostic_sample(sample, class_names=None):
    sample = dict(sample or {})
    ground_truth, prediction = sample.get('ground_truth'), sample.get('prediction')
    class_names = class_names or {}
    reference = prediction or ground_truth or {}
    class_id = reference.get('class_id')
    if class_id is not None and int(class_id) in class_names:
        sample['class_name'] = class_names[int(class_id)]
    elif reference.get('class') or reference.get('class_name'):
        sample['class_name'] = str(reference.get('class', reference.get('class_name')))
    if ground_truth and prediction:
        iou = float(sample.get('iou') or _box_iou(ground_truth.get('bbox', []), prediction.get('bbox', [])))
        confidence = float(prediction.get('confidence', sample.get('confidence', 1)) or 0)
        sample['iou'], sample['confidence'] = iou, confidence
        if iou < .5:
            sample['type'] = 'localization'
        elif not _same_detection_class(ground_truth, prediction):
            sample['type'] = 'class_error'
        elif confidence < .25:
            sample['type'] = 'low_confidence'
        else:
            sample['type'] = 'tp'
    elif prediction and float(prediction.get('confidence', sample.get('confidence', 0)) or 0) < .25:
        sample['_ignored'] = True
    return sample


def _run_diagnosis_job(app, project_id, model_id, dataset_id, sample_limit, key):
    with app.app_context():
        try:
            from ultralytics import YOLO
            model_record = ModelRecord.query.filter_by(id=model_id, project_id=project_id).first()
            dataset = Dataset.query.get(dataset_id)
            if not model_record or not dataset:
                raise ValueError('模型或数据集不存在')
            model_path = os.path.join(_root(), project_id, model_record.stored_filename)
            if not os.path.isfile(model_path) or os.path.splitext(model_path)[1].lower() != '.pt':
                raise ValueError('自动诊断目前仅支持 Ultralytics .pt 模型')
            image_query = DatasetImage.query.filter_by(dataset_id=dataset_id)
            validation_images = image_query.filter_by(split='val').all()
            if not validation_images:
                validation_images = image_query.all()
            if not validation_images:
                raise ValueError('验证数据集没有可用影像')
            source_image_count = len(validation_images)
            if sample_limit and sample_limit < source_image_count:
                if sample_limit == 1:
                    validation_images = [validation_images[source_image_count // 2]]
                else:
                    indexes = [round(index * (source_image_count - 1) / (sample_limit - 1)) for index in range(sample_limit)]
                    validation_images = [validation_images[index] for index in indexes]
            class_names = {row.class_id: row.name for row in DatasetClass.query.filter_by(dataset_id=dataset_id).all()}
            import torch
            use_cuda = torch.cuda.is_available()
            detector = YOLO(model_path)
            samples = []
            processed_count = 0
            _set_diagnosis_job(key, total=len(validation_images), completed=0,
                               message='正在加载模型（GPU）' if use_cuda else '正在加载模型（CPU）')
            for completed, image_record in enumerate(validation_images, 1):
                image_path = os.path.join(current_app.static_folder, 'dataset_library', dataset_id, 'images', image_record.filename)
                if not os.path.isfile(image_path):
                    _set_diagnosis_job(key, completed=completed, message='跳过缺失影像 {}'.format(image_record.filename))
                    continue
                width = image_record.image_info.width if image_record.image_info else 0
                height = image_record.image_info.height if image_record.image_info else 0
                if not width or not height:
                    import cv2
                    shape = cv2.imread(image_path).shape
                    height, width = shape[:2]
                ground_truth = []
                for ann in image_record.annotations:
                    x, y, w, h = float(ann.x), float(ann.y), float(ann.w), float(ann.h)
                    ground_truth.append({'class_id': ann.class_id, 'class': class_names.get(ann.class_id) or ann.category or str(ann.class_id),
                                         'bbox': [(x-w/2)*width, (y-h/2)*height, (x+w/2)*width, (y+h/2)*height]})
                result = detector.predict(source=image_path, conf=.05, iou=.7,
                                          half=use_cuda, device=0 if use_cuda else 'cpu',
                                          verbose=False)[0]
                predictions = []
                if result.boxes is not None:
                    for box, class_id, confidence in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.cls.cpu().tolist(), result.boxes.conf.cpu().tolist()):
                        class_id = int(class_id)
                        predictions.append({'class_id': class_id, 'class': class_names.get(class_id, result.names.get(class_id, str(class_id))),
                                            'confidence': round(float(confidence), 6), 'bbox': [round(float(value), 3) for value in box]})
                item = {'image': image_record.filename, 'width': width, 'height': height,
                        'ground_truth': ground_truth, 'predictions': predictions}
                image_url = '/_uploads/dataset_library/{}/images/{}'.format(dataset_id, image_record.filename)
                samples.extend(_diagnose_image(item, image_url, model_id))
                processed_count += 1
                _set_diagnosis_job(key, completed=completed, message='正在分析 {}'.format(image_record.filename))
            samples = samples[-20000:]
            metadata = {'dataset_id': dataset_id, 'dataset_name': dataset.name,
                        'sample_limit': sample_limit or 0, 'source_image_count': source_image_count,
                        'processed_image_count': processed_count}
            _save_diagnostics_file(project_id, model_id, samples, metadata)
            metrics = dict(model_record.metrics or {})
            metrics['diagnostics'] = _diagnostics_summary(samples, metadata)
            model_record.metrics = metrics
            model_record.project.updated_at = datetime.now()
            db.session.commit()
            counts = {kind: sum(1 for sample in samples if sample.get('type') == kind) for kind in DIAGNOSIS_TYPES}
            _set_diagnosis_job(key, running=False, finished=True, completed=len(validation_images), message='诊断完成', counts=counts)
        except Exception as error:
            current_app.logger.exception('Model diagnosis failed')
            _set_diagnosis_job(key, running=False, finished=False, error=str(error), message='诊断失败')


def _index_path():
    return os.path.join(_root(), 'projects.json')


def _migration_marker_path():
    return os.path.join(_root(), '.projects_json_migrated')


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return datetime.now()


def _write_projects(projects):
    """Persist the legacy dictionary shape into relational project/model tables."""
    try:
        ModelRecord.query.delete()
        ModelProject.query.delete()
        db.session.flush()
        for item in projects:
            project = ModelProject(
                id=item['id'], name=item.get('name', ''), description=item.get('description', ''),
                created_at=_parse_datetime(item.get('created_at')),
                updated_at=_parse_datetime(item.get('updated_at'))
            )
            db.session.add(project)
            db.session.flush()
            for model in item.get('models', []):
                epochs = model.get('training_epochs')
                record = ModelRecord(
                    id=model['id'], project_id=item['id'], name=model.get('name', ''),
                    filename=model.get('filename', ''), stored_filename=model.get('stored_filename', ''),
                    size=int(model.get('size') or 0), framework=model.get('framework', 'PyTorch'),
                    score=str(model.get('score', '')), training_date=model.get('training_date', ''),
                    training_epochs=int(epochs) if str(epochs or '').isdigit() else None,
                    metrics=model.get('metrics') or {},
                    source_type=model.get('source_type', 'local'),
                    source_server=model.get('source_server', ''),
                    remote_path=model.get('remote_path', ''),
                    sync_status=model.get('sync_status', 'synced'),
                    created_at=_parse_datetime(model.get('created_at'))
                )
                db.session.add(record)
                # Large metric JSON documents must be inserted separately. Without an
                # explicit flush SQLAlchemy combines every model into one huge INSERT,
                # which can stall MariaDB and block all API reads during migration.
                db.session.flush()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _migrate_legacy_projects():
    path = _index_path()
    marker = _migration_marker_path()
    if os.path.exists(marker) or not os.path.exists(path):
        return
    if ModelProject.query.count() == 0:
        with open(path, 'r', encoding='utf-8') as file:
            legacy_projects = json.load(file)
        if isinstance(legacy_projects, list) and legacy_projects:
            _write_projects(legacy_projects)
    with open(marker, 'w', encoding='utf-8') as file:
        file.write(datetime.now().isoformat(timespec='seconds'))


def _read_projects():
    _migrate_legacy_projects()
    projects = []
    for project in ModelProject.query.order_by(ModelProject.created_at.asc()).all():
        projects.append({
            'id': project.id, 'name': project.name, 'description': project.description or '',
            'created_at': project.created_at.isoformat(timespec='seconds'),
            'updated_at': project.updated_at.isoformat(timespec='seconds'),
            'models': [{
                'id': model.id, 'name': model.name, 'filename': model.filename,
                'stored_filename': model.stored_filename, 'size': model.size or 0,
                'framework': model.framework or 'PyTorch', 'score': model.score or '',
                'training_date': model.training_date or '',
                'training_epochs': str(model.training_epochs) if model.training_epochs else '',
                'created_at': model.created_at.isoformat(timespec='seconds'),
                'metrics': model.metrics or {}, 'source_type': model.source_type or 'local',
                'source_server': model.source_server or '', 'remote_path': model.remote_path or '',
                'sync_status': model.sync_status or 'synced'
            } for model in project.model_records]
        })
    return projects


def _find_project(projects, project_id):
    return next((item for item in projects if item['id'] == project_id), None)


def _small_sample_rows(raw):
    """Find row- or column-oriented small-sample data in a metrics JSON object."""
    aliases = ('small_sample', 'smallSample', 'small_sample_classes', 'small_sample_changes',
               'small_sample_class_changes', 'class_changes')
    candidate = next((raw[key] for key in aliases if key in raw), None)

    def find_table(value):
        if isinstance(value, list) and any(isinstance(item, dict) for item in value):
            keys = {str(key).strip().lower() for item in value if isinstance(item, dict) for key in item}
            if keys.intersection({'class', 'class_name', 'category'}) and keys.intersection({'baseline', 'base', 'yolo26'}):
                return value
        if isinstance(value, dict):
            normalized = {str(key).strip().lower(): item for key, item in value.items()}
            class_key = next((key for key in ('class', 'class_name', 'category') if isinstance(normalized.get(key), list)), None)
            baseline_key = next((key for key in ('baseline', 'base', 'yolo26') if isinstance(normalized.get(key), list)), None)
            if class_key and baseline_key:
                length = min(len(normalized[class_key]), len(normalized[baseline_key]))
                return [{key: values[index] for key, values in normalized.items() if isinstance(values, list) and index < len(values)} for index in range(length)]
            for nested in value.values():
                found = find_table(nested)
                if found:
                    return found
        return []

    return find_table(candidate) if candidate is not None else find_table(raw)


def _normalized_key(value):
    return ''.join(character.lower() for character in str(value) if character.isalnum())


CLASS_METRIC_FIELDS = {
    'class': ('class', 'classname', 'category', 'categoryname', 'name'),
    'images': ('images', 'imagecount', 'imgs'),
    'instances': ('instances', 'instancecount', 'count', 'targets', 'support', 'samples', 'n'),
    'ap50': ('ap50', 'map50', 'ap050', 'map050'),
    'ap5095': ('ap5095', 'map5095', 'ap050095', 'map050095', 'ap50to95', 'map50to95'),
    'precision': ('precision', 'prec', 'p'),
    'recall': ('recall', 'rec', 'r'),
    'f1': ('f1', 'f1score')
}


def _class_metric_rows(raw):
    """Find row- or column-oriented per-class evaluation metrics."""
    containers = {
        'classmetrics', 'perclass', 'perclassmetrics', 'categorymetrics',
        'classresults', 'percategory', 'percategorymetrics'
    }
    normalized_root = {_normalized_key(key): value for key, value in raw.items()}
    candidate = next((normalized_root[key] for key in containers if key in normalized_root), None)
    class_aliases = set(CLASS_METRIC_FIELDS['class'])
    metric_aliases = set().union(*(set(CLASS_METRIC_FIELDS[key]) for key in ('ap50', 'ap5095', 'precision', 'recall', 'f1')))

    def find_table(value):
        if isinstance(value, list):
            rows = [item for item in value if isinstance(item, dict)]
            keys = {_normalized_key(key) for item in rows for key in item}
            if rows and keys.intersection(class_aliases) and keys.intersection(metric_aliases):
                return rows
        if isinstance(value, dict):
            normalized = {_normalized_key(key): item for key, item in value.items()}
            class_key = next((key for key in class_aliases if isinstance(normalized.get(key), list)), None)
            metric_key = next((key for key in metric_aliases if isinstance(normalized.get(key), list)), None)
            if class_key and metric_key:
                length = len(normalized[class_key])
                return [
                    {key: values[index] for key, values in normalized.items()
                     if isinstance(values, list) and index < len(values)}
                    for index in range(length)
                ]
            for nested in value.values():
                found = find_table(nested)
                if found:
                    return found
        return []

    return find_table(candidate) if candidate is not None else find_table(raw)


def _class_metric_value(normalized, field):
    for alias in CLASS_METRIC_FIELDS[field]:
        if alias in normalized and normalized[alias] not in (None, ''):
            return normalized[alias]
    return None


def _metric_number(value):
    if value in (None, ''):
        return None
    text = str(value).strip()
    percent = text.endswith('%')
    number = float(text[:-1] if percent else text)
    if percent or 1 < number <= 100:
        number /= 100
    if not 0 <= number <= 1:
        return None
    return round(number, 6)


def _clean_class_metrics(raw):
    cleaned = []
    for item in _class_metric_rows(raw)[:500]:
        normalized = {_normalized_key(key): value for key, value in item.items()}
        class_name = str(_class_metric_value(normalized, 'class') or '').strip()[:80]
        if not class_name:
            continue
        try:
            images_value = _class_metric_value(normalized, 'images')
            images = max(0, int(float(images_value))) if images_value not in (None, '') else None
            instances_value = _class_metric_value(normalized, 'instances')
            instances = max(0, int(float(instances_value))) if instances_value not in (None, '') else 0
            values = {
                key: _metric_number(_class_metric_value(normalized, key))
                for key in ('ap50', 'ap5095', 'precision', 'recall', 'f1')
            }
        except (TypeError, ValueError):
            continue
        if values['f1'] is None and values['precision'] is not None and values['recall'] is not None:
            denominator = values['precision'] + values['recall']
            values['f1'] = round(2 * values['precision'] * values['recall'] / denominator, 6) if denominator else 0
        if not any(value is not None for value in values.values()):
            continue
        cleaned.append({'class': class_name, 'images': images, 'instances': instances, **values})
    return cleaned


def _clean_metrics(raw, model_name=''):
    metrics = {}
    if not isinstance(raw, dict):
        return metrics
    raw_class_names = raw.get('class_names', [])
    if isinstance(raw_class_names, dict):
        raw_class_names = [value for _, value in sorted(raw_class_names.items(), key=lambda item: str(item[0]))]
    if isinstance(raw_class_names, list):
        class_names = [str(value).strip()[:80] for value in raw_class_names if str(value).strip()]
        if class_names:
            metrics['class_names'] = class_names[:1000]
    dataset_path = str(raw.get('dataset_path', '')).strip()
    if dataset_path:
        metrics['dataset_path'] = dataset_path[:500]
    for key in METRIC_KEYS:
        values = raw.get(key, [])
        if isinstance(values, list):
            metrics[key] = [round(float(value), 6) for value in values if isinstance(value, (int, float))][:1000]
    small_sample = _small_sample_rows(raw)
    if small_sample:
        cleaned = []
        for item in small_sample[:100]:
            if not isinstance(item, dict):
                continue
            normalized = {str(key).strip().lower(): value for key, value in item.items()}
            try:
                class_name = str(normalized.get('class', normalized.get('class_name', normalized.get('category', '')))).strip()[:60]
                instances = int(normalized.get('instances', normalized.get('instance_count', normalized.get('count', 0))))
                baseline_key = next((key for key in ('baseline', 'base', 'yolo26') if isinstance(normalized.get(key), (int, float))), None)
                baseline = round(float(normalized.get(baseline_key)), 6)
                ignored = {'class', 'class_name', 'category', 'instances', 'instance_count', 'count',
                           'baseline', 'base', 'yolo26', 'change', 'improve', 'trend'}
                candidates = [key for key, value in normalized.items() if key not in ignored and isinstance(value, (int, float))]
                normalized_model_name = ''.join(character for character in model_name.lower() if character.isalnum())
                result_key = next((key for key in candidates if ''.join(character for character in key if character.isalnum()) in normalized_model_name), None)
                if not result_key:
                    result_key = next((key for key in ('strpn', 'result', 'value', 'score') if key in candidates), None)
                if not result_key:
                    result_key = candidates[0] if len(candidates) == 1 else None
                result = round(float(normalized.get(result_key)), 6)
            except (TypeError, ValueError):
                continue
            if class_name and 0 <= instances < 100:
                label = str(normalized.get('result_label', '')).strip() or ('ST-RPN' if result_key == 'strpn' else str(result_key).replace('_', '-').upper())
                baseline_label = str(normalized.get('baseline_label', '')).strip() or ('YOLO26' if baseline_key == 'yolo26' else '基线')
                cleaned.append({'class': class_name, 'instances': instances, 'baseline': baseline,
                                'baseline_label': baseline_label, 'strpn': result, 'result_label': label})
        if cleaned:
            metrics['small_sample'] = cleaned
    class_metrics = _clean_class_metrics(raw)
    if class_metrics:
        metrics['class_metrics'] = class_metrics
    return metrics


def _metrics_from_csv(upload):
    """Parse common Ultralytics results.csv columns into chart metric arrays."""
    content = upload.read()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('gbk')
    reader = csv.DictReader(io.StringIO(text), skipinitialspace=True)
    if not reader.fieldnames:
        raise ValueError('CSV 文件缺少表头')
    normalized_fields = {field.strip(): field for field in reader.fieldnames}
    columns = {}
    for metric, aliases in CSV_COLUMN_ALIASES.items():
        matched = next((normalized_fields[alias] for alias in aliases if alias in normalized_fields), None)
        if matched:
            columns[metric] = matched
    epoch_column = next((normalized_fields[name] for name in ('epoch', 'Epoch', 'epochs') if name in normalized_fields), None)
    if not columns:
        raise ValueError('未识别到 Ultralytics 指标列')
    metrics = {key: [] for key in columns}
    if epoch_column:
        metrics['epochs'] = []
    for row in reader:
        if epoch_column:
            value = str(row.get(epoch_column, '')).strip()
            if value:
                try:
                    metrics['epochs'].append(round(float(value), 6))
                except ValueError:
                    pass
        for metric, column in columns.items():
            value = str(row.get(column, '')).strip()
            if value:
                try:
                    metrics[metric].append(round(float(value), 6))
                except ValueError:
                    pass
    return {key: values[:1000] for key, values in metrics.items() if values}


@model_rank_api.get('/projects')
def project_list():
    projects = _read_projects()
    return success_api(data=sorted(projects, key=lambda item: item['updated_at'], reverse=True))


@model_rank_api.post('/projects')
def project_create():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name or len(name) > 60:
        return fail_api('项目名称不能为空且不能超过60个字符')
    now = datetime.now().isoformat(timespec='seconds')
    project = {
        'id': uuid.uuid4().hex[:12],
        'name': name,
        'description': str(data.get('description', '')).strip()[:300],
        'created_at': now,
        'updated_at': now,
        'models': []
    }
    with _lock:
        projects = _read_projects()
        projects.append(project)
        _write_projects(projects)
    return success_api(msg='项目创建成功', data=project)


@model_rank_api.get('/projects/<string:project_id>')
def project_detail(project_id):
    project = _find_project(_read_projects(), project_id)
    return success_api(data=project) if project else fail_api('项目不存在')


@model_rank_api.delete('/projects/<string:project_id>')
def project_delete(project_id):
    with _lock:
        projects = _read_projects()
        project = _find_project(projects, project_id)
        if not project:
            return fail_api('项目不存在')
        projects.remove(project)
        _write_projects(projects)
    shutil.rmtree(os.path.join(_root(), project_id), ignore_errors=True)
    return success_api(msg='项目删除成功')


@model_rank_api.post('/projects/<string:project_id>/models')
def model_upload(project_id):
    upload = request.files.get('model')
    if not upload or not upload.filename:
        return fail_api('请选择已训练好的模型文件')
    extension = os.path.splitext(upload.filename)[1].lower()
    if extension not in ALLOWED_MODEL_EXTENSIONS:
        return fail_api('仅支持 .pt、.pth、.pdparams 或 .onnx 模型文件')
    model_name = str(request.form.get('name', '')).strip() or os.path.splitext(upload.filename)[0]
    if len(model_name) > 80:
        return fail_api('模型名称不能超过80个字符')
    try:
        metrics = _clean_metrics(json.loads(request.form.get('metrics', '{}')), model_name)
        metrics['model_detail'] = _model_detail_from_form(request.form)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fail_api('指标数据不是有效的 JSON')
    metrics_file = request.files.get('metrics_file')
    if metrics_file and metrics_file.filename:
        if os.path.splitext(metrics_file.filename)[1].lower() != '.csv':
            return fail_api('训练指标文件必须是 results.csv')
        try:
            csv_metrics = _metrics_from_csv(metrics_file)
            for key, values in csv_metrics.items():
                # JSON 与 results.csv 同时提供同一指标时，保留更完整的序列，
                # 避免较短的汇总 CSV 覆盖 JSON 中完整的训练轮次。
                if len(values) >= len(metrics.get(key, [])):
                    metrics[key] = values
        except (ValueError, UnicodeError) as error:
            return fail_api('无法解析 results.csv：{}'.format(str(error)))
    model_id = uuid.uuid4().hex[:12]
    directory = os.path.join(_root(), project_id)
    os.makedirs(directory, exist_ok=True)
    filename = '{}_{}{}'.format(model_id, secure_filename(model_name) or 'model', extension)
    path = os.path.join(directory, filename)
    upload.save(path)
    metrics['model_detail']['weight_hash'] = _sha256(path)
    now = datetime.now().isoformat(timespec='seconds')
    model = {
        'id': model_id,
        'name': model_name,
        'filename': upload.filename,
        'stored_filename': filename,
        'size': os.path.getsize(path),
        'framework': request.form.get('framework', 'PyTorch'),
        'score': request.form.get('score', ''),
        'source_type': 'local',
        'source_server': '',
        'remote_path': '',
        'sync_status': 'synced',
        'created_at': now,
        'metrics': metrics
    }
    with _lock:
        projects = _read_projects()
        project = _find_project(projects, project_id)
        if not project:
            os.remove(path)
            return fail_api('项目不存在')
        project['models'].append(model)
        project['updated_at'] = now
        _write_projects(projects)
    return success_api(msg='模型添加成功', data=model)


@model_rank_api.get('/projects/<string:project_id>/remote-models')
def remote_model_list(project_id):
    project = _find_project(_read_projects(), project_id)
    if not project:
        return fail_api('项目不存在')
    synced = {
        (str(model.get('source_server', '')), model.get('remote_path', ''))
        for model in project['models'] if model.get('source_type') == 'remote'
    }
    configured = configured_servers()

    def inspect_server(server):
        server_data = public_server(server)
        try:
            candidates = scan_server(server)
            server_data.update({'status': 'online', 'message': '', 'model_count': len(candidates)})
            return server, server_data, candidates, ''
        except Exception as error:
            server_data.update({'status': 'offline', 'message': '连接失败或实例未启动', 'model_count': 0})
            return server, server_data, [], str(error)

    servers = []
    models = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(configured)))) as executor:
        scanned = list(executor.map(inspect_server, configured))
    for server, server_data, candidates, error in scanned:
        if error:
            current_app.logger.warning('Remote model scan failed for %s: %s', server['name'], error)
        for candidate in candidates:
            candidate['sync_status'] = 'synced' if (server['name'], candidate['remote_path']) in synced else 'remote'
            models.append(candidate)
        servers.append(server_data)
    return success_api(data={'servers': servers, 'models': models})


@model_rank_api.post('/projects/<string:project_id>/remote-models/import')
def remote_model_import(project_id):
    data = request.get_json(silent=True) or {}
    server = get_server(data.get('server_id'))
    if not server:
        return fail_api('远程服务器不存在或未配置')
    remote_path = validated_model_path(server, data.get('remote_path'))
    if not remote_path:
        return fail_api('仅允许同步 output/*/weights/best.pt')
    projects = _read_projects()
    project = _find_project(projects, project_id)
    if not project:
        return fail_api('项目不存在')
    if any(model.get('source_type') == 'remote' and
           str(model.get('source_server')) == server['name'] and
           model.get('remote_path') == remote_path for model in project['models']):
        return fail_api('该远程模型已同步到当前项目')

    default_name = os.path.basename(os.path.dirname(os.path.dirname(remote_path)))
    model_name = str(data.get('name', '')).strip() or default_name
    if len(model_name) > 80:
        return fail_api('模型名称不能超过80个字符')
    model_id = uuid.uuid4().hex[:12]
    directory = os.path.join(_root(), project_id)
    os.makedirs(directory, exist_ok=True)
    filename = '{}_{}.pt'.format(model_id, secure_filename(model_name) or 'model')
    path = os.path.join(directory, filename)
    temporary_path = path + '.part'
    try:
        downloaded = download_candidate(server, remote_path, temporary_path)
        os.replace(temporary_path, path)
        metrics = {}
        if downloaded['results']:
            metrics = _metrics_from_csv(io.BytesIO(downloaded['results']))
        if downloaded.get('class_names'):
            metrics['class_names'] = downloaded['class_names']
        if downloaded.get('dataset_path'):
            metrics['dataset_path'] = downloaded['dataset_path']
        if downloaded.get('class_metrics'):
            metrics['class_metrics'] = downloaded['class_metrics']
    except (ValueError, UnicodeError) as error:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        if os.path.exists(path):
            os.remove(path)
        return fail_api('远程模型同步失败：{}'.format(str(error)))
    except Exception as error:
        current_app.logger.warning('Remote model download failed from %s: %s', server['name'], error)
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        if os.path.exists(path):
            os.remove(path)
        return fail_api('远程模型同步失败，请确认实例在线且文件可读')

    now = datetime.now().isoformat(timespec='seconds')
    model = {
        'id': model_id, 'name': model_name, 'filename': 'best.pt',
        'stored_filename': filename, 'size': os.path.getsize(path),
        'framework': str(data.get('framework', 'PyTorch')).strip()[:40] or 'PyTorch',
        'score': str(data.get('score', '')).strip()[:30], 'created_at': now,
        'metrics': metrics, 'source_type': 'remote', 'source_server': server['name'],
        'remote_path': remote_path, 'sync_status': 'synced'
    }
    model['metrics']['model_detail'] = {
        'training_config': {}, 'dataset_version': str(data.get('dataset_version', ''))[:120],
        'notes': '', 'tags': [], 'weight_hash': _sha256(path)
    }
    with _lock:
        projects = _read_projects()
        project = _find_project(projects, project_id)
        if not project:
            os.remove(path)
            return fail_api('项目不存在')
        project['models'].append(model)
        project['updated_at'] = now
        _write_projects(projects)
    return success_api(msg='远程模型同步成功', data=model)


@model_rank_api.post('/projects/<string:project_id>/remote-models/class-metrics')
def remote_class_metrics_generate(project_id):
    if not _find_project(_read_projects(), project_id):
        return fail_api('项目不存在')
    data = request.get_json(silent=True) or {}
    server = get_server(data.get('server_id'))
    if not server:
        return fail_api('远程服务器不存在或未配置')
    try:
        result = launch_class_metrics_generation(server, str(data.get('dataset_path', '')).strip())
        return success_api(msg='逐类别验证任务已启动', data=result)
    except ValueError as error:
        return fail_api(str(error))
    except Exception as error:
        current_app.logger.warning('Remote class validation launch failed for %s: %s', server['name'], error)
        return fail_api('无法启动远程验证，请确认实例在线且训练环境可用')


@model_rank_api.get('/projects/<string:project_id>/remote-models/class-metrics/status')
def remote_class_metrics_status(project_id):
    if not _find_project(_read_projects(), project_id):
        return fail_api('项目不存在')
    server = get_server(request.args.get('server_id'))
    if not server:
        return fail_api('远程服务器不存在或未配置')
    try:
        return success_api(data=class_metrics_generation_status(server))
    except Exception as error:
        current_app.logger.warning('Remote class validation status failed for %s: %s', server['name'], error)
        return fail_api('无法读取远程验证状态')


@model_rank_api.patch('/projects/<string:project_id>/models/<string:model_id>')
def model_update(project_id, model_id):
    projects = _read_projects()
    project = _find_project(projects, project_id)
    if not project:
        return fail_api('项目不存在')
    model = next((item for item in project['models'] if item['id'] == model_id), None)
    if not model:
        return fail_api('模型不存在')

    model_name = str(request.form.get('name', model['name'])).strip()
    if not model_name or len(model_name) > 80:
        return fail_api('模型名称不能为空且不能超过80个字符')
    training_date = str(request.form.get('training_date', model.get('training_date', ''))).strip()[:20]
    training_epochs = str(request.form.get('training_epochs', model.get('training_epochs', ''))).strip()
    if training_epochs:
        try:
            epoch_number = int(training_epochs)
            if epoch_number <= 0 or epoch_number > 100000:
                raise ValueError
            training_epochs = str(epoch_number)
        except ValueError:
            return fail_api('训练轮数必须是大于0的整数')
    metrics = model.get('metrics', {})
    existing_detail = metrics.get('model_detail', {}) if isinstance(metrics, dict) else {}
    if 'metrics' in request.form:
        try:
            incoming = json.loads(request.form.get('metrics') or '{}')
            metrics = _clean_metrics(incoming, model_name)
            if isinstance(incoming, dict):
                for key in ('diagnostics',):
                    if key in incoming:
                        metrics[key] = incoming[key]
        except (TypeError, ValueError, json.JSONDecodeError):
            return fail_api('指标数据不是有效的 JSON')
    metrics_file = request.files.get('metrics_file')
    if metrics_file and metrics_file.filename:
        if os.path.splitext(metrics_file.filename)[1].lower() != '.csv':
            return fail_api('训练指标文件必须是 results.csv')
        try:
            csv_metrics = _metrics_from_csv(metrics_file)
            for key, values in csv_metrics.items():
                if len(values) >= len(metrics.get(key, [])):
                    metrics[key] = values
        except (ValueError, UnicodeError) as error:
            return fail_api('无法解析 results.csv：{}'.format(str(error)))
    try:
        metrics['model_detail'] = _model_detail_from_form(request.form, existing_detail)
    except ValueError as error:
        return fail_api(str(error))
    if not metrics['model_detail'].get('weight_hash'):
        weight_path = os.path.join(_root(), project_id, model.get('stored_filename', ''))
        if os.path.isfile(weight_path):
            metrics['model_detail']['weight_hash'] = _sha256(weight_path)

    with _lock:
        projects = _read_projects()
        project = _find_project(projects, project_id)
        model = next((item for item in project['models'] if item['id'] == model_id), None) if project else None
        if not model:
            return fail_api('模型不存在')
        model['name'] = model_name
        model['framework'] = str(request.form.get('framework', model.get('framework', 'PyTorch'))).strip()[:40]
        model['score'] = str(request.form.get('score', model.get('score', ''))).strip()[:30]
        model['training_date'] = training_date
        model['training_epochs'] = training_epochs
        model['metrics'] = metrics
        project['updated_at'] = datetime.now().isoformat(timespec='seconds')
        _write_projects(projects)
    return success_api(msg='模型修改成功', data=model)


@model_rank_api.post('/projects/<string:project_id>/models/<string:model_id>/diagnostics')
def model_diagnostics_upload(project_id, model_id):
    upload = request.files.get('diagnostics')
    if not upload or not upload.filename:
        return fail_api('请选择诊断 JSON 文件')
    try:
        payload = json.loads(upload.read().decode('utf-8-sig'))
    except (UnicodeError, json.JSONDecodeError):
        return fail_api('诊断文件不是有效的 UTF-8 JSON')
    items = payload.get('images', payload.get('samples', [])) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return fail_api('诊断 JSON 需要包含 images 或 samples 数组')

    image_directory = os.path.join(_root(), project_id, 'diagnostics', model_id)
    os.makedirs(image_directory, exist_ok=True)
    image_urls = {}
    for image in request.files.getlist('images')[:1000]:
        extension = os.path.splitext(image.filename)[1].lower()
        if extension not in ('.jpg', '.jpeg', '.png', '.webp'):
            continue
        stored = '{}{}'.format(uuid.uuid4().hex, extension)
        image.save(os.path.join(image_directory, stored))
        image_urls[os.path.basename(image.filename)] = '/static/model_library/{}/diagnostics/{}/{}'.format(project_id, model_id, stored)

    samples = []
    for item in items[:10000]:
        if not isinstance(item, dict):
            continue
        image_name = os.path.basename(str(item.get('image', item.get('image_name', ''))))
        image_url = image_urls.get(image_name, str(item.get('image_url', '')))
        if item.get('type') in DIAGNOSIS_TYPES:
            sample = dict(item)
            sample.update({'id': str(item.get('id') or uuid.uuid4().hex[:12]), 'model_id': model_id,
                           'image': image_url, 'image_name': image_name})
            samples.append(sample)
        else:
            samples.extend(_diagnose_image(item, image_url, model_id))
    if not samples:
        return fail_api('没有识别到可诊断的真实框、预测框或已分类样本')

    with _lock:
        projects = _read_projects()
        project = _find_project(projects, project_id)
        model = next((item for item in project['models'] if item['id'] == model_id), None) if project else None
        if not model:
            return fail_api('模型不存在')
        metrics = model.get('metrics') or {}
        samples = samples[-20000:]
        _save_diagnostics_file(project_id, model_id, samples)
        metrics['diagnostics'] = _diagnostics_summary(samples)
        model['metrics'] = metrics
        project['updated_at'] = datetime.now().isoformat(timespec='seconds')
        _write_projects(projects)
    counts = metrics['diagnostics']['counts']
    return success_api(msg='错误样本诊断数据已导入', data={'imported': len(samples), 'counts': counts})


@model_rank_api.post('/projects/<string:project_id>/models/<string:model_id>/diagnostics/generate')
def model_diagnostics_generate(project_id, model_id):
    data = request.get_json(silent=True) or {}
    dataset_id = str(data.get('dataset_id', '')).strip()
    try:
        sample_limit = int(data.get('sample_limit') or 0)
    except (TypeError, ValueError):
        return fail_api('验证图片数量必须是整数')
    if sample_limit < 0 or sample_limit > 10000:
        return fail_api('验证图片数量必须在 1 到 10000 之间，0 表示全部')
    if not dataset_id:
        return fail_api('请选择验证数据集')
    model = ModelRecord.query.filter_by(id=model_id, project_id=project_id).first()
    dataset = Dataset.query.get(dataset_id)
    if not model:
        return fail_api('模型不存在')
    if not dataset:
        return fail_api('验证数据集不存在')
    if os.path.splitext(model.stored_filename or '')[1].lower() != '.pt':
        return fail_api('自动诊断目前仅支持 Ultralytics .pt 模型')
    key = '{}:{}:{}'.format(project_id, model_id, dataset_id)
    with _diagnosis_jobs_lock:
        if _diagnosis_jobs.get(key, {}).get('running'):
            return fail_api('该模型正在生成诊断数据')
        _diagnosis_jobs[key] = {'running': True, 'finished': False, 'total': 0, 'completed': 0,
                                'message': '任务已启动', 'error': '', 'dataset_id': dataset_id}
    app = current_app._get_current_object()
    threading.Thread(target=_run_diagnosis_job,
                     args=(app, project_id, model_id, dataset_id, sample_limit, key), daemon=True).start()
    return success_api(msg='诊断任务已启动', data=_diagnosis_jobs[key])


@model_rank_api.get('/projects/<string:project_id>/models/<string:model_id>/diagnostics')
def model_diagnostics_data(project_id, model_id):
    if not ModelRecord.query.filter_by(id=model_id, project_id=project_id).first():
        return fail_api('模型不存在')
    path = _diagnostics_path(project_id, model_id)
    if not os.path.isfile(path):
        return success_api(data={'samples': [], 'total': 0, 'counts': {}, 'classes': [], 'metadata': {}})
    try:
        with open(path, 'r', encoding='utf-8') as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return fail_api('诊断明细文件损坏或不可读取')
    raw_samples = payload.get('samples', []) if isinstance(payload, dict) else []
    metadata = payload.get('metadata', {}) if isinstance(payload, dict) else {}
    dataset_id = str(metadata.get('dataset_id', ''))
    class_names = {row.class_id: row.name for row in DatasetClass.query.filter_by(dataset_id=dataset_id).all()} if dataset_id else {}
    all_samples = [sample for sample in (_normalize_diagnostic_sample(item, class_names) for item in raw_samples)
                   if not sample.get('_ignored')]
    samples = all_samples
    model_filter = str(request.args.get('type', '')).strip()
    class_filter = str(request.args.get('class_name', '')).strip()
    if model_filter and model_filter != 'all':
        samples = [sample for sample in samples if sample.get('type') == model_filter]
    if class_filter:
        samples = [sample for sample in samples if str(sample.get('class_name', '')) == class_filter]
    grouped = {}
    for sample in samples:
        key = str(sample.get('image') or sample.get('image_name') or sample.get('id'))
        if key not in grouped:
            grouped[key] = {
                'id': 'image-{}'.format(len(grouped) + 1), 'model_id': sample.get('model_id'),
                'image': sample.get('image', ''), 'image_name': sample.get('image_name', ''),
                'width': sample.get('width'), 'height': sample.get('height'), 'errors': []
            }
        grouped[key]['errors'].append({
            'id': sample.get('id'), 'type': sample.get('type'), 'class_name': sample.get('class_name'),
            'confidence': sample.get('confidence'), 'iou': sample.get('iou'),
            'ground_truth': sample.get('ground_truth'), 'prediction': sample.get('prediction')
        })
    grouped_samples = list(grouped.values())
    for item in grouped_samples:
        errors = item['errors']
        first = errors[0] if errors else {}
        item.update({'type': first.get('type'), 'class_name': first.get('class_name'),
                     'confidence': first.get('confidence'), 'iou': first.get('iou'),
                     'ground_truth': first.get('ground_truth'), 'prediction': first.get('prediction'),
                     'error_count': len(errors),
                     'error_types': list(dict.fromkeys(error.get('type') for error in errors if error.get('type')))})
    total = len(grouped_samples)
    page = max(1, request.args.get('page', 1, type=int))
    limit = min(200, max(1, request.args.get('limit', 60, type=int)))
    start = (page - 1) * limit
    return success_api(data={
        'samples': grouped_samples[start:start + limit], 'total': total, 'error_total': len(samples), 'page': page, 'limit': limit,
        'image_count': int(metadata.get('processed_image_count') or
                           len({str(sample.get('image') or sample.get('image_name')) for sample in all_samples})),
        'counts': {kind: sum(1 for sample in all_samples if sample.get('type') == kind) for kind in DIAGNOSIS_TYPES},
        'classes': sorted({str(sample.get('class_name')) for sample in all_samples if sample.get('class_name')}),
        'metadata': metadata
    })


@model_rank_api.get('/projects/<string:project_id>/models/<string:model_id>/diagnostics/status')
def model_diagnostics_status(project_id, model_id):
    dataset_id = str(request.args.get('dataset_id', '')).strip()
    key = '{}:{}:{}'.format(project_id, model_id, dataset_id)
    with _diagnosis_jobs_lock:
        state = dict(_diagnosis_jobs.get(key, {'running': False, 'finished': False, 'total': 0,
                                               'completed': 0, 'message': '尚未启动', 'error': ''}))
    return success_api(data=state)


@model_rank_api.delete('/projects/<string:project_id>/models/<string:model_id>')
def model_delete(project_id, model_id):
    with _lock:
        projects = _read_projects()
        project = _find_project(projects, project_id)
        if not project:
            return fail_api('项目不存在')
        model = next((item for item in project['models'] if item['id'] == model_id), None)
        if not model:
            return fail_api('模型不存在')
        project['models'].remove(model)
        project['updated_at'] = datetime.now().isoformat(timespec='seconds')
        _write_projects(projects)
    path = os.path.join(_root(), project_id, model['stored_filename'])
    if os.path.exists(path):
        os.remove(path)
    return success_api(msg='模型删除成功')
