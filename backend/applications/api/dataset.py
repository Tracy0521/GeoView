"""
数据集管理 API — 遥感影像上传、YOLO 标注解析、存储与导出。
与模型排行模块完全解耦，仅处理数据集相关业务。
"""
import io
import json
import os
import random
import shutil
import threading
import uuid
import zipfile
from datetime import datetime

from flask import Blueprint, current_app, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from applications.common.path_global import (
    fun_type_2, fun_type_3, fun_type_4, fun_type_5, generate_dir, up_dir
)
from applications.common.utils.http import fail_api, success_api

dataset_api = Blueprint('dataset_api', __name__, url_prefix='/api/dataset')
# 数据集影像静态资源服务（与 photos 上传集独立）
dataset_static = Blueprint(
    'dataset_static', __name__, url_prefix='/_uploads/dataset_library')
_lock = threading.Lock()

# ── 赛题 25 类 YOLO 遥感数据集常量 ──────────────────────────────
NUM_CLASSES = 25
SHIP_CLASS_IDS = set(range(0, 4))       # 0-3 舰船
AIRPLANE_CLASS_IDS = set(range(4, 24))  # 4-23 飞机
LAUNCHER_CLASS_ID = 24                  # 24 发射车
VALID_CLASS_IDS = set(range(NUM_CLASSES))

IMAGE_EXTENSIONS = {'.tif', '.tiff', '.png', '.jpg', '.jpeg'}
LABEL_EXTENSION = '.txt'
MAX_IMAGE_SIZE = 100 * 1024 * 1024          # 单图 100MB
MAX_ZIP_SIZE = 10 * 1024 * 1024 * 1024      # 压缩包 10GB


def _root():
    path = os.path.join(current_app.static_folder, 'dataset_library')
    os.makedirs(path, exist_ok=True)
    return path


def _index_path():
    return os.path.join(_root(), 'datasets.json')


def _read_index():
    path = _index_path()
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as file:
        return json.load(file)


