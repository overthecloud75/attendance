import os
from logging.config import dictConfig
import threading
import time

from flask import Flask, current_app

from models import Report, Device, Mac, get_setting
import utils

def create_app():
    # https://flask.palletsprojects.com/en/2.0.x/logging/
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
    device = Device()
    mac = Mac()
    macs = []
    data_list = device.get(page='all')
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
                    mac.post(network)
                    if network['mac'] not in macs:
                        macs.append(network['mac'])
                        device.post({'mac': network['mac']})
        time.sleep(5)


if __name__ == '__main__':
    app = create_app()
    save_db()

    use_wifi_attendance, _, _, _, _, _, _ = get_setting()

    if use_wifi_attendance:
        th = threading.Thread(target=check_mac)
        th.daemon = True
        th.start()

    app.run(host='127.0.0.1', debug=False, threaded=True)

