from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify, send_file
from io import BytesIO, StringIO
from csvalidate import ValidatedWriter
from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect
import functools

from models import post_signUp, post_login, get_setting, post_employee, get_employee, get_attend, get_summary
from form import UserCreateForm, UserLoginForm, EmployeesSubmitForm, EmployeeSubmitForm, DateSubmitForm
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
    return render_template('base.html')

@bp.route('/signup/', methods=('GET', 'POST'))
def signup():
    form = UserCreateForm()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name':form.name.data, 'email':form.email.data, 'password':generate_password_hash(form.password1.data)}
        error = post_signUp(request_data)
        if error:
            flash('이미 존재하는 사용자입니다.')
        else:
            return redirect(url_for('main.index'))
    return render_template('user/signup.html', form=form)

@bp.route('/login/', methods=('GET', 'POST'))
def login():
    form = UserLoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'email':form.email.data, 'password':form.password.data}
        error, user_data = post_login(request_data)
        if error is None:
            del user_data['_id']
            del user_data['password']

            session.clear()
            for key in user_data:
                session[key] = user_data[key]
            return redirect(url_for('main.index'))
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


@bp.route('/employees/', methods=('GET', 'POST'))
@login_required
def employees():
    form = EmployeesSubmitForm()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name':form.name.data}
        post_employee(request_data)
    page, name, _, _ = request_get(request.args)
    paging, data_list = get_employee(page=page)
    return render_template('user/employees.html', **locals())

@bp.route('/updateEmployee/', methods=('GET', 'POST'))
@login_required
def updateEmployee():
    form = EmployeeSubmitForm()
    _, name, _, _ = request_get(request.args)
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name':form.name.data, 'department':form.department.data, 'rank':form.rank.data, 'employeeId':int(form.employeeId.data)}
        post_employee(request_data)
        return redirect(url_for('main.employees'))
    data = get_employee(name=name)
    return render_template('user/update_employee.html', **locals())

@bp.route('/attend/', methods=('GET', 'POST'))
def attend():
    if request.method == 'POST':
        start = request.form['start']
        end = request.form['end']
        name = request.form['name']
        data_list = get_attend(page='all', name=name, start=start, end=end)
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
    paging, today, data_list, summary = get_attend(page=page, name=name, start=start, end=end)
    return render_template('report/attendance.html', **locals())

@bp.route('/summary/', methods=('GET', 'POST'))
def summary():
    if request.method == 'POST':
        start = request.form['start']
        end = request.form['end']
        paging, data_list = get_summary(start=start, end=end)
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
    paging, data_list = get_summary(page=page, start=start, end=end)
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