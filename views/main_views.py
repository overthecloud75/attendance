from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify, send_file
from io import BytesIO, StringIO
from csvalidate import ValidatedWriter
from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect
import functools

from models import get_setting, User, Employee, Report, Device
from form import UserCreateForm, UserLoginForm, EmployeeSubmitForm, DateSubmitForm, DeviceSubmitForm
from utils import request_get

# blueprint
bp = Blueprint('main', __name__, url_prefix='/')


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('main.login'))
        return view(**kwargs)
    return wrapped_view


@bp.route('/')
def index():
    return redirect(url_for('main.attend'))


@bp.route('/signup/', methods=('GET', 'POST'))
def signup():
    form = UserCreateForm()
    user = User()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name': form.name.data, 'email': form.email.data, 'password': generate_password_hash(form.password1.data)}
        error = user.signup(request_data)
        if error:
            flash('이미 존재하는 사용자입니다.')
        else:
            return redirect(url_for('main.attend'))
    return render_template('user/signup.html', form=form)


@bp.route('/login/', methods=('GET', 'POST'))
def login():
    form = UserLoginForm()
    user = User()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'email': form.email.data, 'password': form.password.data}
        error, user_data = user.login(request_data)
        if error is None:
            del user_data['_id']
            del user_data['password']

            session.clear()
            for key in user_data:
                session[key] = user_data[key]
            return redirect(url_for('main.attend'))
        flash(error)
    return render_template('user/login.html', form=form)


@bp.route('/logout/')
@login_required
def logout():
    session.clear()
    return redirect(url_for('main.index'))


@bp.route('/setting/', methods=('GET', 'POST'))
@login_required
def setting():
    isCalendarConnected, office365_account, working = get_setting()
    return render_template('user/setting.html', **locals())


@bp.route('/employees/', methods=('GET',))
@login_required
def employees():
    employee = Employee()
    page, name, _, _ = request_get(request.args)
    paging, data_list = employee.get(page=page)
    return render_template('user/employees.html', **locals())


@bp.route('/update_employee/', methods=('GET', 'POST'))
@login_required
def update_employee():
    form = EmployeeSubmitForm()
    employee = Employee()
    _, name, _, _ = request_get(request.args)
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name': form.name.data, 'department': form.department.data, 'rank': form.rank.data, 'employeeId': int(form.employeeId.data)}
        employee.post(request_data)
        return redirect(url_for('main.employees'))
    data = employee.get(name=name)
    return render_template('user/update_employee.html', **locals())


@bp.route('/device/', methods=('GET', 'POST'))
@login_required
def get_device():
    form = DeviceSubmitForm()
    device = Device()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'mac': form.mac.data, 'owner': form.owner.data, 'device': form.device.data}
        device.post(request_data)
    page, _, _, _ = request_get(request.args)
    paging, data_list = device.get(page=page)
    return render_template('user/device.html', **locals())


@bp.route('/wifi_attend/', methods=('GET', ))
@login_required
def wifi_attend():
    report = Report()
    page, _, _, _ = request_get(request.args)
    paging, data_list = report.wifi_attend(page=page)
    return render_template('user/wifi_attend.html', **locals())


@bp.route('/attend/', methods=('GET', 'POST'))
def attend():
    report = Report()
    if request.method == 'POST':
        start = request.form['start']
        end = request.form['end']
        name = request.form['name']
        data_list = report.attend(page='all', name=name, start=start, end=end)
        if data_list:
            encoding = 'utf-8-sig'
            filename = start + '_' + end + '.csv'
            buf = StringIO()
            writer = ValidatedWriter(buf, fieldnames=data_list[0].keys())
            writer.writeheader()
            for data in data_list:
                writer.writerow(data)
            buf.seek(0)
            buf = BytesIO(buf.read().encode(encoding))
            return send_file(buf, attachment_filename=filename, as_attachment=True, mimetype='text/csv')
    # https://gist.github.com/doobeh/3e685ef25fac7d03ded7#file-vort-html-L11
    form = DateSubmitForm()
    page, name, start, end = request_get(request.args)
    paging, today, data_list, summary = report.attend(page=page, name=name, start=start, end=end)
    return render_template('report/attendance.html', **locals())


@bp.route('/summary/', methods=('GET', 'POST'))
def summary():
    report = Report()
    if request.method == 'POST':
        start = request.form['start']
        end = request.form['end']
        paging, data_list = report.summary(start=start, end=end)
        # https://github.com/Shir0kamii/Flask-CSV
        if data_list:
            encoding = 'utf-8-sig'
            filename = start + '_' + end + '.csv'
            buf = StringIO()
            writer = ValidatedWriter(buf, fieldnames=data_list[0].keys())
            writer.writeheader()
            for data in data_list:
                writer.writerow(data)
            buf.seek(0)
            buf = BytesIO(buf.read().encode(encoding))
            return send_file(buf, attachment_filename=filename, as_attachment=True, mimetype='text/csv')
    form = DateSubmitForm()
    page, _, start, end = request_get(request.args)
    paging, data_list = report.summary(page=page, start=start, end=end)
    return render_template('report/summary.html', **locals())


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = {}
        for key in session:
            g.user[key] = session[key]