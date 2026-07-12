from flask import Blueprint, request

from applications.common.path_global import (
    fun_type_2, fun_type_3, fun_type_4, fun_type_5, generate_dir, up_dir
)
from applications.common.utils.http import fail_api, success_api
from applications.interface.analysis import object_detection
from applications.interface.object_detection import resolve_model_path

analysis_api = Blueprint('analysis_api', __name__, url_prefix='/api/analysis')


@analysis_api.post('/object_detection')
def object_detection_api():
    req_json = request.get_json(silent=True) or {}
    model_path = req_json.get('model_path')
    try:
        model_path = resolve_model_path(model_path)
    except Exception as error:
        return fail_api(str(error))

    image_list = req_json.get('list')
    prehandle = req_json.get('prehandle')
    denoise = req_json.get('denoise')
    if prehandle not in (0, fun_type_2, fun_type_4) or denoise not in (
            0, fun_type_3, fun_type_5):
        return fail_api('参数异常')
    if not image_list:
        return fail_api('请上传图片')

    object_detection(model_path, up_dir, generate_dir, image_list,
                     prehandle, denoise, 2)
    return success_api()


@analysis_api.post('/image_pre')
def image_pre():
    req_json = request.get_json(silent=True) or {}
    image_list = req_json.get('list')
    prehandle = req_json.get('prehandle')
    if not image_list:
        return fail_api('请上传图片')
    if prehandle not in (fun_type_2, fun_type_4):
        return fail_api('参数异常')

    from applications.common.path_global import generate_url
    from applications.common.utils.upload import img_url_handle
    from applications.interface.analysis import handle

    images = [img_url_handle(image) for image in image_list]
    processed = handle(prehandle, images, up_dir, generate_dir)
    return success_api(data=[generate_url + image for image in processed])
