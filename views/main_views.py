from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify, send_file, make_response
from io import BytesIO, StringIO
from csvalidate import ValidatedWriter
from werkzeug.utils import redirect
from datetime import date

from models import get_setting, Report, Device
from form import PeriodSubmitForm, DeviceSubmitForm
from utils import request_get, log_message
from .utils import *


# blueprint
bp = Blueprint('main', __name__, url_prefix='/')


@bp.before_app_request
def load_logged_in_user():
    message = log_message(request.headers)
    current_app.logger.info(message)

    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = {}
        for key in session:
            g.user[key] = session[key]


@bp.after_request
def add_security_headers(resp):
    # https://flask.palletsprojects.com/en/2.1.x/security/
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


def date_form(start, end):
    form = PeriodSubmitForm()
    start = start or date.today().strftime('%Y-%m-%d')
    end = end or date.today().strftime('%Y-%m-%d')

    form.start.data = start
    form.end.data = end
    return form, start, end


@bp.route('/')
def index():
    return redirect(url_for('main.attend'))


@bp.route('/setting/', methods=('GET', 'POST'))
@admin_required
def setting():
    use_wifi_attendance, use_notice_email, account, cc, working, employees_status = get_setting()
    return render_template('setting/setting.html', **locals())


@bp.route('/device/', methods=('GET', ))
@admin_required
def device():
    form = DeviceSubmitForm()
    devices = Device()
    page, _, _, _ = request_get(request.args)
    paging, data_list = devices.get(page=page, date=date.today().strftime('%Y-%m-%d'))
    return render_template('setting/device.html', **locals())


@bp.route('/update_device/', methods=('GET', 'POST'))
@admin_required
def update_device():
    form = DeviceSubmitForm()
    devices = Device()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'mac': form.mac.data, 'owner': form.owner.data, 'device': form.device.data}
        if form.registerDate.data:
            request_data['registerDate'] = form.registerDate.data.strftime('%Y-%m-%d')
        if form.endDate.data:
            request_data['endDate'] = form.endDate.data.strftime('%Y-%m-%d')
        devices.post(request_data)
        return redirect(url_for('main.device'))
    _id = request.args.get('_id', '')
    data = devices.get_by_id(_id=_id)
    return render_template('setting/update_device.html', **locals())


@bp.route('/wifi_attend/', methods=('GET', ))
def wifi_attend():
    report = Report()
    page, _, start, end = request_get(request.args)
    form, start, end = date_form(start, end)

    paging, data_list = report.wifi_attend(page=page, start=start, end=end)
    return render_template('setting/wifi_attend.html', **locals())


@bp.route('/attend/', methods=('GET', 'POST'))
@client_ip_check
def attend():
    report = Report()
    # https://gist.github.com/doobeh/3e685ef25fac7d03ded7#file-vort-html-L11
    if request.method == 'POST':
        start = request.form['start']
        end = request.form['end']
        name = request.form['name']
        data_list = report.attend(page='all', name=name, start=start, end=end)
        if data_list:
            encoding = 'utf-8-sig'
            filename = 'attend' + '_' + start + '_' + end + '_' + name + '.csv'
            buf = StringIO()
            writer = ValidatedWriter(buf, fieldnames=data_list[0].keys())
            writer.writeheader()
            for data in data_list:
                writer.writerow(data)
            buf.seek(0)
            buf = BytesIO(buf.read().encode(encoding))
            return send_file(buf, attachment_filename=filename, as_attachment=True, mimetype='text/csv')

    page, name, start, end = request_get(request.args)
    form, start, end = date_form(start, end)

    paging, today, data_list, summary = report.attend(page=page, name=name, start=start, end=end)
    return render_template('report/attendance.html', **locals())


@bp.route('/summary/', methods=('GET', 'POST'))
@client_ip_check
def summarize():
    report = Report()
    if request.method == 'POST':
        start = request.form['start']
        end = request.form['end']
        data_list = report.summary(page='all', start=start, end=end)
        # https://github.com/Shir0kamii/Flask-CSV
        if data_list:
            encoding = 'utf-8-sig'
            filename = 'summary' + '_' + start + '_' + end + '.csv'
            buf = StringIO()
            writer = ValidatedWriter(buf, fieldnames=data_list[0].keys())
            writer.writeheader()
            for data in data_list:
                writer.writerow(data)
            buf.seek(0)
            buf = BytesIO(buf.read().encode(encoding))
            return send_file(buf, attachment_filename=filename, as_attachment=True, mimetype='text/csv')
    page, _, start, end = request_get(request.args)
    form, start, end = date_form(start, end)

    paging, data_list = report.summary(page=page, start=start, end=end)
    return render_template('report/summary.html', **locals())