def _write_index(datasets):
    path = _index_path()
    temporary = path + '.tmp'
    with open(temporary, 'w', encoding='utf-8') as file:
        json.dump(datasets, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def _dataset_dir(dataset_id):
    return os.path.join(_root(), dataset_id)


def _images_dir(dataset_id):
    path = os.path.join(_dataset_dir(dataset_id), 'images')
    os.makedirs(path, exist_ok=True)
    return path


def _labels_dir(dataset_id):
    path = os.path.join(_dataset_dir(dataset_id), 'labels')
    os.makedirs(path, exist_ok=True)
    return path


def _find_dataset(datasets, dataset_id):
    return next((item for item in datasets if item['id'] == dataset_id), None)


def _category_group(class_id):
    """返回三大类分组：ship / airplane / launcher"""
    if class_id in SHIP_CLASS_IDS:
        return 'ship'
    if class_id in AIRPLANE_CLASS_IDS:
        return 'airplane'
    if class_id == LAUNCHER_CLASS_ID:
        return 'launcher'
    return 'unknown'


def _parse_yolo_label(content):
    """
    解析 YOLO 归一化水平框标注。
    返回 (annotations, warnings) 元组。
    """
    annotations = []
    warnings = []
    lines = content.strip().splitlines() if content.strip() else []

    if not lines:
        warnings.append('标注文件为空')
        return annotations, warnings

    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 5:
            warnings.append(f'第 {line_num} 行格式错误：需要 class x y w h')
            continue
        try:
            class_id = int(parts[0])
        except ValueError:
            warnings.append(f'第 {line_num} 行类别 ID 非法')
            continue
        if class_id not in VALID_CLASS_IDS:
            warnings.append(f'第 {line_num} 行类别 ID {class_id} 超出范围 0-24')
            continue
        try:
            x, y, w, h = (float(parts[1]), float(parts[2]),
                          float(parts[3]), float(parts[4]))
        except ValueError:
            warnings.append(f'第 {line_num} 行坐标值非法')
            continue
        for name, value in zip(('x', 'y', 'w', 'h'), (x, y, w, h)):
            if value < 0 or value > 1:
                warnings.append(f'第 {line_num} 行坐标 {name}={value} 越界 (0~1)')
                break
        else:
            annotations.append({
                'class_id': class_id,
                'category': _category_group(class_id),
                'x': x, 'y': y, 'w': w, 'h': h
            })
    return annotations, warnings


def _read_text_file(path):
    """读取文本文件，兼容 UTF-8 / GBK 编码。"""
    with open(path, 'rb') as file:
        content = file.read()
    for encoding in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode('utf-8', errors='replace')


def _read_label_file(label_path):
    if not os.path.exists(label_path):
        return [], ['缺少同名 txt 标注文件']
    return _parse_yolo_label(_read_text_file(label_path))


def _unique_filename(directory, basename):
    """避免文件名冲突，必要时追加后缀。"""
    name, ext = os.path.splitext(basename)
    candidate = basename
    counter = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f'{name}_{counter}{ext}'
        counter += 1
    return candidate


def _image_url(dataset_id, filename):
    return f'/_uploads/dataset_library/{dataset_id}/images/{filename}'


def _label_url(dataset_id, filename):
    return f'/_uploads/dataset_library/{dataset_id}/labels/{filename}'


def _compute_dataset_stats(dataset):
    """根据 images 列表重新汇总统计字段。"""
    images = dataset.get('images', [])
    class_ids = set()
    box_count = 0
    for img in images:
        for ann in img.get('annotations', []):
            box_count += 1
            class_ids.add(ann['class_id'])
    dataset['image_count'] = len(images)
    dataset['box_count'] = box_count
    dataset['class_count'] = len(class_ids)
    return dataset


def _global_stats(datasets):
    """全局四项统计。"""
    total_images = sum(d.get('image_count', 0) for d in datasets)
    total_boxes = sum(d.get('box_count', 0) for d in datasets)
    all_classes = set()
    for d in datasets:
        for img in d.get('images', []):
            for ann in img.get('annotations', []):
                all_classes.add(ann['class_id'])
    return {
        'dataset_count': len(datasets),
        'image_count': total_images,
        'box_count': total_boxes,
        'class_count': len(all_classes)
    }


def _add_image_to_dataset(dataset, image_filename, annotations, warnings):
    """向数据集追加一条影像记录。"""
    stem = os.path.splitext(image_filename)[0]
    label_filename = stem + LABEL_EXTENSION
    images = dataset.setdefault('images', [])
    # 若同名已存在则更新
    existing = next((i for i in images if i['filename'] == image_filename), None)
    entry = {
        'id': existing['id'] if existing else uuid.uuid4().hex[:10],
        'filename': image_filename,
        'label_filename': label_filename,
        'url': _image_url(dataset['id'], image_filename),
        'annotations': annotations,
        'box_count': len(annotations),
        'split': existing.get('split', 'unset') if existing else 'unset',
        'warnings': warnings
    }
    if existing:
        idx = images.index(existing)
        images[idx] = entry
    else:
        images.append(entry)
    _compute_dataset_stats(dataset)
    return entry


def _process_image_file(dataset, file_storage, warnings_log):
    """保存单张影像并匹配同名标注。"""
    original = secure_filename(file_storage.filename) or 'image.jpg'
    ext = os.path.splitext(original)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        warnings_log.append(f'跳过不支持的文件: {original}')
        return None

    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_IMAGE_SIZE:
        warnings_log.append(f'{original} 超过单图 100MB 限制')
        return None

    img_dir = _images_dir(dataset['id'])
    lbl_dir = _labels_dir(dataset['id'])
    filename = _unique_filename(img_dir, original)
    file_storage.save(os.path.join(img_dir, filename))

    stem = os.path.splitext(filename)[0]
    label_path = os.path.join(lbl_dir, stem + LABEL_EXTENSION)
    annotations, label_warnings = _read_label_file(label_path)
    warnings_log.extend(label_warnings)
    return _add_image_to_dataset(dataset, filename, annotations, label_warnings)


def _process_label_file(dataset, file_storage, warnings_log):
    """保存独立 txt 标注文件（需已有同名图片）。"""
    original = secure_filename(file_storage.filename) or 'label.txt'
    if not original.lower().endswith(LABEL_EXTENSION):
        return None

    lbl_dir = _labels_dir(dataset['id'])
    img_dir = _images_dir(dataset['id'])
    filename = _unique_filename(lbl_dir, original)
    file_storage.save(os.path.join(lbl_dir, filename))

    stem = os.path.splitext(filename)[0]
    # 查找已有同名图片并更新标注
    matched_image = None
    for ext in IMAGE_EXTENSIONS:
        candidate = stem + ext
        if os.path.exists(os.path.join(img_dir, candidate)):
            matched_image = candidate
            break

    if not matched_image:
        warnings_log.append(f'标注 {filename} 暂无匹配影像，已保存待匹配')
        return None

    annotations, label_warnings = _read_label_file(
        os.path.join(lbl_dir, filename))
    warnings_log.extend(label_warnings)
    return _add_image_to_dataset(dataset, matched_image, annotations, label_warnings)


def _open_zip_robust(zip_path):
    """
    打开 ZIP 文件；若中央目录 UTF-8 标志与实际 GBK 编码冲突则自动降级处理。
    """
    try:
        zf = zipfile.ZipFile(zip_path, 'r')
        zf.infolist()
        return zf
    except UnicodeDecodeError:
        with open(zip_path, 'rb') as file:
            data = bytearray(file.read())
        pos = 0
        while True:
            pos = data.find(b'PK\x01\x02', pos)
            if pos < 0:
                break
            flag_pos = pos + 8
            flags = data[flag_pos] | (data[flag_pos + 1] << 8)
            flags &= ~0x800
            data[flag_pos] = flags & 0xFF
            data[flag_pos + 1] = (flags >> 8) & 0xFF
            pos += 4
        zf = zipfile.ZipFile(io.BytesIO(bytes(data)), 'r')
        zf.infolist()
        return zf


def _decode_zip_member_name(member):
    """
    修正 ZIP 内文件名编码。
    Windows 压缩包常用 GBK，而 Python zipfile 默认按 cp437/UTF-8 解码会失败或乱码。
    """
    name = member.filename
    if member.flag_bits & 0x800:
        return name.replace('\\', '/')
    for encoding in ('gbk', 'utf-8', 'cp437'):
        try:
            return name.encode('cp437').decode(encoding).replace('\\', '/')
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
    return name.replace('\\', '/')


def _extract_zip_archive(zip_path, dest_dir):
    """解压 ZIP，兼容 Windows GBK 文件名与 macOS 元数据文件。"""
    with _open_zip_robust(zip_path) as zf:
        for member in zf.infolist():
            name = _decode_zip_member_name(member)
            if not name or name.endswith('/'):
                continue
            if name.startswith('__MACOSX/') or '/__MACOSX/' in name:
                continue
            if os.path.basename(name).startswith('._'):
                continue

            target = os.path.join(dest_dir, name)
            abs_dest = os.path.abspath(dest_dir)
            abs_target = os.path.abspath(target)
            if not abs_target.startswith(abs_dest + os.sep) and abs_target != abs_dest:
                continue

            parent = os.path.dirname(abs_target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with zf.open(member) as src, open(abs_target, 'wb') as dst:
                shutil.copyfileobj(src, dst)


def _extract_zip_to_dataset(dataset, zip_path, warnings_log):
    """解压 ZIP 并导入 YOLO 数据集（支持 images/labels 目录或扁平结构）。"""
    img_dir = _images_dir(dataset['id'])
    lbl_dir = _labels_dir(dataset['id'])
    temp_dir = os.path.join(_dataset_dir(dataset['id']), '_extract_tmp')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try:
        _extract_zip_archive(zip_path, temp_dir)

        # 收集所有图片和标注
        image_files = {}
        label_files = {}

        for root, _, files in os.walk(temp_dir):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                full = os.path.join(root, fname)
                stem = os.path.splitext(fname)[0]
                rel_lower = root.lower().replace('\\', '/')

                if ext in IMAGE_EXTENSIONS:
                    # 优先 labels 同名匹配；也支持 images/ 与 labels/ 目录结构
                    image_files[stem] = full
                elif ext == LABEL_EXTENSION:
                    label_files[stem] = full

        if not image_files:
            warnings_log.append('ZIP 压缩包中未找到有效影像文件')
            return []

        imported = []
        for stem, src_path in image_files.items():
            ext = os.path.splitext(src_path)[1].lower()
            dest_name = _unique_filename(img_dir, stem + ext)
            shutil.copy2(src_path, os.path.join(img_dir, dest_name))

            label_src = label_files.get(stem)
            annotations = []
            label_warnings = []
            if label_src:
                dest_label = os.path.splitext(dest_name)[0] + LABEL_EXTENSION
                shutil.copy2(label_src, os.path.join(lbl_dir, dest_label))
                annotations, label_warnings = _read_label_file(
                    os.path.join(lbl_dir, dest_label))
            else:
                label_warnings = ['缺少同名 txt 标注文件']

            warnings_log.extend(
                [f'{dest_name}: {w}' for w in label_warnings])
            entry = _add_image_to_dataset(
                dataset, dest_name, annotations, label_warnings)
            imported.append(entry)
        return imported
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        if os.path.exists(zip_path):
            os.remove(zip_path)


# ── 静态资源路由 ────────────────────────────────────────────────

@dataset_static.route('/<path:filename>')
def serve_dataset_file(filename):
    """提供数据集影像/标注文件的 HTTP 访问。"""
    return send_from_directory(
        os.path.join(current_app.static_folder, 'dataset_library'),
        filename
    )


# ── API 路由 ────────────────────────────────────────────────────

@dataset_api.get('/stats')
def global_stats():
    """全局统计：数据集总数、影像数、标注框数、类别数。"""
    datasets = _read_index()
    return success_api(data=_global_stats(datasets))


@dataset_api.get('/samples')
def sample_images():
    """首页卡片缩略预览：最近上传的影像样本。"""
    datasets = _read_index()
    samples = []
    for ds in sorted(datasets, key=lambda d: d.get('updated_at', ''), reverse=True):
        for img in reversed(ds.get('images', [])):
            samples.append({
                'dataset_id': ds['id'],
                'dataset_name': ds['name'],
                'filename': img['filename'],
                'url': img['url'],
                'box_count': img.get('box_count', 0)
            })
            if len(samples) >= 20:
                break
        if len(samples) >= 20:
            break
    return success_api(data=samples)


@dataset_api.get('/list')
def dataset_list():
    """数据集列表（含缩略图与统计）。"""
    datasets = _read_index()
    result = []
    for ds in sorted(datasets, key=lambda d: d.get('updated_at', ''), reverse=True):
        images = ds.get('images', [])
        preview = images[0]['url'] if images else ''
        result.append({
            'id': ds['id'],
            'name': ds['name'],
            'image_count': ds.get('image_count', 0),
            'box_count': ds.get('box_count', 0),
            'class_count': ds.get('class_count', 0),
            'created_at': ds.get('created_at', ''),
            'updated_at': ds.get('updated_at', ''),
            'preview_url': preview,
            'images': images
        })
    return success_api(data=result)


@dataset_api.post('/create')
def dataset_create():
    """新建空数据集。"""
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name:
        name = f'数据集_{datetime.now().strftime("%m%d_%H%M")}'
    if len(name) > 60:
        return fail_api('数据集名称不能超过60个字符')

    now = datetime.now().isoformat(timespec='seconds')
    dataset_id = uuid.uuid4().hex[:12]
    dataset = {
        'id': dataset_id,
        'name': name,
        'created_at': now,
        'updated_at': now,
        'image_count': 0,
        'box_count': 0,
        'class_count': 0,
        'images': []
    }
    _images_dir(dataset_id)
    _labels_dir(dataset_id)

    with _lock:
        datasets = _read_index()
        datasets.append(dataset)
        _write_index(datasets)

    return success_api(msg='数据集创建成功', data=dataset)


@dataset_api.get('/<dataset_id>')
def dataset_detail(dataset_id):
    """单个数据集详情。"""
    datasets = _read_index()
    dataset = _find_dataset(datasets, dataset_id)
    if not dataset:
        return fail_api('数据集不存在')
    return success_api(data=dataset)


@dataset_api.put('/<dataset_id>/rename')
def dataset_rename(dataset_id):
    """重命名数据集。"""
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name or len(name) > 60:
        return fail_api('名称不能为空且不能超过60个字符')

    with _lock:
        datasets = _read_index()
        dataset = _find_dataset(datasets, dataset_id)
        if not dataset:
            return fail_api('数据集不存在')
        dataset['name'] = name
        dataset['updated_at'] = datetime.now().isoformat(timespec='seconds')
        _write_index(datasets)

    return success_api(msg='重命名成功', data=dataset)


@dataset_api.delete('/<dataset_id>')
def dataset_delete(dataset_id):
    """删除数据集及其文件。"""
    with _lock:
        datasets = _read_index()
        dataset = _find_dataset(datasets, dataset_id)
        if not dataset:
            return fail_api('数据集不存在')
        datasets = [d for d in datasets if d['id'] != dataset_id]
        _write_index(datasets)

    dir_path = _dataset_dir(dataset_id)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    return success_api(msg='数据集已删除')


@dataset_api.post('/<dataset_id>/upload')
def dataset_upload(dataset_id):
    """
    上传影像 / 标注 / ZIP 压缩包。
    自动匹配同名 txt，解析 YOLO 归一化水平框并校验。
    """
    files = request.files.getlist('files')
    if not files:
        return fail_api('请选择要上传的文件')

    warnings_log = []
    imported = []

    with _lock:
        datasets = _read_index()
        dataset = _find_dataset(datasets, dataset_id)
        if not dataset:
            return fail_api('数据集不存在')

        for upload in files:
            if not upload or not upload.filename:
                continue
            fname = upload.filename.lower()
            ext = os.path.splitext(fname)[1]

            if ext == '.zip':
                upload.seek(0, os.SEEK_END)
                zip_size = upload.tell()
                upload.seek(0)
                if zip_size > MAX_ZIP_SIZE:
                    warnings_log.append('ZIP 压缩包超过 10GB 限制')
                    continue
                tmp_zip = os.path.join(
                    _dataset_dir(dataset_id), f'_upload_{uuid.uuid4().hex}.zip')
                upload.save(tmp_zip)
                try:
                    items = _extract_zip_to_dataset(
                        dataset, tmp_zip, warnings_log)
                    imported.extend(items)
                except (UnicodeDecodeError, zipfile.BadZipFile, OSError) as err:
                    warnings_log.append(f'ZIP 解压失败: {err}')
                    if os.path.exists(tmp_zip):
                        os.remove(tmp_zip)
            elif ext in IMAGE_EXTENSIONS:
                entry = _process_image_file(dataset, upload, warnings_log)
                if entry:
                    imported.append(entry)
            elif ext == LABEL_EXTENSION:
                entry = _process_label_file(dataset, upload, warnings_log)
                if entry:
                    imported.append(entry)
            else:
                warnings_log.append(f'不支持的文件类型: {upload.filename}')

        dataset['updated_at'] = datetime.now().isoformat(timespec='seconds')
        _compute_dataset_stats(dataset)
        _write_index(datasets)

    # 有严重校验问题时附带 warnings 返回，前端弹窗提示
    has_errors = any(
        '超出范围' in w or '越界' in w or '格式错误' in w
        for w in warnings_log
    )
    return success_api(
        msg='上传完成' if not has_errors else '上传完成，但存在标注校验问题',
        data={
            'imported_count': len(imported),
            'imported': imported,
            'warnings': warnings_log,
            'has_errors': has_errors,
            'dataset': dataset
        }
    )


@dataset_api.post('/<dataset_id>/split')
def dataset_split(dataset_id):
    """划分训练集 / 验证集（按比例随机）。"""
    data = request.get_json(silent=True) or {}
    ratio = float(data.get('train_ratio', 0.8))
    ratio = max(0.1, min(0.9, ratio))

    with _lock:
        datasets = _read_index()
        dataset = _find_dataset(datasets, dataset_id)
        if not dataset:
            return fail_api('数据集不存在')
        images = dataset.get('images', [])
        if len(images) < 2:
            return fail_api('至少需要2张影像才能划分')

        indices = list(range(len(images)))
        random.shuffle(indices)
        split_point = int(len(indices) * ratio)
        train_set = set(indices[:split_point])

        for i, img in enumerate(images):
            img['split'] = 'train' if i in train_set else 'val'

        dataset['updated_at'] = datetime.now().isoformat(timespec='seconds')
        _write_index(datasets)

    train_count = sum(1 for img in images if img['split'] == 'train')
    val_count = len(images) - train_count
    return success_api(
        msg=f'划分完成：训练集 {train_count} 张，验证集 {val_count} 张',
        data={'train_count': train_count, 'val_count': val_count, 'dataset': dataset}
    )


@dataset_api.post('/<dataset_id>/preprocess')
def dataset_preprocess(dataset_id):
    """对数据集中指定影像执行预处理（CLAHE / 锐化 / 平滑 / 滤波）。"""
    data = request.get_json(silent=True) or {}
    filenames = data.get('filenames', [])
    prehandle = data.get('prehandle', 0)
    denoise = data.get('denoise', 0)

    if prehandle not in (0, fun_type_2, fun_type_4):
        return fail_api('预处理参数异常')
    if denoise not in (0, fun_type_3, fun_type_5):
        return fail_api('降噪参数异常')
    if not filenames:
        return fail_api('请指定要处理的影像')

    datasets = _read_index()
    dataset = _find_dataset(datasets, dataset_id)
    if not dataset:
        return fail_api('数据集不存在')

    from applications.interface.analysis import handle

    img_dir = _images_dir(dataset_id)
    processed_urls = []
    for fname in filenames:
        fpath = os.path.join(img_dir, fname)
        if not os.path.exists(fpath):
            continue
        rel = f'dataset_library/{dataset_id}/images/{fname}'
        # 复制到 upload 目录供现有处理管线使用
        target = os.path.join(up_dir, fname)
        os.makedirs(up_dir, exist_ok=True)
        shutil.copy2(fpath, target)

        result_names = [fname]
        if prehandle:
            result_names = handle(prehandle, result_names, up_dir, generate_dir)
        if denoise:
            result_names = handle(denoise, result_names, up_dir, generate_dir)

        if result_names:
            out_src = os.path.join(generate_dir, result_names[0])
            if os.path.exists(out_src):
                shutil.copy2(out_src, fpath)
                processed_urls.append(_image_url(dataset_id, fname))

    with _lock:
        datasets = _read_index()
        dataset = _find_dataset(datasets, dataset_id)
        dataset['updated_at'] = datetime.now().isoformat(timespec='seconds')
        _write_index(datasets)

    return success_api(
        msg=f'已处理 {len(processed_urls)} 张影像',
        data={'processed': processed_urls}
    )


@dataset_api.get('/<dataset_id>/export')
def dataset_export(dataset_id):
    """导出标准 YOLO 格式数据集 ZIP（images/ + labels/ + data.yaml）。"""
    datasets = _read_index()
    dataset = _find_dataset(datasets, dataset_id)
    if not dataset:
        return fail_api('数据集不存在')
    images = dataset.get('images', [])
    if not images:
        return fail_api('数据集为空，无法导出')

    buffer = io.BytesIO()
    class_names = [f'class_{i}' for i in range(NUM_CLASSES)]
    # 赛题三大类注释写入 data.yaml
    yaml_content = (
        f'path: .\n'
        f'train: images\n'
        f'val: images\n'
        f'nc: {NUM_CLASSES}\n'
        f'names:\n'
    )
    for i, name in enumerate(class_names):
        group = _category_group(i)
        yaml_content += f'  {i}: {name}  # {group}\n'

    img_dir = _images_dir(dataset_id)
    lbl_dir = _labels_dir(dataset_id)

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('data.yaml', yaml_content)
        for img in images:
            fname = img['filename']
            img_path = os.path.join(img_dir, fname)
            if os.path.exists(img_path):
                zf.write(img_path, f'images/{fname}')
            label_fname = img.get('label_filename',
                                   os.path.splitext(fname)[0] + '.txt')
            label_path = os.path.join(lbl_dir, label_fname)
            if os.path.exists(label_path):
                zf.write(label_path, f'labels/{label_fname}')
            elif img.get('annotations'):
                # 由内存标注重新生成 txt
                lines = []
                for ann in img['annotations']:
                    lines.append(
                        f"{ann['class_id']} {ann['x']} {ann['y']} "
                        f"{ann['w']} {ann['h']}"
                    )
                zf.writestr(f'labels/{label_fname}', '\n'.join(lines))

    buffer.seek(0)
    safe_name = secure_filename(dataset['name']) or 'dataset'
    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{safe_name}_yolo.zip'
    )
