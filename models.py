from werkzeug.security import check_password_hash
import datetime
from pymongo import MongoClient
import pyodbc
from collections import OrderedDict
import json

from office365.runtime.auth.user_credential import UserCredential
from office365.runtime.http.request_options import RequestOptions
from office365.sharepoint.client_context import ClientContext

from utils import checkTime, checkHoliday, request_event, request_get, Page
from mainconfig import ACCESS_DB_PWD, IS_CALENDAR_CONNECTED, OFFICE365_ACCOUNT
from workingconfig import WORKING

mongoClient = MongoClient('mongodb://localhost:27017/')
db = mongoClient['report']

# connect to access db
# https://stackoverflow.com/questions/50757873/connect-to-ms-access-in-python
# You probably have 32-bit Access (Office) and 64-bit Python. As you know, 32-bit and 64-bit are completely incompatible.
# You need to install 32-bit Python, or upgrade Access (Office) to 64-bit
conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=c:/caps/acserver/access.mdb;PWD=%s' %ACCESS_DB_PWD)
cursor = conn.cursor()


def eventFromSharePoint():
    collection = db['calendar']

    calendar_url = "https://mirageworks.sharepoint.com/sites/msteams_a0f4c8/_api/web/lists(guid'%s')/items" %(OFFICE365_ACCOUNT['guid'])

    ctx = ClientContext(calendar_url).with_credentials(UserCredential(OFFICE365_ACCOUNT['email'], OFFICE365_ACCOUNT['password']))
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
            collection.update_one({'id': event['id']}, {'$set': event}, upsert=True)
        else:
            collection.update_one({'id': event['id']}, {'$set': event}, upsert=True)


def saveDB(today=None):
    if today is None:
        hour, today, _ = checkTime()
    else:
        hour, this_day, _ = checkTime()
        if today != this_day:
            hour = 23
    is_holiday = checkHoliday(today)
    if not is_holiday and hour > 6:
        if IS_CALENDAR_CONNECTED:
            eventFromSharePoint()
        access_day = today[0:4] + today[5:7] + today[8: ] # access_day 형식으로 변환
        cursor.execute("select e_name, e_date, e_time from tenter where e_date = ?", access_day)
        event = Event()
        schedule_dict = event.schedule(date=today)
        employees = event.emloyeees

        attend = {}
        for employee in employees:
            name = employee['name']
            attend[name] = {'date': today, 'name': name, 'begin': None, 'end': None, 'reason': None}

        for row in cursor.fetchall():
            name = row[0]
            date = row[1]
            time = row[2]
            # card 출근자 name = ''
            if name != '':
                if name not in attend:
                    attend[name] = {'date': today, 'name': name, 'begin': None, 'end': None, 'reason': None}
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
            if name in schedule_dict:
                status = schedule_dict[name]
                attend[name]['status'] = (None, 0)
                if status == '월차':
                    status = '연차'
                attend[name]['reason'] = status
                if hour >= 18:
                    attend[name]['workingHours'] = WORKING['status'][status]
                else:
                    attend[name]['workingHours'] = None
            elif attend[name]['begin']:
                if int(attend[name]['begin']) > WORKING['time']['beginTime']:
                    attend[name]['status'] = ('지각', 1)
                else:
                    attend[name]['status'] = ('정상출근', 0)
                if hour >= 18:
                    working_hours = int(attend[name]['end'][0:2]) - int(attend[name]['begin'][0:2]) + \
                                   (int(attend[name]['end'][2:4]) - int(attend[name]['begin'][2:4])) / 60
                    if int(attend[name]['end']) > WORKING['time']['lunchFinishTime'] and \
                            WORKING['time']['lunchTime'] > int(attend[name]['begin']):
                        working_hours = working_hours - 1
                    working_hours = round(working_hours, 1)
                    attend[name]['workingHours'] = working_hours
                else:
                    attend[name]['workingHours'] = None
            else:
                if hour >= 18:
                    attend[name]['status'] = ('미출근', 3)
                    attend[name]['workingHours'] = 0
                elif hour >= WORKING['time']['beginTime'] / 10000:
                    attend[name]['workingHours'] = None
                    attend[name]['status'] = ('지각', 1)
                else:
                    attend[name]['status'] = ('출근전', 2)
                    attend[name]['workingHours'] = None

            collection.update_one({'date': today, 'name': name}, {'$set': attend[name]}, upsert=True)


