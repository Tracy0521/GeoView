import os.path as osp

import cv2

from applications.common.path_global import md5_name


def resize(src_dir, save_dir, names, mode=3):
    temps = list()
    for name in names:
        img = cv2.imread(osp.join(src_dir, name))
        img = cv2.resize(img, (608, 608))
        new_name = md5_name(name)
        cv2.imwrite(osp.join(save_dir, new_name), img)
        temps.append(new_name)
    return temps
