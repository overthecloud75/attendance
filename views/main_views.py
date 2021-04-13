from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify
from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect
import functools

from models import post_signUp, post_login, post_employees, get_employees, get_attend, get_summary
from form import UserCreateForm, UserLoginForm, EmployeesSubmitForm, DateSubmitForm
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

@bp.route('/employees/', methods=('GET', 'POST'))
def employees():
    form = EmployeesSubmitForm()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name':form.name.data}
        post_employees(request_data)
    page, keyword, _, _ = request_get(request.args)
    paging, data_list = get_employees(page=page)
    return render_template('user/employees.html', **locals())

@bp.route('/attend/')
def attend():
    # https://gist.github.com/doobeh/3e685ef25fac7d03ded7#file-vort-html-L11
    form = DateSubmitForm()
    page, keyword, startDate, endDate = request_get(request.args)
    paging, today, data_list, summary = get_attend(page=page, startDate=startDate, endDate=endDate)
    return render_template('report/attendance.html', **locals())

@bp.route('/attend/<name>')
def attendByName(name):
    # https://gist.github.com/doobeh/3e685ef25fac7d03ded7#file-vort-html-L11
    form = DateSubmitForm()
    page, keyword, startDate, endDate = request_get(request.args)
    paging, today, data_list, summary = get_attend(page=page, name=name, startDate=startDate, endDate=endDate)
    return render_template('report/attendance.html', **locals())

@bp.route('/summary/')
def summary():
    form = DateSubmitForm()
    page, keyword, startDate, endDate = request_get(request.args)
    paging, data_list = get_summary(page=page, startDate=startDate, endDate=endDate)
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