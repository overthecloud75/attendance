from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify
from werkzeug.utils import redirect

from models import Event, get_sharepoint
try:
    from mainconfig import OUTSIDE_CALENDAR_URL
except Exception as e:
    OUTSIDE_CALENDAR_URL = None
from workingconfig import IS_OUTSIDE_CALENDAR_CONNECTED

# blueprint
bp = Blueprint('calendar', __name__, url_prefix='/calendar')


@bp.route('/', methods=('GET', 'POST'))
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

