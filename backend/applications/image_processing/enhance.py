import os.path as osp

import cv2
import numpy as np

from applications.common.path_global import md5_name


def _process(src_dir, save_dir, names, transform):
    outputs = []
    for name in names:
        image = cv2.imread(osp.join(src_dir, name))
        if image is None:
            raise RuntimeError('无法读取图片：{}'.format(name))
        result = transform(image)
        new_name = md5_name(name)
        if not cv2.imwrite(osp.join(save_dir, new_name), result):
            raise RuntimeError('增强结果保存失败：{}'.format(name))
        outputs.append(new_name)
    return outputs


def gamma_correction(src_dir, save_dir, names):
    """Lift shadow detail while preserving highlights."""
    gamma = 0.75
    table = np.array([
        ((value / 255.0) ** gamma) * 255 for value in range(256)
    ], dtype=np.uint8)
    return _process(
        src_dir, save_dir, names, lambda image: cv2.LUT(image, table))


def histogram_equalization(src_dir, save_dir, names):
    """Equalize luminance without independently shifting RGB channels."""
    def transform(image):
        ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
        ycrcb[:, :, 0] = cv2.equalizeHist(ycrcb[:, :, 0])
        return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

    return _process(src_dir, save_dir, names, transform)


def brightness_contrast(src_dir, save_dir, names):
    """Apply a conservative global contrast and brightness lift."""
    return _process(
        src_dir,
        save_dir,
        names,
        lambda image: cv2.convertScaleAbs(image, alpha=1.15, beta=12),
    )
