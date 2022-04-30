from flask import current_app
from werkzeug.security import check_password_hash
import datetime
from pymongo import MongoClient
import pyodbc
from collections import OrderedDict
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time

from office365.runtime.auth.user_credential import UserCredential
from office365.runtime.http.request_options import RequestOptions
from office365.sharepoint.client_context import ClientContext

from utils import check_time, check_holiday, request_event, request_delta, request_get, get_delta_day, get_date_several_months_before, Page
try:
    from mainconfig import ACCESS_DB_PWD, OUTSIDE_CALENDAR_URL, ACCOUNT, MAIL_SERVER, SERVER_URL, MONGO_URL
except Exception as e:
    # try your own Access_DB_PWD and ACCOUNT
    ACCESS_DB_PWD = '*******'
    OUTSIDE_CALENDAR_URL = None
    ACCOUNT = {
        'email': 'test@test.co.kr',
        'password': '*******',
    }
    MAIL_SERVER = {'host': 'smtp.office365.com', 'port': 587}
    SERVER_URL = 'http://127.0.0.1:5000/'
    MONGO_URL = 'mongodb://localhost:27017/'

try:
    from mainconfig import CC
except Exception as e:
    # CC: cc email when notice email
    CC = None
    # CC = 'test@test.co.kr'

from config import USE_WIFI_ATTENDANCE, USE_NOTICE_EMAIL, IS_OUTSIDE_CALENDAR_CONNECTED, EMAIL_NOTICE_BASE, WORKING

mongoClient = MongoClient(MONGO_URL)
db = mongoClient['report']

# createIndex https://velopert.com/560
db.mac.create_index([('date', 1), ('mac', 1)])

# connect to access db
# https://stackoverflow.com/questions/50757873/connect-to-ms-access-in-python
# You probably have 32-bit Access (Office) and 64-bit Python. As you know, 32-bit and 64-bit are completely incompatible.
# You need to install 32-bit Python, or upgrade Access (Office) to 64-bit
conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=c:/caps/acserver/access.mdb;PWD=%s' %ACCESS_DB_PWD)
cursor = conn.cursor()


def eventFromSharePoint():
    collection = db['calendar']

    calendar_url = "https://mirageworks.sharepoint.com/sites/msteams_a0f4c8/_api/web/lists(guid'%s')/items" %(ACCOUNT['guid'])

    ctx = ClientContext(calendar_url).with_credentials(UserCredential(ACCOUNT['email'], ACCOUNT['password']))
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
    return USE_WIFI_ATTENDANCE, USE_NOTICE_EMAIL, IS_OUTSIDE_CALENDAR_CONNECTED, OUTSIDE_CALENDAR_URL, ACCOUNT, CC, WORKING


def get_sharepoint():
    _, yesterday, today, this_month = check_time()
    start = this_month['start']
    end = this_month['end']
    collection = db['calendar']


