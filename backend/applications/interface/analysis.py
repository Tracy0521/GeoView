from applications.common.path_global import up_url
from applications.common.utils.upload import img_url_handle
from applications.extensions import db
from applications.image_processing.CLAHE import CLAHE
from applications.image_processing.gaussian_blur import gaussian_blur
from applications.image_processing.median_blur import median_blur
from applications.image_processing.resize import resize
from applications.image_processing.sharpen import sharpen
from applications.interface import object_detection as detection
from applications.models.analysis import Analysis


def save_analysis(type_, before_img, after_img, checked='0,0'):
    analysis = Analysis(
        type=type_, before_img=before_img, before_img1='',
        after_img=after_img, data='', is_hole=False, checked=checked)
    db.session.add(analysis)
    db.session.commit()


def object_detection(model_path, data_path, out_dir, names, prehandle,
                     denoise, type_):
    images = [img_url_handle(name) for name in names]
    resized = resize(data_path, data_path, images, mode=3)

    processed = resized
    if prehandle:
        processed = handle(prehandle, processed, data_path, data_path)
    if denoise:
        processed = handle(denoise, processed, data_path, data_path)

    result_images = detection.execute(model_path, data_path, out_dir, processed)
    for index, result_image in enumerate(result_images):
        save_analysis(
            type_, up_url + resized[index], result_image,
            checked=f'{prehandle},{denoise}')


def handle(fun_type, images, src_dir, save_dir):
    processors = {
        2: CLAHE,
        3: median_blur,
        4: sharpen,
        5: gaussian_blur,
    }
    return processors[fun_type](src_dir, save_dir, images)
