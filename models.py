from werkzeug.security import check_password_hash
import datetime
from pymongo import MongoClient
import pyodbc
from collections import OrderedDict
import json

from office365.runtime.auth.user_credential import UserCredential
from office365.runtime.http.request_options import RequestOptions
from office365.sharepoint.client_context import ClientContext

from views.config import page_default
from utils import paginate, checkTime, checkHoliday
from mainconfig import accessDBPwd, calendar_url, office365_account, workTime, workStatus, workInStatus

mongoClient = MongoClient('mongodb://localhost:27017/')
db = mongoClient['report']

# connect to access db
# https://stackoverflow.com/questions/50757873/connect-to-ms-access-in-python
# You probably have 32-bit Access (Office) and 64-bit Python. As you know, 32-bit and 64-bit are completely incompatible.
# You need to install 32-bit Python, or upgrade Access (Office) to 64-bit
conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=c:/caps/acserver/access.mdb;PWD=%s' %accessDBPwd)
cursor = conn.cursor()

# db
def get_schedule(date=None):
    collection = db['event']
    employees = get_employee(page='all')
    scheduleDict = {}
    data_list = collection.find({'start':{"$lte":date}, 'end':{"$gt":date}})
    for data in data_list:
        name = None
        status = None
        for employee in employees:
            if employee['name'] in data['title']:
                name = employee['name']
        for type in workStatus:
            if type in data['title']:
                status = type
        scheduleDict[name] = status
    return scheduleDict

def eventFromSharePoint():
    collection = db['callendar']

    ctx = ClientContext(calendar_url).with_credentials(UserCredential(office365_account['email'], office365_account['password']))
    request = RequestOptions(calendar_url)
    response = ctx.execute_request_direct(request)
    json_data = json.loads(response.content)

    for i, data in enumerate(json_data['d']['results']):
        event = {}
        event['title'] = data['Title']
        event['start'] = data['EventDate']
        event['end'] = data['EndDate']
        event['id'] = data['ID']
        event['allday'] = data['fAllDayEvent']
        event['every'] = data['fRecurrence']
        if data['fRecurrence']:
            collection.update_one({'id':event['id']}, {'$set':event}, upsert=True)
        else:
            collection.update_one({'id':event['id']}, {'$set':event}, upsert=True)

def saveDB():
    hour, today, _ = checkTime()
    isHoliday = checkHoliday(today)
    if not isHoliday and hour > 6:
        eventFromSharePoint()
        accessDay = today[0:4] + today[5:7] + today[8:] # accessDay 형식으로 변환
        cursor.execute("select e_name, e_date, e_time from tenter where e_date = ?", accessDay)
        scheduleDict = get_schedule(date=today)

        attend = {}
        employees = get_employee(page='all')
        for employee in employees:
            name = employee['name']
            attend[name] = {'date':today, 'name':name, 'begin':None, 'end':None}

        for row in cursor.fetchall():
            name = row[0]
            date = row[1]
            time = row[2]
            if name not in attend:
                attend[name] = {'date':today, 'name':name, 'begin':None, 'end':None}
            if attend[name]['begin']:
                if int(time) < int(attend[name]['begin']):
                    attend[name]['begin'] = time
                if hour >= 18:
                    attend[name]['end'] = time
            else:
                attend[name]['begin'] = time
                if hour >= 18:
                    attend[name]['end'] = time
                else:
                    attend[name]['end'] = None

        collection = db['report']
        for name in attend:
            if name in scheduleDict:
                status = scheduleDict[name]
                attend[name]['status'] = (None, 0)
                attend[name]['reason'] = status
                if hour >= 18:
                    attend[name]['workingHours'] = workStatus[status]
                else:
                    attend[name]['workingHours'] = None
            elif attend[name]['begin']:
                if int(attend[name]['begin']) > workTime['beginTime']:
                    attend[name]['status'] = ('지각', 1)
                else:
                    attend[name]['status'] = ('정상출근', 0)
                if hour >= 18:
                    workingHours = round(int(attend[name]['end'][0:2]) - int(attend[name]['begin'][0:2]) +
                                         (int(attend[name]['end'][2:4]) - int(attend[name]['begin'][2:4])) / 60, 1)
                    if int(attend[name]['end']) > workTime['lunchFinishTime'] and \
                            workTime['lunchTime'] > int(attend[name]['begin']):
                        workingHours = workingHours - 1
                    attend[name]['workingHours'] = workingHours
                else:
                    attend[name]['workingHours'] = None
            else:
                if hour >= 18:
                    attend[name]['status'] = ('미출근', 3)
                    attend[name]['workingHours'] = 0
                elif hour >= workTime['beginTime'] / 10000:
                    attend[name]['workingHours'] = None
                    attend[name]['status'] = ('지각', 1)
                else:
                    attend[name]['status'] = ('출근전', 2)
                    attend[name]['workingHours'] = None

            collection.update_one({'date':today, 'name':name}, {'$set':attend[name]}, upsert=True)