class User:
    collection = db['user']
    error = None

    def get_user(self, request_data):
        return self.collection.find_one({'email': request_data['email']})

    def get_employee(self, request_data):
        collection = db['employees']
        return collection.find_one({'email': request_data['email'], 'name': request_data['name']})

    def signup(self, request_data):
        '''
            1. the first user is admin.
            2. from the second user, request_data['email'] must be in the employees data.
        '''
        user_data = self.get_user(request_data)
        if user_data:
            self.error = '이미 존재하는 사용자입니다.'
        else:
            user_data = self.collection.find_one(sort=[('create_time', -1)])
            if user_data:
                employee_data = self.get_employee(request_data)
                if employee_data:
                    user_id = user_data['user_id'] + 1
                    request_data['is_admin'] = False
                else:
                    self.error = '가입 요건이 되지 않습니다.'
                    return self.error
            else:
                user_id = 1
                request_data['is_admin'] = True
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

    def get(self, page=1, name=None, date=None):
        if name:
            employee = self.collection.find_one({'name': name})
            return employee
        elif page == 'all':
            employees = self.collection.find(sort=[('name', 1)])
            employees_list = []
            for employee in employees:
                regular = True
                if 'regular' in employee and employee['regular'] == '비상근':
                    regular = False
                if 'email' in employee and employee['email']:
                    email = employee['email']
                else:
                    email = None
                if 'status' in employee and employee['status']:
                    status = employee['status']
                else:
                    status = None
                # 퇴사하지 않은 직원만 포함하기 위해서
                if status != '퇴사':
                    if 'endDate' not in employee:
                        employees_list.append({'name': employee['name'], 'employeeId': employee['employeeId'], 'email': email, 'regular': regular, 'status': status})
                    else:
                        if date and date <= employee['endDate']:
                            employees_list.append({'name': employee['name'], 'employeeId': employee['employeeId'], 'email': email, 'regular': regular, 'status': status})
            return employees_list
        else:
            data_list = self.collection.find(sort=[('department', 1), ('name', 1)])
            get_page = Page(page)
            return get_page.paginate(data_list)

    def post(self, request_data):
        if 'employeeId' not in request_data:
            data = self.collection.find_one(sort=[('employeeId', -1)])
            request_data['employeeId'] = data['employeeId'] + 1
        self.collection.update_one({'name': request_data['name'], 'employeeId': request_data['employeeId']},
                                   {'$set': request_data}, upsert=True)


# Device
class Device:
    employee = Employee()
    collection = db['device']

    def get(self, page=1, date=None):
        if date is None and page=='all':
            device_list = self.collection.find()
        else:
            if date is None:
                _, _, today, _ = check_time()
                date = today
            date = get_date_several_months_before(date, delta=2)
            device_list = self.collection.find({'endDate': {"$gt": date}})
        if page == 'all':
            return device_list
        else:
            get_page = Page(page)
            return get_page.paginate(device_list)

    def new_post(self, request_data): # new device 발견인 경우
        now = datetime.datetime.now() # 최초 등록 시간 기록
        now = str(now)[:10]
        request_data = {'mac': request_data['mac'], 'registerDate': now, 'endDate': now, 'owner': None, 'device': None}
        self.collection.update_one({'mac': request_data['mac']}, {'$set': request_data}, upsert=True)

    def post(self, request_data):
        if 'owner' in request_data and request_data['owner'] == 'None':
            request_data['owner'] = None
        if 'device' in request_data and request_data['device'] == 'None':
            request_data['device'] = None
        if 'owner' in request_data and request_data['owner']:
            employees_list = self.employee.get(page='all')
            for employee in employees_list:
                name = employee['name']
                employee_id = employee['employeeId']
                if request_data['owner'] == name:
                    request_data['employeeId'] = employee_id
        self.collection.update_one({'mac': request_data['mac']}, {'$set': request_data}, upsert=True)

    def by_employees(self, date=None):
        device_list = self.get(page='all', date=date)
        device_dict = {}
        for device in device_list:
            if 'owner' in device:
                if device['owner']:
                    # device가 여러개 있는 경우
                    if device['owner'] in device_dict:
                        device_dict[device['owner']].append(device['mac'])
                    else:
                        device_dict[device['owner']] = [device['mac']]
        return device_dict


class Mac:
    collection = db['mac']

    def get(self, mac_list, date=None):
        begin = None
        end = None
        # if users have devices
        for mac in mac_list:
            data = self.collection.find_one({'date': date, 'mac': mac, 'time': {"$gt": WORKING['time']['overNight']}}, sort=[('time', 1)])
            if data:
                if begin and int(begin) > int(data['time']):
                    begin = data['time']
                elif not begin:
                    begin = data['time']
            data = self.collection.find_one({'date': date, 'mac': mac, 'time': {"$gt": WORKING['time']['overNight']}}, sort=[('time', -1)])
            if data:
                if end and int(end) < int(data['time']):
                    end = data['time']
                elif not end:
                    end = data['time']
        return begin, end

    def get_device_list(self, page=1, date=None):
        device_list = []
        data_list = self.collection.aggregate([
            {'$match':{'date': date, 'time': {"$gt": WORKING['time']['overNight']}}},
            {'$group':{'_id': '$mac'}}])
        for data in data_list:
            for key in data:
                device_list.append(data[key])
        if page == 'all':
            return device_list
        else:
            get_page = Page(page)
            return get_page.paginate(device_list)

    def get_device_end_date(self, mac):
        data = self.collection.find_one({'mac': mac}, sort=[('date', -1)])
        if data is not None:
            date = data['date']
            return date
        else:
            return None

    def post(self, request_data):
        self.collection.insert_one(request_data)


