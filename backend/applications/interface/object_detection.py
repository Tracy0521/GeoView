import json
import os
import os.path as osp

import cv2
from flask import current_app
from ultralytics import YOLO

from applications.common.path_global import generate_url, md5_name


def resolve_model_path(reference):
    if not reference or not reference.startswith('library:'):
        raise ValueError('请选择模型排行中已上传的模型')
    parts = reference.split(':')
    if len(parts) != 3:
        raise ValueError('模型标识不正确')
    project_id, model_id = parts[1], parts[2]
    root = os.path.join(current_app.static_folder, 'model_library')
    with open(os.path.join(root, 'projects.json'), 'r', encoding='utf-8') as file:
        projects = json.load(file)
    for project in projects:
        if project.get('id') != project_id:
            continue
        for model in project.get('models', []):
            if model.get('id') != model_id:
                continue
            path = os.path.abspath(os.path.join(root, project_id,
                                                model['stored_filename']))
            if not path.startswith(os.path.abspath(root) + os.sep):
                raise ValueError('模型路径不安全')
            if not osp.isfile(path) or osp.splitext(path)[1].lower() != '.pt':
                raise ValueError('目前目标检测仅支持 Ultralytics .pt 模型')
            return path
    raise ValueError('模型不存在，请重新选择')


def execute(model_path, data_path, out_dir, names, threshold=0.2):
    image_list = [osp.join(data_path, name) for name in names]
    detector = YOLO(model_path)
    results = detector.predict(source=image_list, conf=threshold, verbose=False)
    output_urls = []
    os.makedirs(out_dir, exist_ok=True)
    for name, result in zip(names, results):
        new_name = md5_name(name)
        if not cv2.imwrite(osp.join(out_dir, new_name), result.plot()):
            raise RuntimeError('检测结果保存失败：{}'.format(name))
        output_urls.append(generate_url + new_name)
    return output_urls
