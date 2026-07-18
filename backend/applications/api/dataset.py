"""
数据集管理 API — 遥感影像上传、YOLO 标注解析、存储与导出。
元数据存储迁移至MySQL，影像文件保留在static/dataset_library
新增image_info子表存储单张遥感影像地理/像素元信息
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
from PIL import Image

from flask import Blueprint, current_app, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from applications.common.path_global import (
    fun_type_2, fun_type_3, fun_type_4, fun_type_5, generate_dir, up_dir
)
from applications.common.utils.http import fail_api, success_api
from applications.extensions import db
from applications.models.dataset_model import Dataset, DatasetImage, DatasetAnnotation, ImageInfo

dataset_api = Blueprint('dataset_api', __name__, url_prefix='/api/dataset')
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


def _sync_dataset_stat(ds_model: Dataset):
    """根据图片与标注重新统计并更新数据集统计字段"""
    all_images = DatasetImage.query.filter_by(dataset_id=ds_model.id).all()
    box_total = 0
    class_set = set()
    for img in all_images:
        anns = DatasetAnnotation.query.filter_by(image_id=img.id).all()
        box_total += len(anns)
        for a in anns:
            class_set.add(a.class_id)
    ds_model.image_count = len(all_images)
    ds_model.box_count = box_total
    ds_model.class_count = len(class_set)
    ds_model.updated_at = datetime.now()
    db.session.commit()


def _build_image_dict(img_model: DatasetImage):
    """数据库模型 → 前端JSON结构，携带image_info影像元信息"""
    ann_models = DatasetAnnotation.query.filter_by(image_id=img_model.id).all()
    ann_list = []
    for ann in ann_models:
        ann_list.append({
            "class_id": ann.class_id,
            "category": ann.category,
            "x": ann.x,
            "y": ann.y,
            "w": ann.w,
            "h": ann.h
        })
    # 读取一对一影像信息
    info_data = None
    if img_model.image_info:
        info_data = {
            "width": img_model.image_info.width,
            "height": img_model.image_info.height,
            "channels": img_model.image_info.channels,
            "file_size": img_model.image_info.file_size,
            "geo_extent": img_model.image_info.geo_extent,
            "projection": img_model.image_info.projection,
            "extra_meta": img_model.image_info.extra_meta
        }
    return {
        "id": img_model.id,
        "filename": img_model.filename,
        "label_filename": img_model.label_filename,
        "url": img_model.url,
        "annotations": ann_list,
        "box_count": len(ann_list),
        "split": img_model.split,
        "warnings": img_model.warnings.split("||") if img_model.warnings else [],
        "image_info": info_data
    }


def _add_image_record(dataset_id: str, full_img_path: str, image_filename: str, annotations: list, warnings: list, file_size: int):
    """
    【新版数据库写入核心函数，替代旧版_add_image_to_dataset】
    1. 写入dataset_image主记录
    2. 写入对应annotation标注框
    3. 解析影像宽高/通道，写入一对一ImageInfo影像信息子表
    """
    stem = os.path.splitext(image_filename)[0]
    label_filename = stem + LABEL_EXTENSION
    img_id = uuid.uuid4().hex[:10]
    warning_str = "||".join(warnings) if warnings else ""

    # 读取影像像素信息
    width = None
    height = None
    channels = None
    try:
        with Image.open(full_img_path) as img:
            width, height = img.size
            channels = len(img.getbands())
    except Exception:
        pass

    # 查找是否已存在该图片记录
    exist_img = DatasetImage.query.filter_by(dataset_id=dataset_id, filename=image_filename).first()
    if exist_img:
        img_model = exist_img
        img_model.warnings = warning_str
        # 清空原有标注
        DatasetAnnotation.query.filter_by(image_id=img_model.id).delete()
    else:
        img_model = DatasetImage(
            id=img_id,
            dataset_id=dataset_id,
            filename=image_filename,
            label_filename=label_filename,
            url=_image_url(dataset_id, image_filename),
            box_count=len(annotations),
            split="unset",
            warnings=warning_str
        )
        db.session.add(img_model)
        db.session.flush()

    # 新增所有标注
    for ann in annotations:
        ann_model = DatasetAnnotation(
            image_id=img_model.id,
            class_id=ann["class_id"],
            category=ann["category"],
            x=ann["x"],
            y=ann["y"],
            w=ann["w"],
            h=ann["h"]
        )
        db.session.add(ann_model)

    # 一对一：新增/更新ImageInfo影像信息子表
    info_model = ImageInfo.query.filter_by(image_id=img_model.id).first()
    if not info_model:
        info_model = ImageInfo(
            image_id=img_model.id,
            width=width,
            height=height,
            channels=channels,
            file_size=file_size
        )
        db.session.add(info_model)
    else:
        info_model.width = width
        info_model.height = height
        info_model.channels = channels
        info_model.file_size = file_size
    db.session.commit()
    return _build_image_dict(img_model)


def _process_image_file(dataset_id, file_storage, warnings_log):
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

    img_dir = _images_dir(dataset_id)
    lbl_dir = _labels_dir(dataset_id)
    filename = _unique_filename(img_dir, original)
    full_save_path = os.path.join(img_dir, filename)
    file_storage.save(full_save_path)

    stem = os.path.splitext(filename)[0]
    label_path = os.path.join(lbl_dir, stem + LABEL_EXTENSION)
    annotations, label_warnings = _read_label_file(label_path)
    warnings_log.extend(label_warnings)
    # 调用数据库写入函数，传入完整文件路径与文件大小
    return _add_image_record(dataset_id, full_save_path, filename, annotations, label_warnings, size)


def _process_label_file(dataset_id, file_storage, warnings_log):
    original = secure_filename(file_storage.filename) or 'label.txt'
    if not original.lower().endswith(LABEL_EXTENSION):
        return None

    lbl_dir = _labels_dir(dataset_id)
    img_dir = _images_dir(dataset_id)
    filename = _unique_filename(lbl_dir, original)
    file_storage.save(os.path.join(lbl_dir, filename))

    stem = os.path.splitext(filename)[0]
    matched_image = None
    matched_img_full_path = ""
    for ext in IMAGE_EXTENSIONS:
        candidate = stem + ext
        cand_path = os.path.join(img_dir, candidate)
        if os.path.exists(cand_path):
            matched_image = candidate
            matched_img_full_path = cand_path
            break

    if not matched_image:
        warnings_log.append(f'标注 {filename} 暂无匹配影像，已保存待匹配')
        return None

    annotations, label_warnings = _read_label_file(os.path.join(lbl_dir, filename))
    warnings_log.extend(label_warnings)
    # 获取图片文件大小
    file_size = os.path.getsize(matched_img_full_path) if os.path.exists(matched_img_full_path) else 0
    return _add_image_record(dataset_id, matched_img_full_path, matched_image, annotations, label_warnings, file_size)


def _open_zip_robust(zip_path):
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


def _extract_zip_to_dataset(dataset_id, zip_path, warnings_log):
    img_dir = _images_dir(dataset_id)
    lbl_dir = _labels_dir(dataset_id)
    temp_dir = os.path.join(_dataset_dir(dataset_id), '_extract_tmp')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try:
        _extract_zip_archive(zip_path, temp_dir)
        image_files = {}
        label_files = {}

        for root, _, files in os.walk(temp_dir):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                full = os.path.join(root, fname)
                stem = os.path.splitext(fname)[0]
                if ext in IMAGE_EXTENSIONS:
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
            full_dest_img = os.path.join(img_dir, dest_name)
            shutil.copy2(src_path, full_dest_img)

            label_src = label_files.get(stem)
            annotations = []
            label_warnings = []
            if label_src:
                dest_label = os.path.splitext(dest_name)[0] + LABEL_EXTENSION
                shutil.copy2(label_src, os.path.join(lbl_dir, dest_label))
                annotations, label_warnings = _read_label_file(os.path.join(lbl_dir, dest_label))
            else:
                label_warnings = ['缺少同名 txt 标注文件']

            warnings_log.extend([f'{dest_name}: {w}' for w in label_warnings])
            img_size = os.path.getsize(full_dest_img) if os.path.exists(full_dest_img) else 0
            entry = _add_image_record(dataset_id, full_dest_img, dest_name, annotations, label_warnings, img_size)
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
    return send_from_directory(
        os.path.join(current_app.static_folder, 'dataset_library'),
        filename
    )


# ── API 路由 ────────────────────────────────────────────────────
from datetime import datetime, timedelta

# 全局缓存变量
_stats_cache = None
_stats_expire = None

@dataset_api.get("/stats")
def global_stats():
    global _stats_cache, _stats_expire
    now = datetime.now()
    # 缓存5分钟
    if _stats_cache and _stats_expire and now < _stats_expire:
        return success_api(data=_stats_cache)

    # 原有统计逻辑
    all_ds = Dataset.query.all()
    total_ds = len(all_ds)
    total_img = sum(ds.image_count for ds in all_ds)
    total_box = sum(ds.box_count for ds in all_ds)
    total_cls = 25

    res_data = {
        "dataset_count": total_ds,
        "image_count": total_img,
        "box_count": total_box,
        "class_count": total_cls
    }
    # 更新缓存
    _stats_cache = res_data
    _stats_expire = now + timedelta(minutes=5)
    return success_api(data=res_data)


from sqlalchemy.orm import joinedload

@dataset_api.get('/samples')
def sample_images():
    ds_list = Dataset.query.order_by(Dataset.updated_at.desc()).all()
    samples = []
    for ds in ds_list:
        # 1. 数据库层只取每个数据集最新8张，不查全量图片
        # 2. joinedload 预加载标注关联，仅1次子查询，不再循环每张图查annotation
        imgs = DatasetImage.query.filter_by(dataset_id=ds.id) \
            .options(joinedload(DatasetImage.annotations)) \
            .order_by(DatasetImage.id.desc()).limit(8).all()

        for img in imgs:
            samples.append({
                'dataset_id': ds.id,
                'dataset_name': ds.name,
                'filename': img.filename,
                'url': img.url,
                # 直接取关联列表长度，不用额外SQL
                'box_count': len(img.annotations)
            })
            # 全局最多20张预览，提前终止循环
            if len(samples) >= 20:
                break
        if len(samples) >= 20:
            break
    return success_api(data=samples)


@dataset_api.get("/list")
def get_dataset_list():
    # 分页参数
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("limit", 10, type=int)
    offset = (page - 1) * page_size

    ds_list = Dataset.query.order_by(Dataset.updated_at.desc()).limit(page_size).offset(offset).all()
    result = []
    for ds in ds_list:
        # 每个数据集仅取8张预览图，不查全部7000+
        preview_imgs = DatasetImage.query.filter_by(dataset_id=ds.id).order_by(DatasetImage.id.desc()).limit(8).all()
        img_arr = []
        for img in preview_imgs:
            img_arr.append({
                "id": img.id,
                "filename": img.filename,
                "url": img.url,
                "split": img.split,
                "warnings": img.warnings,
                # 只返回数字，不返回完整标注数组，大幅瘦身JSON
                "box_count": img.box_count
            })
        result.append({
            "id": ds.id,
            "name": ds.name,
            "created_at": ds.created_at,
            "updated_at": ds.updated_at,
            "image_count": ds.image_count,
            "box_count": ds.box_count,
            "class_count": ds.class_count,
            "images": img_arr
        })
    return success_api(data=result)


@dataset_api.post('/create')
def dataset_create():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name:
        name = f'数据集_{datetime.now().strftime("%m%d_%H%M")}'
    if len(name) > 60:
        return fail_api('数据集名称不能超过60个字符')

    dataset_id = uuid.uuid4().hex[:12]
    ds_model = Dataset(
        id=dataset_id,
        name=name,
        image_count=0,
        box_count=0,
        class_count=0
    )
    _images_dir(dataset_id)
    _labels_dir(dataset_id)
    db.session.add(ds_model)
    db.session.commit()

    resp_data = {
        "id": ds_model.id,
        "name": ds_model.name,
        "created_at": ds_model.created_at.isoformat(timespec='seconds'),
        "updated_at": ds_model.updated_at.isoformat(timespec='seconds'),
        "image_count": 0,
        "box_count": 0,
        "class_count": 0,
        "images": []
    }
    return success_api(msg='数据集创建成功', data=resp_data)


@dataset_api.get('/<dataset_id>')
def dataset_detail(dataset_id):
    ds = Dataset.query.get(dataset_id)
    if not ds:
        return fail_api('数据集不存在')
    imgs = DatasetImage.query.filter_by(dataset_id=dataset_id).all()
    img_list = [_build_image_dict(i) for i in imgs]
    resp = {
        "id": ds.id,
        "name": ds.name,
        "created_at": ds.created_at.isoformat(timespec='seconds'),
        "updated_at": ds.updated_at.isoformat(timespec='seconds'),
        "image_count": ds.image_count,
        "box_count": ds.box_count,
        "class_count": ds.class_count,
        "images": img_list
    }
    return success_api(data=resp)


@dataset_api.put('/<dataset_id>/rename')
def dataset_rename(dataset_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    if not name or len(name) > 60:
        return fail_api('名称不能为空且不能超过60个字符')
    ds = Dataset.query.get(dataset_id)
    if not ds:
        return fail_api('数据集不存在')
    ds.name = name
    ds.updated_at = datetime.now()
    db.session.commit()
    return success_api(msg='重命名成功')


@dataset_api.delete('/<dataset_id>')
def dataset_delete(dataset_id):
    ds = Dataset.query.get(dataset_id)
    if not ds:
        return fail_api('数据集不存在')
    db.session.delete(ds)
    db.session.commit()
    dir_path = _dataset_dir(dataset_id)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    return success_api(msg='数据集已删除')


@dataset_api.post('/<dataset_id>/upload')
def dataset_upload(dataset_id):
    files = request.files.getlist('files')
    if not files:
        return fail_api('请选择要上传的文件')
    warnings_log = []
    imported = []
    ds = Dataset.query.get(dataset_id)
    if not ds:
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
            tmp_zip = os.path.join(_dataset_dir(dataset_id), f'_upload_{uuid.uuid4().hex}.zip')
            upload.save(tmp_zip)
            try:
                items = _extract_zip_to_dataset(dataset_id, tmp_zip, warnings_log)
                imported.extend(items)
            except Exception as err:
                warnings_log.append(f'ZIP 解压失败: {err}')
                if os.path.exists(tmp_zip):
                    os.remove(tmp_zip)
        elif ext in IMAGE_EXTENSIONS:
            entry = _process_image_file(dataset_id, upload, warnings_log)
            if entry:
                imported.append(entry)
        elif ext == LABEL_EXTENSION:
            entry = _process_label_file(dataset_id, upload, warnings_log)
            if entry:
                imported.append(entry)
        else:
            warnings_log.append(f'不支持的文件类型: {upload.filename}')
    _sync_dataset_stat(ds)
    has_errors = any('超出范围' in w or '越界' in w or '格式错误' in w for w in warnings_log)
    return success_api(
        msg='上传完成' if not has_errors else '上传完成，但存在标注校验问题',
        data={
            'imported_count': len(imported),
            'imported': imported,
            'warnings': warnings_log,
            'has_errors': has_errors,
            'dataset': {
                "id": ds.id,
                "name": ds.name,
                "image_count": ds.image_count,
                "box_count": ds.box_count,
                "class_count": ds.class_count,
                "updated_at": ds.updated_at.isoformat(timespec='seconds')
            }
        }
    )


@dataset_api.post('/<dataset_id>/split')
def dataset_split(dataset_id):
    data = request.get_json(silent=True) or {}
    ratio = float(data.get('train_ratio', 0.8))
    ratio = max(0.1, min(0.9, ratio))
    ds = Dataset.query.get(dataset_id)
    if not ds:
        return fail_api('数据集不存在')
    img_models = DatasetImage.query.filter_by(dataset_id=dataset_id).all()
    if len(img_models) < 2:
        return fail_api('至少需要2张影像才能划分')
    random.shuffle(img_models)
    split_idx = int(len(img_models) * ratio)
    for idx, img in enumerate(img_models):
        img.split = "train" if idx < split_idx else "val"
    db.session.commit()
    train_count = sum(1 for x in img_models if x.split == "train")
    val_count = len(img_models) - train_count
    return success_api(
        msg=f'划分完成：训练集 {train_count} 张，验证集 {val_count} 张',
        data={'train_count': train_count, 'val_count': val_count}
    )


@dataset_api.post('/<dataset_id>/preprocess')
def dataset_preprocess(dataset_id):
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
    ds = Dataset.query.get(dataset_id)
    if not ds:
        return fail_api('数据集不存在')
    from applications.interface.analysis import handle
    img_dir = _images_dir(dataset_id)
    processed_urls = []
    for fname in filenames:
        fpath = os.path.join(img_dir, fname)
        if not os.path.exists(fpath):
            continue
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
                # 更新处理后图片尺寸信息
                file_size = os.path.getsize(fpath)
                img_record = DatasetImage.query.filter_by(dataset_id=dataset_id, filename=fname).first()
                if img_record and img_record.image_info:
                    try:
                        with Image.open(fpath) as img:
                            w, h = img.size
                            ch = len(img.getbands())
                            img_record.image_info.width = w
                            img_record.image_info.height = h
                            img_record.image_info.channels = ch
                            img_record.image_info.file_size = file_size
                            db.session.commit()
                    except Exception:
                        pass
    return success_api(msg=f'已处理 {len(processed_urls)} 张影像', data={'processed': processed_urls})


@dataset_api.get('/<dataset_id>/export')
def dataset_export(dataset_id):
    ds = Dataset.query.get(dataset_id)
    if not ds:
        return fail_api('数据集不存在')
    img_models = DatasetImage.query.filter_by(dataset_id=dataset_id).all()
    if not img_models:
        return fail_api('数据集为空，无法导出')
    buffer = io.BytesIO()
    class_names = [f'class_{i}' for i in range(NUM_CLASSES)]
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
        for img in img_models:
            fname = img.filename
            img_path = os.path.join(img_dir, fname)
            if os.path.exists(img_path):
                zf.write(img_path, f'images/{fname}')
            label_fname = img.label_filename
            label_path = os.path.join(lbl_dir, label_fname)
            anns = DatasetAnnotation.query.filter_by(image_id=img.id).all()
            if os.path.exists(label_path):
                zf.write(label_path, f'labels/{label_fname}')
            elif anns:
                lines = []
                for ann in anns:
                    lines.append(f"{ann.class_id} {ann.x} {ann.y} {ann.w} {ann.h}")
                zf.writestr(f'labels/{label_fname}', '\n'.join(lines))
    buffer.seek(0)
    safe_name = secure_filename(ds.name) or 'dataset'
    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{safe_name}_yolo.zip'
    )