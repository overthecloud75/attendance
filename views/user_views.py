from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify, send_file, make_response
from io import BytesIO, StringIO
from csvalidate import ValidatedWriter
from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect
import functools

from models import User
from form import UserCreateForm, UserLoginForm, EmailForm, PasswordResetForm
from utils import request_get, check_private_ip

# blueprint
bp = Blueprint('user', __name__, url_prefix='/user')


@bp.before_app_request
def load_logged_in_user():
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


def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('user.login'))
        elif not g.user['is_admin']:
            return redirect(url_for('main.attend'))
        return view(**kwargs)
    return wrapped_view


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('user.login'))
        return view(**kwargs)
    return wrapped_view


def client_ip_check(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'X-Forwarded-For' in request.headers and g.user is None:
            if not check_private_ip(request.headers['X-Forwarded-For']):
                return redirect(url_for('user.login'))
        return view(**kwargs)
    return wrapped_view


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
            return redirect(url_for('user.email_unconfirmed'))
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('user/signup.html', form=form), 400)
    return render_template('user/signup.html', form=form)


@bp.route('/login/', methods=('GET', 'POST'))
def login():
    form = UserLoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        user = User()
        request_data = {'email': form.email.data, 'password': form.password.data}
        error, user_data = user.login(request_data)
        if error is None and user_data['email_confirmed']:
            del user_data['_id']
            del user_data['password']

            session.clear()
            for key in user_data:
                session[key] = user_data[key]
            return redirect(url_for('main.attend'))
        elif error is None and not user_data['email_confirmed']:
            return redirect(url_for('user.email_unconfirmed'))
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


@bp.route('/email_confirm/<token>')
def email_confirm(token):
    user = User()
    error, user_data = user.confirm_token(token)
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
            return make_response(render_template('user/email_unconfirmed.html'), 400)
    else:
        flash(error)
        return make_response(render_template('user/email_unconfirmed.html'), 400)


@bp.route('/email_unconfirmed/')
def email_unconfirmed():
    return render_template('user/email_unconfirmed.html')


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
            return make_response(render_template('user/email_send.html', **locals(), form=form), 400)
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('user/resend.html', form=form), 400)
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
            return redirect(url_for('user.password_unconfirmed'))
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
            return make_response(render_template('user/confirm_reset_password.html', form=form), 400)
        return render_template('user/confirm_reset_password.html', form=form)


@bp.route('/password_unconfirmed/')
def password_unconfirmed():
    return render_template('user/password_unconfirmed.html')