class Report:
    collection = db['report']
    employee = Employee()
    mac = Mac()

    def __init__(self):
        self.hour, self.yesterday, self.today, self.this_month = check_time()

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
            if start and end:
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

            summary = OrderedDict()
            if name:
                attend_list = []
                summary['totalDay'] = 0
                summary['totalWorkingDay'] = 0
                summary['totalWorkingHours'] = 0
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
                summary = self.get_summary(summary)
                return paging, self.today, attend_list, summary
            else:
                return paging, self.today, data_list, summary

    def summary(self, page=1, start=None, end=None):

        data_list = None
        summary_list = []
        if start and end:
            data_list = self.collection.find({'date': {"$gte": start, "$lte": end}}, sort=[('name', 1), ('date', -1)])
        if data_list:
            summary = OrderedDict()
            for data in data_list:
                if data['workingHours'] is not None:
                    name = data['name']
                    if name not in summary:
                        summary[name] = {'name': name}
                    if 'totalDay' not in summary[name]:
                        summary[name]['totalDay'] = 0
                    if 'totalWorkingDay' not in summary[name]:
                        summary[name]['totalWorkingDay'] = 0
                    if 'totalWorkingHours' not in summary[name]:
                        summary[name]['totalWorkingHours'] = 0
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
                    if 'reason' in data and data['reason'] and data['reason'] in summary[name]:
                        summary[name][data['reason']] = summary[name][data['reason']] + 1
                    summary[name]['totalWorkingHours'] = summary[name]['totalWorkingHours'] + data['workingHours']
            for name in summary:
                summary[name] = self.get_summary(summary[name])
                summary_list.append(summary[name])

        get_page = Page(page)
        return get_page.paginate(summary_list)

    def get_summary(self, summary):
        summary['totalWorkingDay'] = summary['totalDay']
        for status in summary:
            if status in WORKING['offDay']:
                summary['totalWorkingDay'] = summary['totalWorkingDay'] - summary[status] * WORKING['offDay'][status]
        summary['totalWorkingDay'] = round(summary['totalWorkingDay'], 2)
        summary['totalWorkingHours'] = round(summary['totalWorkingHours'], 2)
        summary['휴가'] = summary['휴가'] + summary['연차'] + summary['월차']
        del summary['연차']
        del summary['월차']
        return summary

    def update(self, date=None):
        if date is not None:
            if date != self.today:
                hour = 23
            else:
                hour = self.hour
        else:
            date = self.today
            hour = self.hour

        is_holiday = check_holiday(date)
        if hour > 6:
            if IS_OUTSIDE_CALENDAR_CONNECTED:
                try:
                    eventFromSharePoint()
                except Exception as e:
                    # current_app.logger.info(e)
                    # https://wikidocs.net/81081
                    # https://stackoverflow.com/questions/39476889/use-flask-current-app-logger-inside-threading
                    print(e)

            # attend 초기화
            attend = {}
            schedule_dict = {}
            overnight_employees = []

            if date == self.today:        # device update는 오늘 날짜인 경우만 진행
                self.update_devices(date=date)

            if not is_holiday:
                employees_list = self.employee.get(page='all', date=date)
                event = Event()
                schedule_dict = event.schedule(employees_list, date=date)
                for employee in employees_list:
                    name = employee['name']
                    employee_id = employee['employeeId']
                    regular = employee['regular']
                    reason = employee['status']
                    # 같은 employee_id 인데 이름이 바뀌는 경우 발생
                    attend[name] = {'date': date, 'name': name, 'employeeId': employee_id, 'begin': None, 'end': None, 'reason': reason, 'regular': regular}

                self.notice_email(employees_list=employees_list)

            # 지문 인식 출퇴근 기록
            access_today = date[0:4] + date[5:7] + date[8:]  # access_day 형식으로 변환
            cursor.execute("select e_id, e_name, e_date, e_time, e_mode from tenter where e_date = ?", access_today)

            for row in cursor.fetchall():
                employee_id = row[0]
                name = row[1]
                time = row[3]
                mode = int(row[4])
                # card 출근자 name = ''
                if name != '':
                    if int(time) > int(WORKING['time']['overNight']):   # overnight가 아닌 것에 대한 기준
                        if name not in attend:
                            attend[name] = {'date': date, 'name': name, 'employeeId': int(employee_id), 'begin': None, 'end': None, 'reason': None}
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
                    else:
                        overnight_employees.append(employee_id)

            # wifi device
            devices = Device()
            device_dict = devices.by_employees(date=date)

            # wifi 와 지문 인식기 근태 비교
            for name in device_dict:
                begin, end = self.mac.get(device_dict[name], date=date)
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
                        attend[name] = {'date': date, 'name': name, 'begin': begin, 'end': end, 'reason': None}

            for name in attend:
                if name in schedule_dict:
                    status = schedule_dict[name]
                    attend[name]['status'] = (None, 0)
                    attend[name]['reason'] = status
                    if hour >= 18:
                        if '반차' in status:  # status가 2개 이상으로 표시된 경우 ex) 반차, 정기점검
                            status = '반차'
                            attend[name]['reason'] = status
                        attend[name]['workingHours'] = WORKING['status'][status]
                    else:
                        attend[name]['workingHours'] = None
                elif attend[name]['reason']:
                    attend[name]['status'] = (None, 0)
                    if hour >= 18:
                        attend[name]['workingHours'] = WORKING['status'][attend[name]['reason']]
                elif attend[name]['begin']:
                    if not is_holiday:
                        if 'regular' in attend[name] and attend[name]['regular'] and int(attend[name]['begin']) > int(WORKING['time']['beginTime']):
                            # fulltime job만 지각 처리
                            attend[name]['status'] = ('지각', 1)
                        else:
                            attend[name]['status'] = ('정상출근', 0)
                    else:
                        attend[name]['status'] = ('정상출근', 0)
                    if hour >= 18:
                        working_hours = int(attend[name]['end'][0:2]) - int(attend[name]['begin'][0:2]) + \
                                        (int(attend[name]['end'][2:4]) - int(attend[name]['begin'][2:4])) / 60
                        if int(attend[name]['end']) > int(WORKING['time']['lunchFinishTime']) and \
                                int(WORKING['time']['lunchTime']) > int(attend[name]['begin']):
                            working_hours = working_hours - 1
                        attend[name]['workingHours'] = round(working_hours, 1)
                    else:
                        attend[name]['workingHours'] = None
                else:
                    if not is_holiday:
                        if hour >= 18:
                            attend[name]['workingHours'] = 0
                            attend[name]['status'] = ('미출근', 3)
                        elif hour >= int(WORKING['time']['beginTime']) / 10000:
                            attend[name]['workingHours'] = None
                            attend[name]['status'] = ('지각', 1)
                        else:
                            attend[name]['workingHours'] = None
                            attend[name]['status'] = ('출근전', 2)
                    else:
                        attend[name]['status'] = ('정상출근', 0)
                try:
                    if 'regular' in attend[name] and not attend[name]['regular'] and attend[name]['status'][0] in ['미출근', '출근전', '지각'] :
                        # fulltime이 아닌 직원에 대해 미출근과 출근전인 경우 기록하지 않음
                        pass
                    else:
                        self.collection.update_one({'date': date, 'name': name}, {'$set': attend[name]}, upsert=True)
                except Exception as e:
                    print(e)
                    print(attend[name])

            '''
                 1. overnight 근무자에 대해서 이전 날짜 update
            '''
            if overnight_employees:
                self.update_overnight(overnight_employees)

    def update_date(self, start=None, end=None):
        data_list = self.collection.find({'date': {"$gte": start, "$lt": end}})
        date_list = []
        for data in data_list:
            if data['date'] not in date_list:
                date_list.append(data['date'])
        for date in date_list:
            self.update(date=date)

    def wifi_attend(self, page=1, date=None):
        if date is None:
            date = self.today
        devices = Device()
        device_list = devices.get(page='all', date=date)
        device_dict = {}
        for device in device_list:
            device_dict[device['mac']] = device

        paging, mac_list = self.mac.get_device_list(page=page, date=date)

        wifi_list = []
        for mac in mac_list:
            begin, end = self.mac.get([mac], date=date)
            device = device_dict[mac]
            if begin:
                wifi_list.append({'mac': mac, 'date': date, 'begin': begin, 'end': end, 'owner': device['owner'], 'device': device['device'],})
        return paging, wifi_list

    def update_overnight(self, overnight_employees):
        print(overnight_employees)
        access_yesterday = self.yesterday[0:4] + self.yesterday[5:7] + self.yesterday[8:]
        for employee_id in overnight_employees:
            cursor.execute("select e_id, e_name, e_date, e_time, e_mode from tenter where e_date=? and e_id = ?",
                           (access_yesterday, employee_id))
            attend = {'date': self.yesterday, 'employeeId': int(employee_id)}
            for row in cursor.fetchall():
                time = row[3]
                mode = int(row[4])
                if int(time) > int(WORKING['time']['overNight']) or mode != 2:
                    if 'begin' in attend:
                        if int(time) < int(attend['begin']):
                            attend['begin'] = time
                        if int(time) > int(attend['end']):
                            attend['end'] = time
                    else:
                        attend['begin'] = time
                        attend['end'] = time

            if 'begin' in attend:
                access_today = self.today[0:4] + self.today[5:7] + self.today[8:]
                cursor.execute(
                    "select e_id, e_name, e_date, e_time, e_mode from tenter where e_date = ? and e_id = ? and e_mode = ?",
                    (access_today, employee_id, '2'))
                for row in cursor.fetchall():
                    print(row)
                    time = row[3]
                    if int(time) < int(WORKING['time']['overNight']):
                        attend['end'] = time

                working_hours = 24 + int(attend['end'][0:2]) - int(attend['begin'][0:2]) + \
                                (int(attend['end'][2:4]) - int(attend['begin'][2:4])) / 60
                if int(WORKING['time']['lunchTime']) > int(attend['begin']):
                    working_hours = working_hours - 1
                attend['workingHours'] = round(working_hours, 1)
                self.collection.update_one({'date': attend['date'], 'employeeId': int(employee_id)}, {'$set': attend},
                                           upsert=True)

    def notice_email(self, employees_list=[]):
        '''
            1. USE_NOTICE_EMAIL 설정이 True일 경우
            2. 오늘 notice한 이력이 있는지 확인 후
            3. EMAIL_NOTICE_BASE 일 경우 email 전송
        '''
        if USE_NOTICE_EMAIL:
            collection = db['notice']
            notice = collection.find_one({'date': self.today})
            if notice is None:
                for employee in employees_list:
                    if employee['email'] is not None:
                        insert_data = self.send_email(employee=employee)
                        if insert_data is not None:
                            collection.insert_one(insert_data)

    def send_email(self, employee=None):
        name = employee['name']
        email = employee['email']

        report = self.collection.find_one({'name': name, 'date': {"$lt": self.today}}, sort=[('date', -1)])
        report_date = report['date']
        begin = report['begin']
        if begin is not None:
            begin = begin[0:2] + ':' + begin[2:4] + ':' + begin[4:6]
        status = report['status'][0]
        working_hours = report['workingHours']

        if status in EMAIL_NOTICE_BASE:
            # https://techexpert.tips/ko/python-ko/파이썬-office-365를-사용하여-이메일-보내기
            # https://nowonbun.tistory.com/684 (참조자)
            body = '\n' \
                   ' 안녕하세요 %s님 \n' \
                   '근태 관련하여 다음의 사유가 있어 메일을 송부합니다. \n ' \
                   '\n' \
                   '- 이름: %s \n' \
                   '- 날짜: %s \n' \
                   '- 출근 시각: %s \n' \
                   '- 근무 시간: %s \n' \
                   '- 사유: %s \n' \
                   '\n' \
                   '연차, 외근 등의 사유가 있는 경우 %s 에 기록을 하시면 근태가 정정이 됩니다. ' \
                   % (name, name, report_date, begin, working_hours, str(status), SERVER_URL + 'calendar')

            mimemsg = MIMEMultipart()
            mimemsg['From'] = ACCOUNT['email']
            mimemsg['To'] = email
            if CC is not None:
                mimemsg['Cc'] = CC
            mimemsg['Subject'] = '[근태 관리] ' + report_date + ' ' + name + ' ' + str(status)
            mimemsg.attach(MIMEText(body, 'plain'))
            try:
                connection = smtplib.SMTP(host=MAIL_SERVER['host'], port=MAIL_SERVER['port'])
                connection.starttls()
                connection.login(ACCOUNT['email'], ACCOUNT['password'])
                connection.send_message(mimemsg)
                connection.quit()
                insert_data = {'date': self.today, 'name': name, 'email': email, 'reportDate': report_date, 'status': status}
                return insert_data

            except Exception as e:
                print(e)
                return None
        else:
            return None

    def update_devices(self, date=None):
        devices = Device()
        mac_list = self.mac.get_device_list(page='all', date=date)
        for mac in mac_list:
            request_data = {'mac': mac, 'endDate': date}
            devices.post(request_data)


