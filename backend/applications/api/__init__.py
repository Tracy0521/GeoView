from flask import Flask

from applications.api.analysis import analysis_api
from applications.api.file import file_api
from applications.api.history import history_api
from applications.api.model import model_api
from applications.api.model_rank import model_rank_api
from applications.api.dataset import dataset_api, dataset_static


def system_api(app: Flask):
    app.register_blueprint(file_api)
    app.register_blueprint(history_api)
    app.register_blueprint(analysis_api)
    app.register_blueprint(model_api)
    app.register_blueprint(model_rank_api)
    app.register_blueprint(dataset_api)
    app.register_blueprint(dataset_static)
    pass
