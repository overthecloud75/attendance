from flask import Blueprint, request, render_template, url_for, current_app, session, g, flash, jsonify
from werkzeug.utils import redirect

from models import Event, Employee
from form import ApprovalSubmitForm
from config import WORKING
from .utils import *
from config import APPROVAL_REASON


# blueprint
bp = Blueprint('calendar', __name__, url_prefix='/schedule')


@bp.after_request
def add_security_headers(resp):
    # https://flask.palletsprojects.com/en/2.1.x/security/
    resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


@bp.route('/', methods=('GET', 'POST'))
@client_ip_check
def calendar():
    # https://stackoverflow.com/questions/39902405/fullcalendar-in-django
    # open link in new tab
    # https://www.freecodecamp.org/news/how-to-use-html-to-open-link-in-new-tab/
    # To open a link in a new tab, just set the target attribute to _blank:
    return render_template('report/calendar.html', **locals())


@bp.route('/approval', methods=('GET', 'POST'))
@login_required
@client_ip_check
def approval():
    form = ApprovalSubmitForm()
    form, start, end = date_form(form)
    approval_reason = APPROVAL_REASON
    employees = Employee()
    approver = employees.get_approver(email=g.user['email'])
    return render_template('report/approval.html', **locals())


@bp.route('/get_event/')
@client_ip_check
def get_event():
    event = Event()
    events = event.get(request.args)
    event_list = []
    for event in events:
        del event['_id']
        title = event['title'].split('/')
        if len(title) == 1:
            title = title[0].split(' ')
        if len(title) > 1:
            event_title = title[1]
            for status in WORKING['status']:
                if status in title[1]:
                    event_title = status
            if event_title in WORKING['offDay']:
                event['color'] = 'yellow'
                event['textColor'] = 'black'
            elif event_title not in WORKING['status']:
                event['color'] = 'green'
        else:
            event['color'] = 'red'
        event_list.append(event)
    return jsonify(event_list)


@bp.route('/add_event/')
@client_ip_check
def add_event():
    event = Event()
    event.insert(request.args)
    return jsonify({})


@bp.route('/drop_event/')
@client_ip_check
def drop():
    event = Event()
    event.drop(request.args)
    return jsonify({})


@bp.route('/delete_event/')
@client_ip_check
def delete():
    event = Event()
    event.delete(request.args)
    return jsonify({})


