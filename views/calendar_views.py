from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify
from werkzeug.utils import redirect
import functools

from models import Event, get_sharepoint
try:
    from mainconfig import OUTSIDE_CALENDAR_URL
except Exception as e:
    OUTSIDE_CALENDAR_URL = None
from workingconfig import IS_OUTSIDE_CALENDAR_CONNECTED
from utils import check_private_ip

# blueprint
bp = Blueprint('calendar', __name__, url_prefix='/calendar')


def client_ip_check(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'X-Forwarded-For' in request.headers and g.user is None:
            if not check_private_ip(request.headers['X-Forwarded-For']):
                return redirect(url_for('main.login'))
        return view(**kwargs)
    return wrapped_view


@bp.route('/', methods=('GET', 'POST'))
@client_ip_check
def calendar():
    # https://stackoverflow.com/questions/39902405/fullcalendar-in-django
    event = Event()
    events = event.get()
    is_outside_calendar_connected = IS_OUTSIDE_CALENDAR_CONNECTED
    outside_calendar_url = OUTSIDE_CALENDAR_URL
    # open link in new tab
    # https://www.freecodecamp.org/news/how-to-use-html-to-open-link-in-new-tab/
    # To open a link in a new tab, just set the target attribute to _blank:
    return render_template('report/calendar.html', **locals())


@bp.route('/add_event/')
def add_event():
    event = Event()
    event.post(request.args, type='insert')
    return jsonify({})


@bp.route('/update_event/')
def update():
    event = Event()
    event.post(request.args, type='update')
    return jsonify({})


@bp.route('/delete_event/')
def delete():
    event = Event()
    event.post(request.args, type='delete')
    return jsonify({})


@bp.route('/sharepoint/')
def sharepoint():
    events = get_sharepoint()
    return render_template('report/sharepoint.html', **locals())

