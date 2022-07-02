from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify, send_file, make_response
from io import BytesIO, StringIO
from csvalidate import ValidatedWriter
from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect
import functools

from models import get_setting, User, Employee, Report, Device, Board
from form import WriteSubmitForm
from utils import request_get

# blueprint
bp = Blueprint('board', __name__, url_prefix='/board')


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


@bp.route('/')
def get_board():
    board = Board()
    page, _, start, end = request_get(request.args)
    paging, data_list = board.get(page=page)
    return render_template('report/board.html', **locals())


@bp.route('/content')
def get_content():
    board = Board()
    create_time = request.args.get('create_time', None)
    data = board.get_content(create_time=create_time)
    return render_template('report/get_content.html', data=data)


@bp.route('/write', methods=('GET', 'POST'))
def write():
    form = WriteSubmitForm()
    board = Board()
    if request.method == 'POST' and form.validate_on_submit():
        request_data = {'name': form.name.data, 'title': form.title.data, 'content': form.content.data}
        board.post(request_data)
        return redirect(url_for('board.get_board'))
    elif request.method == 'POST' and not form.validate_on_submit():
        return make_response(render_template('report/write.html', form=form), 400)
    return render_template('report/write.html', **locals())