# user
def post_signUp(request_data):
    collection = db['user']
    user_data = collection.find_one(filter={'email': request_data['email']})
    error = None
    if user_data:
        error = '이미 존재하는 사용자입니다.'
    else:
        user_data = collection.find_one(sort=[('create_time', -1)])
        if user_data:
            user_id = user_data['user_id'] + 1
        else:
            user_id = 1
        request_data['create_time'] = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        request_data['user_id'] = user_id
        collection.insert(request_data)
    return error

def post_login(request_data):
    collection = db['user']
    error = None
    user_data = collection.find_one(filter={'email':request_data['email']})
    if not user_data:
        error = "존재하지 않는 사용자입니다."
    elif not check_password_hash(user_data['password'], request_data['password']):
        error = "비밀번호가 올바르지 않습니다."
    return error, user_data

def post_employee(request_data):
    collection = db['employees']
    collection.update_one({'name':request_data['name']}, {'$set':request_data}, upsert=True)

def get_employee(page=1, name=None):
    collection = db['employees']
    if name:
        employee = collection.find_one({'name':name})
        return employee
    elif page == 'all':
        data_list = []
        employees = collection.find(sort=[('name', 1)])
        for employee in employees:
            data_list.append({'name':employee['name']})
        return data_list
    else:
        per_page = page_default['per_page']
        offset = (page - 1) * per_page
        data_list = collection.find(sort=[('department', 1), ('name', 1)]).limit(per_page).skip(offset)
        count = data_list.count()
        paging = paginate(page, per_page, count)
        return paging, data_list

