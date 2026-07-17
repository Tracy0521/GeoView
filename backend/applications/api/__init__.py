from flask import Flask

from applications.api.file import file_api
from applications.api.history import history_api
from applications.api.model import model_api
from applications.api.model_rank import model_rank_api
from applications.api.dataset import dataset_api, dataset_static


def system_api(app: Flask):
    app.register_blueprint(file_api)
    app.register_blueprint(history_api)
    app.register_blueprint(model_api)
    app.register_blueprint(model_rank_api)
    app.register_blueprint(dataset_api)
    app.register_blueprint(dataset_static)

    # Keep the management APIs available even when optional native image
    # dependencies (for example OpenCV) cannot be imported.  Importing this
    # blueprint at module load time previously prevented the whole backend
    # from starting, leaving every frontend page stuck on its loading state.
    try:
        from applications.api.analysis import analysis_api
    except (ImportError, RuntimeError) as exc:
        app.logger.warning('Image analysis API is unavailable: %s', exc)
    else:
        app.register_blueprint(analysis_api)
    pass