class Event:
    collection = db['event']

    def get(self, args):
        _, start, end, _ = request_event(args)
        data_list = []
        if start is not None and end is not None:
            data_list = self.collection.find({'start': {"$gte": start, "$lt": end}}, sort=[('id', 1)])
        return data_list

    def insert(self, args):
        title, start, end, event_id = request_event(args)
        request_data = {'title': title, 'start': start, 'end': end, 'id': event_id}

        if event_id is None:
            data = self.collection.find_one(sort=[('id', -1)])
            if data:
                request_data['id'] = data['id'] + 1
            else:
                request_data['id'] = 1
            self.collection.insert_one(request_data)
        else:
            self.collection.update_one({'id': event_id}, {'$set': request_data}, upsert=True)
        # calendar 일정이 변경 되면 그에 따라서 report 내용도 update 하기 위함
        self.update_report(start=start, end=end)

    def delete(self, args):
        title, _, _, event_id = request_event(args)

        data = self.collection.find_one({'id': event_id})
        start = data['start']
        end = data['end']
        self.collection.delete_one({'id': event_id})

        # calendar 일정이 변경 되면 그에 따라서 report 내용도 update 하기 위함
        self.update_report(start=start, end=end)
        return start, end

    def drop(self, args):

        start, end = self.delete(args)
        title, event_id, delta = request_delta(args)
        start = get_delta_day(start, delta=delta)
        end = get_delta_day(end, delta=delta)

        request_data = {'title': title, 'start': start, 'end': end, 'id': event_id}
        self.collection.update_one({'id': event_id}, {'$set': request_data}, upsert=True)

        # calendar 일정이 변경 되면 그에 따라서 report 내용도 update 하기 위함
        self.update_report(start=start, end=end)

    def schedule(self, employees_list, date=None):
        schedule_dict = {}
        data_list = self.collection.find({'start': {"$lte": date}, 'end': {"$gt": date}})
        for data in data_list:
            name = None
            status = '기타'
            for employee in employees_list:
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

    def update_report(self, start=None, end=None):
        if start is not None and end is not None:
            report = Report()
            report.update_date(start=start, end=end)










