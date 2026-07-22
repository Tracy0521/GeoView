from applications.common.scripts.init_db import init_db
from applications.extensions import db


def _ensure_model_source_columns():
    """Backfill additive columns for deployments that rely on create_all()."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if not inspector.has_table('model_record'):
        return
    existing = {column['name'] for column in inspector.get_columns('model_record')}
    definitions = {
        'source_type': "VARCHAR(20) DEFAULT 'local'",
        'source_server': "VARCHAR(80) DEFAULT ''",
        'remote_path': "VARCHAR(500) DEFAULT ''",
        'sync_status': "VARCHAR(20) DEFAULT 'synced'"
    }
    with db.engine.begin() as connection:
        for name, definition in definitions.items():
            if name not in existing:
                connection.execute(text('ALTER TABLE model_record ADD COLUMN {} {}'.format(name, definition)))


def _ensure_dataset_source_columns():
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if not inspector.has_table('dataset'):
        return
    existing = {column['name'] for column in inspector.get_columns('dataset')}
    definitions = {
        'source_type': "VARCHAR(20) DEFAULT 'local'",
        'source_server': "VARCHAR(80) DEFAULT ''",
        'remote_path': "VARCHAR(500) DEFAULT ''",
        'sync_status': "VARCHAR(20) DEFAULT 'synced'"
    }
    with db.engine.begin() as connection:
        for name, definition in definitions.items():
            if name not in existing:
                connection.execute(text('ALTER TABLE dataset ADD COLUMN {} {}'.format(name, definition)))


def init_script(app):
    init_db()
    with app.app_context():
        # 为已有数据库补建后续新增的业务表；不会修改已有表和数据。
        from applications import models  # noqa: F401
        db.create_all()
        _ensure_model_source_columns()
        _ensure_dataset_source_columns()
