import csv
import io
import json
import os
import shutil
import threading
import uuid
from datetime import datetime

from flask import Blueprint, current_app, request
from werkzeug.utils import secure_filename

from applications.common.utils.http import fail_api, success_api

model_rank_api = Blueprint('model_rank_api', __name__, url_prefix='/api/model-rank')
_lock = threading.Lock()
ALLOWED_MODEL_EXTENSIONS = {'.pt', '.pth', '.pdparams', '.onnx'}
METRIC_KEYS = ('precision', 'recall', 'map50', 'map5095', 'box_loss', 'cls_loss', 'dfl_loss')
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


def _read_projects():
    path = _index_path()
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as file:
        return json.load(file)


def _write_projects(projects):
    path = _index_path()
    temporary = path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as file:
        json.dump(projects, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def _find_project(projects, project_id):
    return next((item for item in projects if item['id'] == project_id), None)


def _clean_metrics(raw):
    metrics = {}
    if not isinstance(raw, dict):
        return metrics
    for key in METRIC_KEYS:
        values = raw.get(key, [])
        if isinstance(values, list):
            metrics[key] = [round(float(value), 6) for value in values if isinstance(value, (int, float))][:1000]
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
    if not columns:
        raise ValueError('未识别到 Ultralytics 指标列')
    metrics = {key: [] for key in columns}
    for row in reader:
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
        metrics = _clean_metrics(json.loads(request.form.get('metrics', '{}')))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fail_api('指标数据不是有效的 JSON')
    metrics_file = request.files.get('metrics_file')
    if metrics_file and metrics_file.filename:
        if os.path.splitext(metrics_file.filename)[1].lower() != '.csv':
            return fail_api('训练指标文件必须是 results.csv')
        try:
            metrics.update(_metrics_from_csv(metrics_file))
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