# report
def get_attend(page=1, name=None, start=None, end=None):
    collection = db['report']
    if page == 'all':
        employee = get_employee(name=name)
        data_list = collection.find({'name':name}, sort=[('date', 1)])
        attend_list = []
        for data in data_list:

            if data['begin']:
                begin = data['begin'][0:2] + ':' + data['begin'][2:4]
            else:
                begin = ''
            if data['end']:
                end = data['end'][0:2] + ':' + data['end'][2:4]
            else:
                end = ''
            if 'reason' in data:
                reason = data['reason']
            else:
                reason = ''
            attend_list.append({'name':data['name'], 'rank':employee['rank'], 'department':employee['department'],
                                'date':data['date'], 'begin':begin, 'end':end, 'reason':reason})
        return attend_list
    else:
        per_page = page_default['per_page']
        offset = (page - 1) * per_page
        _, today, _ = checkTime()
        if start:
            if name:
                data_list = collection.find({'date':{"$gte":start, "$lte":end}, 'name':name}, sort=[('name', 1), ('date', -1)])
            else:
                data_list = collection.find({'date':{"$gte":start, "$lte":end}}, sort=[('name', 1), ('date', -1)])
        else:
            if name:
                data_list = collection.find({'date':today, 'name':name}, sort=[('date', -1)])
            else:
                data_list = collection.find({'date':today}, sort=[('name', 1)])
        count = data_list.count()
        data_list = data_list.limit(per_page).skip(offset)
        paging = paginate(page, per_page, count)
        summary = {}
        if name:
            attend_list = []
            summary = {}
            summary['totalWorkingHours'] = 0
            summary['totalDay'] = 0
            for status in workInStatus:
                summary[status] = 0
            for status in workStatus:
                summary[status] = 0
            for data in data_list:
                if data['workingHours'] is not None:
                    summary['totalDay'] = summary['totalDay'] + 1
                    del data['_id']
                    if 'status' in data:
                        if data['status'][0]:
                            summary[data['status'][0]] = summary[data['status'][0]] + 1
                    if 'reason' in data:
                        summary[data['reason']] = summary[data['reason']] + 1
                    summary['totalWorkingHours'] = summary['totalWorkingHours'] + data['workingHours']
                attend_list.append(data)
            summary['totalWorkingHours'] = round(summary['totalWorkingHours'], 2)
            return paging, today, attend_list, summary
        else:
            return paging, today, data_list, summary

def get_summary(page=1, start=None, end=None):
    per_page = page_default['per_page']
    offset = (page - 1) * per_page
    _, today, _ = checkTime()
    collection = db['report']
    data_list = None
    summary_list = []
    if start:
        data_list = collection.find({'date':{"$gte":start, "$lte":end}}, sort=[('name', 1), ('date', -1)])
    if data_list:
        summary = OrderedDict()
        for data in data_list:
            if data['workingHours'] is not None:
                name = data['name']
                if name not in summary:
                    summary[name] = {'name':name}
                if 'totalWorkingHours' not in summary[name]:
                    summary[name]['totalWorkingHours'] = 0
                if 'totalDay' not in summary[name]:
                    summary[name]['totalDay'] = 0
                for status in workInStatus:
                    if status not in summary[name]:
                        summary[name][status] = 0
                for status in workStatus:
                    if status not in summary[name]:
                        summary[name][status] = 0

                summary[name]['totalDay'] = summary[name]['totalDay'] + 1
                if 'status' in data:
                    if data['status'][0]:
                        summary[name][data['status'][0]] = summary[name][data['status'][0]] + 1
                if 'reason' in data:
                    summary[name][data['reason']] = summary[name][data['reason']] + 1
                summary[name]['totalWorkingHours'] = summary[name]['totalWorkingHours'] + data['workingHours']
        for name in summary:
            summary[name]['totalWorkingHours'] = round(summary[name]['totalWorkingHours'], 2)
            summary_list.append(summary[name])
        count = len(summary_list)
        paging = paginate(page, per_page, count)

        summary_list = summary_list[offset:offset + per_page]
        return paging, summary_list
    else:
        count = len(summary_list)
        paging = paginate(page, per_page, count)
        return paging, summary_list

def get_events(start=None, end=None):
    collection = db['event']
    data_list = []
    if start is not None and end is not None:
        data_list = collection.find({'start':{"$gte":start, "$lt":end}}, sort=[('id', 1)])
    return data_list

def update_event(request_data, type='insert'):
    collection = db['event']
    if request_data['id'] is None and type == 'insert':
        data = collection.find_one(sort=[('id', -1)])
        if data:
            id = data['id'] + 1
        else:
            id = 1
        request_data['id'] = id
        collection.insert_one(request_data)
    elif type == 'update':
        collection.update_one({'id':request_data['id']}, {'$set':request_data})
    elif type == 'delete':
        collection.delete_one({'id':request_data['id']})

def get_sharepoint(start=None, end=None):
    collection = db['callendar']

# calendar
def get_calendar():
    _, today, thisMonth = checkTime()
    return today, thisMonth

