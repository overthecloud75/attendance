from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify, send_file, make_response
from io import BytesIO, StringIO
from csvalidate import ValidatedWriter
from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect
import functools

from models import get_setting, User, Employee, Report, Device
from form import UserCreateForm, UserLoginForm, EmployeeSubmitForm, PeriodSubmitForm, DateSubmitForm, DeviceSubmitForm
from utils import request_get, check_private_ip

# blueprint
bp = Blueprint('main', __name__, url_prefix='/')


@bp.after_request
def add_security_headers(resp):
    # https://flask.palletsprojects.com/en/2.1.x/security/
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('main.login'))
        elif not g.user['is_admin']:
            return redirect(url_for('main.attend'))
        return view(**kwargs)
    return wrapped_view


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('main.login'))
        return view(**kwargs)
    return wrapped_view


def client_ip_check(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'X-Forwarded-For' in request.headers and g.user is None:
            if not check_private_ip(request.headers['X-Forwarded-For']):
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
            flash(error)
            return make_response(render_template('user/signup.html', form=form), 400)
        else:
            return redirect(url_for('main.attend'))
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('user/signup.html', form=form), 400)
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
        else:
            flash(error)
            return make_response(render_template('user/login.html', form=form), 400)
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('user/login.html', form=form), 400)
    return render_template('user/login.html', form=form)


@bp.route('/logout/')
@login_required
def logout():
    session.clear()
    return redirect(url_for('main.index'))


@bp.route('/setting/', methods=('GET', 'POST'))
@admin_required
def setting():
    use_wifi_attendance, use_notice_email, is_outside_calendar_connected, outside_calendar_url, account, cc, working = get_setting()
    return render_template('user/setting.html', **locals())


@bp.route('/employees/', methods=('GET',))
@admin_required
def employees():
    employee = Employee()
    page, name, _, _ = request_get(request.args)
    paging, data_list = employee.get(page=page)
    return render_template('user/employees.html', **locals())


@bp.route('/update_employee/', methods=('GET', 'POST'))
@admin_required
def update_employee():
    form = EmployeeSubmitForm()
    employee = Employee()
    _, name, _, _ = request_get(request.args)
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name': form.name.data, 'department': form.department.data, 'rank': form.rank.data}
        if form.employeeId.data:
            request_data['employeeId'] = int(form.employeeId.data)
        if form.beginDate.data:
            request_data['beginDate'] = form.beginDate.data
        if form.endDate.data:
            request_data['endDate'] = form.endDate.data
        if form.email.data:
            request_data['email'] = form.email.data
        if form.regular.data:
            request_data['regular'] = form.regular.data
        if form.status.data:
            request_data['status'] = form.status.data
        employee.post(request_data)
        return redirect(url_for('main.employees'))
    data = employee.get(name=name)
    return render_template('user/update_employee.html', **locals())


@bp.route('/device/', methods=('GET', 'POST'))
@admin_required
def get_device():
    form = DeviceSubmitForm()
    device = Device()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'mac': form.mac.data, 'registerTime': form.registerTime.data, 'owner': form.owner.data, 'device': form.device.data}
        device.post(request_data)
    page, _, _, _ = request_get(request.args)
    paging, data_list = device.get(page=page)
    return render_template('user/device.html', **locals())


@bp.route('/wifi_attend/', methods=('GET', ))
@admin_required
def wifi_attend():
    report = Report()
    form = DateSubmitForm()
    page, _, start, _ = request_get(request.args)
    paging, data_list = report.wifi_attend(page=page, date=start)
    return render_template('user/wifi_attend.html', **locals())


@bp.route('/attend/', methods=('GET', 'POST'))
@client_ip_check
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
    form = PeriodSubmitForm()
    page, name, start, end = request_get(request.args)
    paging, today, data_list, summary = report.attend(page=page, name=name, start=start, end=end)
    return render_template('report/attendance.html', **locals())


@bp.route('/summary/', methods=('GET', 'POST'))
@client_ip_check
def summarize():
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
    form = PeriodSubmitForm()
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