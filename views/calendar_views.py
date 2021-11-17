from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify
from werkzeug.utils import redirect

from models import Event, get_sharepoint
from mainconfig import OFFICE365_CALENDAR_URL

# blueprint
bp = Blueprint('calendar', __name__, url_prefix='/calendar')


@bp.route('/', methods=('GET', 'POST'))
def calendar():
    # https://stackoverflow.com/questions/39902405/fullcalendar-in-django
    event = Event()
    events = event.get()
    calendar_url = OFFICE365_CALENDAR_URL
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