def get_setting():
    return IS_CALENDAR_CONNECTED, OFFICE365_ACCOUNT, WORKING


def get_sharepoint():
    _, today, thisMonth = checkTime()
    start = thisMonth['start']
    end = thisMonth['end']
    collection = db['calendar']


class User:
    collection = db['user']
    error = None

    # user
    def signup(self, request_data):
        user_data = self.collection.find_one(filter={'email': request_data['email']})
        if user_data:
            self.error = '이미 존재하는 사용자입니다.'
        else:
            user_data = self.collection.find_one(sort=[('create_time', -1)])
            if user_data:
                user_id = user_data['user_id'] + 1
            else:
                user_id = 1
            request_data['create_time'] = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            request_data['user_id'] = user_id
            self.collection.insert(request_data)
        return self.error

    def login(self, request_data):
        user_data = self.collection.find_one(filter={'email': request_data['email']})
        if not user_data:
            self.error = "존재하지 않는 사용자입니다."
        elif not check_password_hash(user_data['password'], request_data['password']):
            self.error = "비밀번호가 올바르지 않습니다."
        return self.error, user_data


class Employee:
    collection = db['employees']

    def get(self, page=1, name=None):
        if name:
            employee = self.collection.find_one({'name': name})
            return employee
        elif page == 'all':
            data_list = []
            employees = self.collection.find(sort=[('name', 1)])
            for employee in employees:
                data_list.append({'name': employee['name']})
            return data_list
        else:
            data_list = self.collection.find(sort=[('department', 1), ('name', 1)])
            get_page = Page(page)
            return get_page.paginate(data_list)

    def post(self, request_data):
        self.collection.update_one({'name': request_data['name']}, {'$set': request_data}, upsert=True)


class Report:
    collection = db['report']

    def attend(self, page=None, name=None, start=None, end=None):
        if page == 'all':
            employee = Employee()
            employee = employee.get(name=name)
            data_list = self.collection.find({'name': name}, sort=[('date', 1)])
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
                attend_list.append(
                    {'name': data['name'], 'rank': employee['rank'], 'department': employee['department'],
                     'date': data['date'], 'begin': begin, 'end': end, 'reason': reason})
            return attend_list
        else:
            _, today, _ = checkTime()
            if start:
                if name:
                    data_list = self.collection.find({'date': {"$gte": start, "$lte": end}, 'name': name},
                                                     sort=[('name', 1), ('date', -1)])
                else:
                    data_list = self.collection.find({'date': {"$gte": start, "$lte": end}},
                                                     sort=[('name', 1), ('date', -1)])
            else:
                if name:
                    data_list = self.collection.find({'date': today, 'name': name}, sort=[('date', -1)])
                else:
                    data_list = self.collection.find({'date': today}, sort=[('name', 1)])

            get_page = Page(page)
            paging, data_list = get_page.paginate(data_list)

            summary = {}
            if name:
                attend_list = []
                summary['totalWorkingHours'] = 0
                summary['totalDay'] = 0
                for status in WORKING['inStatus']:
                    summary[status] = 0
                for status in WORKING['status']:
                    summary[status] = 0
                for data in data_list:
                    if data['workingHours'] is not None:
                        summary['totalDay'] = summary['totalDay'] + 1
                        del data['_id']
                        if 'status' in data:
                            if data['status'][0]:
                                summary[data['status'][0]] = summary[data['status'][0]] + 1
                        if 'reason' in data and data['reason']:
                            summary[data['reason']] = summary[data['reason']] + 1
                        summary['totalWorkingHours'] = summary['totalWorkingHours'] + data['workingHours']
                    attend_list.append(data)
                summary['totalWorkingHours'] = round(summary['totalWorkingHours'], 2)
                return paging, today, attend_list, summary
            else:
                return paging, today, data_list, summary

    def summary(self, page=1, start=None, end=None):

        data_list = None
        summary_list = []
        if start:
            data_list = self.collection.find({'date': {"$gte": start, "$lte": end}}, sort=[('name', 1), ('date', -1)])
        if data_list:
            summary = OrderedDict()
            for data in data_list:
                if data['workingHours'] is not None:
                    name = data['name']
                    if name not in summary:
                        summary[name] = {'name': name}
                    if 'totalWorkingHours' not in summary[name]:
                        summary[name]['totalWorkingHours'] = 0
                    if 'totalDay' not in summary[name]:
                        summary[name]['totalDay'] = 0
                    for status in WORKING['inStatus']:
                        if status not in summary[name]:
                            summary[name][status] = 0
                    for status in WORKING['status']:
                        if status not in summary[name]:
                            summary[name][status] = 0

                    summary[name]['totalDay'] = summary[name]['totalDay'] + 1
                    if 'status' in data:
                        if data['status'][0]:
                            summary[name][data['status'][0]] = summary[name][data['status'][0]] + 1
                    if 'reason' in data and data['reason']:
                        summary[name][data['reason']] = summary[name][data['reason']] + 1
                    summary[name]['totalWorkingHours'] = summary[name]['totalWorkingHours'] + data['workingHours']
            for name in summary:
                summary[name]['totalWorkingHours'] = round(summary[name]['totalWorkingHours'], 2)
                summary_list.append(summary[name])

        get_page = Page(page)
        return get_page.paginate(summary_list)


