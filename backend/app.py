import traceback
from datetime import timedelta

from flask import session
from flask_migrate import Migrate

from applications import create_app
from applications.common.utils.http import fail_api
from applications.extensions import db
# ============新增导入============
from applications.models.dataset_model import DatasetClass

debug_mode = False
app = create_app()

# ============新增：启动自动创建dataset_class表============
with app.app_context():
    # checkfirst=True 表存在则跳过，不存在自动创建，安全无冲突
    DatasetClass.__table__.create(bind=db.engine, checkfirst=True)


@app.before_request
def before():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=20)


@app.errorhandler(Exception)
def error_handler(e):
    if debug_mode:
        traceback.print_exc()
    return fail_api("后端出现异常：{}".format(str(e)))


migrate = Migrate(app, db)

if __name__ == '__main__':
    import yaml
    with open('../config.yaml') as file:
        config = yaml.load(file.read(), Loader=yaml.FullLoader)
    debug_mode = bool(config.get("debug", False))
    with open("../frontend/.env", 'w') as file:
        file.write(
            "VUE_APP_BACKEND_PORT = {}\nVUE_APP_BACKEND_IP = {}".format(
                config["port"]["backend"], config["host"]["backend"]
                if config["host"]["backend"] != "0.0.0.0" else "127.0.0.1"))
    app.run(host=config["host"]["backend"], port=config["port"]["backend"])