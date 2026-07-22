import datetime

from applications.extensions import db


class ModelProject(db.Model):
    __tablename__ = 'model_project'

    id = db.Column(db.String(12), primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(300), default='')
    created_at = db.Column(db.DateTime, default=datetime.datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now, nullable=False)
    model_records = db.relationship('ModelRecord', backref='project', cascade='all, delete-orphan',
                                    order_by='ModelRecord.created_at', lazy=True)


class ModelRecord(db.Model):
    __tablename__ = 'model_record'

    id = db.Column(db.String(12), primary_key=True)
    project_id = db.Column(db.String(12), db.ForeignKey('model_project.id'), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    filename = db.Column(db.String(255), default='')
    stored_filename = db.Column(db.String(255), default='')
    size = db.Column(db.BigInteger, default=0)
    framework = db.Column(db.String(40), default='PyTorch')
    score = db.Column(db.String(30), default='')
    training_date = db.Column(db.String(20), default='')
    training_epochs = db.Column(db.Integer, nullable=True)
    metrics = db.Column(db.JSON, default=dict)
    source_type = db.Column(db.String(20), default='local')
    source_server = db.Column(db.String(80), default='')
    remote_path = db.Column(db.String(500), default='')
    sync_status = db.Column(db.String(20), default='synced')
    created_at = db.Column(db.DateTime, default=datetime.datetime.now, nullable=False)
