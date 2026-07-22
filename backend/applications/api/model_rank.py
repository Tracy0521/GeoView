import csv
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
from applications.services.remote_models import (
    configured_servers, download_candidate, get_server, public_server, scan_server,
    validated_model_path
)

model_rank_api = Blueprint('model_rank_api', __name__, url_prefix='/api/model-rank')
_lock = threading.Lock()
ALLOWED_MODEL_EXTENSIONS = {'.pt', '.pth', '.pdparams', '.onnx'}
METRIC_KEYS = ('precision', 'recall', 'map50', 'map5095', 'box_loss', 'cls_loss', 'dfl_loss', 'epochs')
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
        if any(item.get('source_type') == 'remote' and
               str(item.get('source_server')) == server['name'] and
               item.get('remote_path') == remote_path for item in project['models']):
            os.remove(path)
            return fail_api('该远程模型已同步到当前项目')
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
    if 'metrics' in request.form:
        try:
            metrics = _clean_metrics(json.loads(request.form.get('metrics') or '{}'), model_name)
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
