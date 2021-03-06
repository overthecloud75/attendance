from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify, send_file, make_response
from io import BytesIO, StringIO
from csvalidate import ValidatedWriter
from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect

from models import get_setting, User, Employee, Report, Device, Board
from form import WriteSubmitForm
from utils import request_get
from .utils import *


# blueprint
bp = Blueprint('board', __name__, url_prefix='/board')


@bp.after_request
def add_security_headers(resp):
    # https://flask.palletsprojects.com/en/2.1.x/security/
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp

@bp.route('/')
@client_ip_check
def get_board():
    board = Board()
    page, _, start, end = request_get(request.args)
    paging, data_list = board.get(page=page)
    return render_template('report/board.html', **locals())


@bp.route('/content')
@client_ip_check
def get_content():
    board = Board()
    _id = request.args.get('_id', '')
    data = board.get_by_id(_id=_id)
    return render_template('report/get_content.html', data=data)


@bp.route('/write', methods=('GET', 'POST'))
@client_ip_check
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