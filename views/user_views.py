from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify, send_file, make_response
from io import BytesIO, StringIO
from csvalidate import ValidatedWriter
from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect

from models import User, Employee
from form import UserCreateForm, UserLoginForm, EmailForm, PasswordResetForm, EmployeeSubmitForm, UserUpdateForm
from utils import request_get
from .utils import *
from config import EMPLOYEES_STATUS

# blueprint
bp = Blueprint('user', __name__, url_prefix='/user')


@bp.after_request
def add_security_headers(resp):
    # https://flask.palletsprojects.com/en/2.1.x/security/
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


@bp.route('/signup/', methods=('GET', 'POST'))
def signup():
    form = UserCreateForm()
    if request.method == 'POST' and form.validate_on_submit():
        user = User()
        request_data = {'name': form.name.data, 'email': form.email.data, 'password': generate_password_hash(form.password1.data)}
        error = user.signup(request_data)
        if error:
            flash(error)
            return make_response(render_template('user/signup.html', form=form), 400)
        else:
            return redirect(url_for('user.unconfirmed', _type='email'))
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('user/signup.html', **locals()), 400)
    return render_template('user/signup.html', **locals())


@bp.route('/login/', methods=('GET', 'POST'))
def login():
    form = UserLoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        user = User()
        request_data = {'email': form.email.data, 'password': form.password.data}
        error, user_data = user.login(request_data)
        if error is None and user_data['emailConfirm']:
            del user_data['password']
            user_data['_id'] = str(user_data['_id'])

            session.clear()
            for key in user_data:
                session[key] = user_data[key]
            return redirect(url_for('main.attend'))
        elif error is None and not user_data['emailConfirm']:
            return redirect(url_for('user.unconfirmed', _type='email'))
        else:
            flash(error)
            return make_response(render_template('user/login.html', **locals()), 400)
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('user/login.html', **locals()), 400)
    return render_template('user/login.html', **locals())


@bp.route('/logout/')
@login_required
def logout():
    session.clear()
    return redirect(url_for('main.index'))


@bp.route('/email_confirm/<token>')
def email_confirm(token):
    user = User()
    error, user_data = user.confirm_token(token)
    form = EmailForm()
    button_title = '이메일 다시 보내기'
    if error is None:
        error = user.confirm_email(user_data)
        if error is None:
            del user_data['_id']
            del user_data['password']

            session.clear()
            for key in user_data:
                session[key] = user_data[key]
            return redirect(url_for('main.attend'))
        else:
            flash(error)
            return make_response(render_template('user/email_send.html', **locals()), 400)
    else:
        flash(error)
        return make_response(render_template('user/email_send.html', **locals()), 400)


@bp.route('/unconfirmed/<_type>')
def unconfirmed(_type):
    if _type == 'email':
        return render_template('user/email_unconfirmed.html')
    elif _type == 'password':
        return render_template('user/password_unconfirmed.html')
    else:
        return redirect(url_for('main.attend'))


@bp.route('/resend/', methods=('GET', 'POST'))
def resend():
    form = EmailForm()
    button_title = '이메일 다시 보내기'
    if request.method == 'POST' and form.validate_on_submit():
        email = form.email.data
        user = User()
        error = user.resend({'email': email})
        if error is None:
            return redirect(url_for('user.email_unconfirmed'))
        else:
            flash(error)
            return make_response(render_template('user/email_send.html', **locals()), 400)
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('user/email_send.html', **locals()), 400)
    return render_template('user/email_send.html', **locals())


@bp.route('/reset_password/', methods=('GET', 'POST'))
def reset_password():
    form = EmailForm()
    button_title = 'email 확인하기'
    if request.method == 'POST' and form.validate_on_submit():
        user = User()
        request_data = {'email': form.email.data}
        error = user.reset_password(request_data)
        if error:
            flash(error)
            return make_response(render_template('user/email_send.html', **locals()), 400)
        else:
            return redirect(url_for('user.unconfirmed', _type='password'))
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('user/email_send.html', **locals()), 400)
    return render_template('user/email_send.html', **locals())


@bp.route('/reset_password/<token>', methods=('GET', 'POST'))
def confirm_reset_password(token):
    user = User()
    error, user_data = user.confirm_token(token)
    if error:
        form = EmailForm()
        flash(error)
        return make_response(render_template('user/email_send.html', **locals()), 400)
    else:
        form = PasswordResetForm()
        if request.method == 'POST' and form.validate_on_submit():
            user_data['password'] = generate_password_hash(form.password1.data)
            user.change_password(user_data)
            return redirect(url_for('user.login'))
        elif request.method == 'POST' and not form.validate_on_submit():
            return make_response(render_template('user/confirm_reset_password.html', **locals()), 400)
        return render_template('user/confirm_reset_password.html', **locals())


@bp.route('/employees/', methods=('GET',))
@admin_required
def employees():
    employee = Employee()
    page, _, _, _ = request_get(request.args)
    paging, data_list = employee.get(page=page)
    return render_template('user/employees.html', **locals())


@bp.route('/update_employee/', methods=('GET', 'POST'))
@admin_required
def update_employee():
    form = EmployeeSubmitForm()
    employee = Employee()
    employees_status = EMPLOYEES_STATUS
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name': form.name.data, 'department': form.department.data, 'position': form.position.data,
                        'rank': form.rank.data, 'regular': form.regular.data, 'mode': form.mode.data}
        if form.employeeId.data:
            request_data['employeeId'] = int(form.employeeId.data)
        if form.email.data:
            request_data['email'] = form.email.data
        if form.beginDate.data:
            request_data['beginDate'] = form.beginDate.data.strftime('%Y-%m-%d')
        if form.endDate.data:
            request_data['endDate'] = form.endDate.data.strftime('%Y-%m-%d')
        employee.post(request_data)
        return redirect(url_for('user.employees'))
    _id = request.args.get('_id', '')
    data = employee.get_by_id(_id=_id)
    return render_template('user/update_employee.html', **locals())


@bp.route('/users/', methods=('GET',))
@admin_required
def users():
    user = User()
    page, _, _, _ = request_get(request.args)
    paging, data_list = user.get(page=page)
    return render_template('user/users.html', **locals())


@bp.route('/update_user/', methods=('GET', 'POST'))
@admin_required
def update_user():
    form = UserUpdateForm()
    user = User()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name': form.name.data, 'email': form.email.data, 'isAdmin': form.is_admin.data}
        error = user.post(request_data)
        if error:
            flash(error)
            return make_response(render_template('user/update_user.html', **locals()), 400)
        else:
            return redirect(url_for('user.users'))
    _id = request.args.get('_id', '')
    data = user.get_by_id(_id=_id)
    return render_template('user/update_user.html', **locals())

