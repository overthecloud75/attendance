import os
from logging.config import dictConfig
import threading
import time

from flask import Flask, current_app
from flaskext.markdown import Markdown

from models import Report, Device, Mac, get_setting
import utils

BASE_DIR= os.getcwd()
LOG_DIR = 'logs'
print(BASE_DIR)
if os.path.exists(os.path.join(BASE_DIR, LOG_DIR)):
    pass
else:
    os.mkdir(os.path.join(BASE_DIR, LOG_DIR))

import logging
from flask import has_request_context, request
from flask.logging import default_handler

class RequestFormatter(logging.Formatter):
    def format(self, record):
        if has_request_context():
            record.url = request.url
            record.remote_addr = request.remote_addr
        else:
            record.url = None
            record.remote_addr = None

        return super().format(record)

def create_app():
    # https://flask.palletsprojects.com/en/2.0.x/logging/
    # https://wikidocs.net/81081
    dictConfig({
        'version': 1,
        'formatters': {
            'default': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            }
        },
        'handlers': {
            'file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': os.path.join(BASE_DIR, LOG_DIR, 'project.log'),
                'maxBytes': 1024 * 1024 * 5,  # 5 MB
                'backupCount': 5,
                'formatter': 'default',
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['file']
        }
    })

    app = Flask(__name__)
    # https://wikidocs.net/81066
    Markdown(app, extensions=['nl2br', 'fenced_code'])

    app.config['SECRET_KEY'] = os.urandom(32)
    app.config['SESSION_COOKIE_SECURE'] = True

    from views import main_views, user_views, calendar_views, board_views
    app.register_blueprint(main_views.bp)
    app.register_blueprint(user_views.bp)
    app.register_blueprint(calendar_views.bp)
    app.register_blueprint(board_views.bp)

    # Manually Push a Context https://flask.palletsprojects.com/en/2.0.x/appcontext/
    # with app.app_context():
    #    save_db()
    return app


def save_db():
    report = Report()
    report.update()
    # report.update(date='2021-10-11')
    t = threading.Timer(1800, save_db)
    app.logger.info('save_db')
    t.daemon = True
    t.start()


def check_mac():
    devices = Device()
    mac = Mac()
    macs = []
    data_list = devices.get(page='all')
    for data in data_list:
        macs.append(data['mac'])
    while True:
        wifi_connected = utils.check_wifi_connected()
        if not wifi_connected:
            utils.connect_wifi()
        for ip in range(155):
            if ip not in [0, 1, 2, 5, 255]:
                network = utils.check_arp(ip)
                if network:
                    # app.logger.info(network)
                    if network['mac'] not in macs:
                        macs.append(network['mac'])
                        devices.new_post({'mac': network['mac']})
                    mac.post(network)
        time.sleep(5)


if __name__ == '__main__':
    app = create_app()
    save_db()

    use_wifi_attendance, _, _, _, _, _ = get_setting()

    if use_wifi_attendance:
        th = threading.Thread(target=check_mac)
        th.daemon = True
        th.start()

    app.run(host='127.0.0.1', debug=False, threaded=True)

