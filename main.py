import os
from logging.config import dictConfig
from flask import Flask
import threading
import models

def create_app():
    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s: %(message)s',
        }},
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })

    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(32)

    from views import main_views
    app.register_blueprint(main_views.bp)
    return app

def saveDB():
    t = threading.Timer(1800, saveDB)
    models.saveDB()
    t.start()

if __name__ == '__main__':
    app = create_app()
    saveDB()
    app.run(host='0.0.0.0', debug=True, threaded=True)

