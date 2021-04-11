from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify
from models import get_calendar, get_schedule

# blueprint
bp = Blueprint('calendar', __name__, url_prefix='/calendar')

@bp.route('/')
def calendar():
    today = get_calendar()
    return render_template('report/calendar.html', **locals())

@bp.route('/data/')
def calendarData():
    startDate = request.args.get('start', '')
    endDate = request.args.get('end', '')

    schedule = get_schedule(startDate=startDate, endDate=endDate)
    return jsonify(schedule)