from flask import request, render_template, url_for, g
from werkzeug.utils import redirect
import functools
from datetime import date

from utils import check_private_ip


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


def date_form(form, start='', end=''):
    start = start or date.today().strftime('%Y-%m-%d')
    end = end or date.today().strftime('%Y-%m-%d')

    form.start.data = start
    form.end.data = end
    return form, start, end