import os
from logging.config import dictConfig
import threading

from flask import Flask

import models
from models import Report, Device
import utils


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

    from views import main_views, calendar_views
    app.register_blueprint(main_views.bp)
    app.register_blueprint(calendar_views.bp)
    return app


def saveDB():
    t = threading.Timer(1800, saveDB)
    report = Report()
    report.update()
    t.daemon = True
    t.start()


def checkMac():
    t = threading.Timer(30, checkMac)
    networks = utils.detect_network()
    global macs
    for network in networks:
        mac = network['mac']
        if network['mac'] not in macs:
            macs.append(mac)
            device.post({'mac': mac})
            print(mac)
    t.daemon = True
    t.start()


if __name__ == '__main__':
    app = create_app()
    saveDB()
    macs = []
    device = Device()
    data_list = device.get(page='all')
    for data in data_list:
        macs.append(data['mac'])
    print(macs)
    checkMac()
    app.run(host='0.0.0.0', debug=False, threaded=True)

