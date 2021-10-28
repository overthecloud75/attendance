from werkzeug.security import check_password_hash
import datetime
from pymongo import MongoClient
import pyodbc
from collections import OrderedDict
import json

from office365.runtime.auth.user_credential import UserCredential
from office365.runtime.http.request_options import RequestOptions
from office365.sharepoint.client_context import ClientContext

from utils import check_time, check_holiday, request_event, request_get, Page
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


def get_setting():
    return IS_CALENDAR_CONNECTED, OFFICE365_ACCOUNT, WORKING


def get_sharepoint():
    _, today, this_month = check_time()
    start = this_month['start']
    end = this_month['end']
    collection = db['calendar']


class User:
    collection = db['user']
    error = None

    def get_user(self, request_data):
        return self.collection.find_one(filter={'email': request_data['email']})

    def signup(self, request_data):
        user_data = self.get_user(request_data)
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
        user_data = self.get_user(request_data)
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


# Device
class Device:
    collection = db['device']

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
        elif request_data['owner'] == 'None':
            request_data['owner'] = None
        self.collection.update_one({'mac': request_data['mac']}, {'$set': request_data}, upsert=True)


class Mac:
    collection = db['mac']

    def get(self, mac_list, date):
        begin = None
        end = None
        # if users have devices
        for mac in mac_list:
            data = self.collection.find_one({'date': date, 'mac': mac}, sort=[('time', 1)])
            if data:
                if begin and int(begin) > int(data['time']):
                    begin = data['time']
                elif not begin:
                    begin = data['time']
            data = self.collection.find_one({'date': date, 'mac': mac}, sort=[('time', -1)])
            if data:
                if end and int(end) < int(data['time']):
                    end = data['time']
                elif not end:
                    end = data['time']
        return begin, end

    def post(self, request_data):
        self.collection.insert_one(request_data)


class Report:
    collection = db['report']
    employee = Employee()
    mac = Mac()

    def __init__(self):
        self.hour, self.today, self.this_month = check_time()

    def attend(self, page=None, name=None, start=None, end=None):
        if page == 'all':
            employee = self.employee.get(name=name)
            if start:
                data_list = self.collection.find({'date': {"$gte": start, "$lte": end}, 'name': name},
                                                 sort=[('name', 1), ('date', 1)])
            else:
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
            if start:
                if name:
                    data_list = self.collection.find({'date': {"$gte": start, "$lte": end}, 'name': name},
                                                     sort=[('name', 1), ('date', -1)])
                else:
                    data_list = self.collection.find({'date': {"$gte": start, "$lte": end}},
                                                     sort=[('name', 1), ('date', -1)])
            else:
                if name:
                    data_list = self.collection.find({'date': self.today, 'name': name}, sort=[('date', -1)])
                else:
                    data_list = self.collection.find({'date': self.today}, sort=[('name', 1)])

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
                return paging, self.today, attend_list, summary
            else:
                return paging, self.today, data_list, summary

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

    def update(self, date=None):
        if date is not None:
            if date != self.today:
                self.hour = 23
            self.today = date
        is_holiday = check_holiday(self.today)

        if self.hour > 6:
            if IS_CALENDAR_CONNECTED:
                eventFromSharePoint()

            # attend 초기화
            attend = {}
            schedule_dict = {}
            if not is_holiday:
                employees = self.employee.get(page='all')
                event = Event()
                schedule_dict = event.schedule(employees, date=self.today)
                for employee in employees:
                    name = employee['name']
                    attend[name] = {'date': self.today, 'name': name, 'begin': None, 'end': None, 'reason': None}

            # 지문 인식 출퇴근 기록
            access_day = self.today[0:4] + self.today[5:7] + self.today[8:]  # access_day 형식으로 변환
            cursor.execute("select e_name, e_date, e_time from tenter where e_date = ?", access_day)

            for row in cursor.fetchall():
                name = row[0]
                date = row[1]
                time = row[2]
                # card 출근자 name = ''
                if name != '':
                    if name not in attend:
                        attend[name] = {'date': self.today, 'name': name, 'begin': None, 'end': None, 'reason': None}
                    if attend[name]['begin']:
                        if int(time) < int(attend[name]['begin']):
                            attend[name]['begin'] = time
                        if self.hour >= 18:
                            attend[name]['end'] = time
                    else:
                        attend[name]['begin'] = time
                        if self.hour >= 18:
                            attend[name]['end'] = time
                        else:
                            attend[name]['end'] = None

            # wifi device
            device = Device()
            device_list = device.get(page='all')
            device_dict = {}
            for device in device_list:
                if 'owner' in device:
                    if device['owner']:
                        # device가 여러개 있는 경우
                        if device['owner'] in device_dict:
                            device_dict[device['owner']].append(device['mac'])
                        else:
                            device_dict[device['owner']] = [device['mac']]

            # wifi 와 지문 인식기 근태 비교
            for name in device_dict:
                begin, end = self.mac.get(device_dict[name], self.today)
                if begin:
                    if name in attend:
                        if attend[name]['begin']:
                            if int(begin) < int(attend[name]['begin']):
                                attend[name]['begin'] = begin
                        else:
                            attend[name]['begin'] = begin
                        if attend[name]['end']:
                            if int(end) > int(attend[name]['end']):
                                attend[name]['end'] = end
                        else:
                            attend[name]['end'] = end
                    else:
                        attend[name] = {'date': self.today, 'name': name, 'begin': begin, 'end': end, 'reason': None}

            for name in attend:
                if name in schedule_dict:
                    status = schedule_dict[name]
                    attend[name]['status'] = (None, 0)
                    if status == '월차':
                        status = '연차'
                    attend[name]['reason'] = status
                    if self.hour >= 18:
                        if '반차' in status:  # status가 2개 이상으로 표시된 경우 ex) 반차, 정기점검
                            status = '반차'
                            attend[name]['reason'] = status
                        attend[name]['workingHours'] = WORKING['status'][status]
                    else:
                        attend[name]['workingHours'] = None
                elif attend[name]['begin']:
                    if not is_holiday:
                        if int(attend[name]['begin']) > WORKING['time']['beginTime']:
                            attend[name]['status'] = ('지각', 1)
                        else:
                            attend[name]['status'] = ('정상출근', 0)
                    else:
                        attend[name]['status'] = ('정상출근', 0)
                    if self.hour >= 18:
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
                    if not is_holiday:
                        if self.hour >= 18:
                            attend[name]['status'] = ('미출근', 3)
                            attend[name]['workingHours'] = 0
                        elif self.hour >= WORKING['time']['beginTime'] / 10000:
                            attend[name]['workingHours'] = None
                            attend[name]['status'] = ('지각', 1)
                        else:
                            attend[name]['status'] = ('출근전', 2)
                            attend[name]['workingHours'] = None
                    else:
                        attend[name]['status'] = ('정상출근', 0)

                self.collection.update_one({'date': self.today, 'name': name}, {'$set': attend[name]}, upsert=True)

    def update_date(self, start=None, end=None):
        data_list = self.collection.find({'date': {"$gte": start, "$lt": end}})
        date_list = []
        for data in data_list:
            if data['date'] not in date_list:
                date_list.append(data['date'])
        for date in date_list:
            self.update(date=date)

    def wifi_attend(self, page=1):
        device = Device()
        paging, device_list = device.get(page=page)
        wifi_list = []
        for device in device_list:
            begin, end = self.mac.get([device['mac']], self.today)
            wifi_list.append({'mac': device['mac'], 'begin': begin, 'end': end, 'owner': device['owner'], 'device': device['device']})
        get_page = Page(page)
        return get_page.paginate(wifi_list, count=paging['count'])


