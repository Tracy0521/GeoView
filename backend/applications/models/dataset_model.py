from datetime import datetime
from applications.extensions import db


class Dataset(db.Model):
    __tablename__ = "dataset"
    id = db.Column(db.String(32), primary_key=True, comment="数据集唯一ID uuid")
    name = db.Column(db.String(128), nullable=False, comment="数据集名称")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    image_count = db.Column(db.Integer, default=0)
    box_count = db.Column(db.Integer, default=0)
    class_count = db.Column(db.Integer, default=0)

    images = db.relationship("DatasetImage", back_populates="dataset", cascade="all, delete-orphan")


class DatasetImage(db.Model):
    __tablename__ = "dataset_image"
    id = db.Column(db.String(32), primary_key=True)
    dataset_id = db.Column(db.String(32), db.ForeignKey("dataset.id"), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    label_filename = db.Column(db.String(256), nullable=False)
    url = db.Column(db.String(512))
    box_count = db.Column(db.Integer, default=0)
    split = db.Column(db.String(16), default="unset")  # unset / train / val
    warnings = db.Column(db.Text, default="")

    dataset = db.relationship("Dataset", back_populates="images")
    annotations = db.relationship("DatasetAnnotation", back_populates="image", cascade="all, delete-orphan")
    # 一对一关联影像信息
    image_info = db.relationship("ImageInfo", back_populates="image", uselist=False, cascade="all, delete-orphan")


class DatasetAnnotation(db.Model):
    __tablename__ = "dataset_annotation"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    image_id = db.Column(db.String(32), db.ForeignKey("dataset_image.id"), nullable=False)
    class_id = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(32))
    x = db.Column(db.Float)
    y = db.Column(db.Float)
    w = db.Column(db.Float)
    h = db.Column(db.Float)

    image = db.relationship("DatasetImage", back_populates="annotations")


# ========== 新增：单张影像信息表 ==========
class ImageInfo(db.Model):
    __tablename__ = "image_info"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    image_id = db.Column(db.String(32), db.ForeignKey("dataset_image.id"), nullable=False, unique=True, comment="关联dataset_image主键，一对一")

    # 遥感影像常用字段，你按需增删
    width = db.Column(db.Integer, comment="影像宽度像素")
    height = db.Column(db.Integer, comment="影像高度像素")
    channels = db.Column(db.Integer, comment="通道数")
    file_size = db.Column(db.BigInteger, comment="文件字节大小")
    geo_extent = db.Column(db.Text, comment="地理范围JSON字符串")
    projection = db.Column(db.String(256), comment="投影坐标系")
    upload_time = db.Column(db.DateTime, default=datetime.now)
    extra_meta = db.Column(db.Text, comment="其他扩展元信息(json)")

    image = db.relationship("DatasetImage", back_populates="image_info")