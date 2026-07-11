import hashlib
import random

# 上传文件地址
up_dir = "static/upload/"
# 生成的文件地址
generate_dir = "static/upload/res/"
# 网络地址
generate_url = "/_uploads/photos/res/"
up_url = "/_uploads/photos/"


def md5_name(name):
    nname = hashlib.md5(str(random.random()).encode()).hexdigest() + "_" + name
    if len(nname) > 100:
        nname = hashlib.md5(str(random.random()).encode()).hexdigest(
        ) + "." + name.split(".")[1]
    return nname


# 目标检测页面支持的图像预处理方式。
fun_type_2 = 2
fun_type_3 = 3
fun_type_4 = 4
fun_type_5 = 5