class Event:
    collection = db['event']
    start = None
    end = None

    def get(self):
        _, today, this_month = check_time()
        self.start = this_month['start']
        self.end = this_month['end']
        data_list = []
        if self.start is not None and self.end is not None:
            data_list = self.collection.find({'start': {"$gte": self.start, "$lt": self.end}}, sort=[('id', 1)])
        return data_list

    def post(self, args, type='insert'):

        title, self.start, self.end, event_id = request_event(args)
        request_data = {'title': title, 'start': self.start, 'end': self.end, 'id': event_id}

        if event_id is None and type == 'insert':
            data = self.collection.find_one(sort=[('id', -1)])
            if data:
                event_id = data['id'] + 1
            else:
                event_id = 1
            request_data['id'] = event_id
            self.collection.insert_one(request_data)
        elif type == 'update':
            self.collection.update_one({'id': event_id}, {'$set': request_data})
        elif type == 'delete':
            data = self.collection.find_one({'id': event_id})
            self.start = data['start']
            self.end = data['end']
            self.collection.delete_one({'id': event_id})

        # calendar 에 일정이 변경 되면 그에 따라서 report 내용도 update 하기 위함
        if self.start is not None and self.end is not None:
            report = Report()
            report.update_date(start=self.start, end=self.end)

    def schedule(self, employees, date=None):
        schedule_dict = {}
        data_list = self.collection.find({'start': {"$lte": date}, 'end': {"$gt": date}})
        for data in data_list:
            name = None
            status = '기타'
            for employee in employees:
                if employee['name'] in data['title']:
                    name = employee['name']
            for status_type in WORKING['status']:
                if status_type in data['title']:
                    status = status_type
            if name is not None:
                if name in schedule_dict:
                    schedule_dict[name] = schedule_dict[name] + ', ' + status
                else:
                    schedule_dict[name] = status
        return schedule_dict






