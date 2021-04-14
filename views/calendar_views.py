from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify
from models import get_calendar, get_schedule, get_events, update_event
from werkzeug.utils import redirect

from utils import request_event

# blueprint
bp = Blueprint('calendar', __name__, url_prefix='/calendar')

@bp.route('/', methods=('GET', 'POST'))
def calendar():
    # https://stackoverflow.com/questions/39902405/fullcalendar-in-django
    today, thisMonth = get_calendar()
    events = get_events(start=thisMonth['start'], end=thisMonth['end'])
    return render_template('report/calendar.html', **locals())

@bp.route('/add_event/')
def add_event():
    title, start, end, id = request_event(request.args)
    event = {'title':title, 'start':start, 'end':end, 'id':id}
    update_event(event)
    return jsonify(event)