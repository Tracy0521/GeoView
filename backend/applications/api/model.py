import json
import os

from flask import Blueprint, current_app

from applications.common.utils.http import success_api, fail_api

model_api = Blueprint('model_api', __name__, url_prefix='/api/model')


@model_api.get('/list/<string:model_type>')
def get_model_list(model_type):
    if model_type != 'object_detection':
        return fail_api("模型类型不正确")
    index_path = os.path.join(current_app.static_folder, 'model_library',
                              'projects.json')
    model_list = []
    if not os.path.exists(index_path):
        return success_api(data=model_list)
    with open(index_path, 'r', encoding='utf-8') as file:
        projects = json.load(file)
    supported = {'.pt'}
    for project in projects:
        for model in project.get('models', []):
            extension = os.path.splitext(model.get('stored_filename', ''))[1].lower()
            if extension not in supported:
                continue
            model_list.append({
                'model_path': 'library:{}:{}'.format(project['id'], model['id']),
                'model_type': 'detector',
                'model_name': '{} / {}'.format(project['name'], model['name'])
            })
    return success_api(data=model_list)
