from applications.common.scripts.init_db import init_db
from applications.extensions import db


def init_script(app):
    init_db()
    with app.app_context():
        # 为已有数据库补建后续新增的业务表；不会修改已有表和数据。
        from applications import models  # noqa: F401
        db.create_all()