class Event:
    collection = db['event']
    start = None
    end = None
    employees = []

    def get(self):
        _, today, this_month = checkTime()
        self.start = this_month['start']
        self.end = this_month['end']
        data_list = []
        if self.start is not None and self.end is not None:
            data_list = self.collection.find({'start': {"$gte": self.start, "$lt": self.end}}, sort=[('id', 1)])
        return data_list

    def post(self, args, type='insert'):

        title, self.start, self.end, id = request_event(args)
        request_data = {'title': title, 'start': self.start, 'end': self.end, 'id': id}

        if id is None and type == 'insert':
            data = self.collection.find_one(sort=[('id', -1)])
            if data:
                id = data['id'] + 1
            else:
                id = 1
            request_data['id'] = id
            self.collection.insert_one(request_data)
        elif type == 'update':
            self.collection.update_one({'id': id}, {'$set': request_data})
        elif type == 'delete':
            self.collection.delete_one({'id': request_data['id']})

        # calendar 에 일정이 변경 되면 그에 따라서 report 내용도 update 하기 위함
        if self.start is not None and self.end is not None:
            self.report()

    def report(self):
        collection = db['report']  # report 에는 오늘까지만 기록이 되어 있어 제일 큰 날짜가 오늘이 됨
        data_list = collection.find({'date': {"$gte": self.start, "$lt": self.end}})
        date_list = []
        for data in data_list:
            if data['date'] not in date_list:
                date_list.append(data['date'])
        for date in date_list:
            saveDB(today=date)

    def schedule(self, date=None):
        employee = Employee()
        self.employees = employee.get(page='all')
        schedule_dict = {}
        data_list = self.collection.find({'start': {"$lte": date}, 'end': {"$gt": date}})
        for data in data_list:
            name = None
            status = '기타'
            for employee in self.employees:
                if employee['name'] in data['title']:
                    name = employee['name']
            for type in WORKING['status']:
                if type in data['title']:
                    status = type
            schedule_dict[name] = status
        return schedule_dict


# Device
class Device:
    collection = db['mac']

    def get(self, page=1):
        data_list = self.collection.find()
        if page == 'all':
            return data_list
        else:
            get_page = Page(page)
            return get_page.paginate(data_list)

    def post(self, request_data):
        if 'owner' not in request_data:
            request_data = {'mac': request_data['mac'], 'owner': None, 'device': None}
        self.collection.update_one({'mac': request_data['mac']}, {'$set': request_data}, upsert=True)



