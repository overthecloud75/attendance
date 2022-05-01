import pyodbc
from collections import OrderedDict

from utils import check_time, check_holiday, get_delta_day, Page #, request_event, request_delta, request_get, get_date_several_months_before
from .db import db
from .mail import send_email
from .employee import Employee
from .mac import Mac
from .device import Device
try:
    from mainconfig import ACCESS_DB_PWD, SERVER_URL
except Exception as e:
    # try your own Access_DB_PWD
    ACCESS_DB_PWD = '*******'
    SERVER_URL = 'http://127.0.0.1:5000/'
from config import USE_WIFI_ATTENDANCE, USE_NOTICE_EMAIL, EMAIL_NOTICE_BASE, WORKING

# connect to access db
# https://stackoverflow.com/questions/50757873/connect-to-ms-access-in-python
# You probably have 32-bit Access (Office) and 64-bit Python. As you know, 32-bit and 64-bit are completely incompatible.
# You need to install 32-bit Python, or upgrade Access (Office) to 64-bit
conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=c:/caps/acserver/access.mdb;PWD=%s' %ACCESS_DB_PWD)
cursor = conn.cursor()

class Report:
    def __init__(self):
        self.collection = db['report']
        self.employee = Employee()
        self.mac = Mac()

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
            # attend 초기화
            attend = {}
            schedule_dict = {}
            overnight_employees = []

            if date == self.today:        # device update는 오늘 날짜인 경우만 진행
                self.update_devices(date=date)

            if not is_holiday:
                employees_list = self.employee.get(page='all', date=date)
                schedule_dict = self.schedule(employees_list, date=date)
                for employee in employees_list:
                    print('employee', employee)
                    name = employee['name']
                    employee_id = employee['employeeId']
                    regular = employee['regular']
                    reason = employee['status']
                    # 같은 employee_id 인데 이름이 바뀌는 경우 발생
                    attend[name] = {'date': date, 'name': name, 'employeeId': employee_id, 'begin': None, 'end': None, 'reason': reason, 'regular': regular}
                # update 날짜가 오늘일때만 메일 송부
                if date == self.today:
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
                self.update_overnight(overnight_employees, date=date)

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

    def update_overnight(self, overnight_employees, date=None):
        print('overnight', overnight_employees)
        if date is None:
            date = self.today
        yesterday = get_delta_day(date, delta=-1)

        access_yesterday = yesterday[0:4] + yesterday[5:7] + yesterday[8:]
        for employee_id in overnight_employees:
            cursor.execute("select e_id, e_name, e_date, e_time, e_mode from tenter where e_date=? and e_id = ?",
                           (access_yesterday, employee_id))
            attend = {'date': yesterday, 'employeeId': int(employee_id)}
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
                access_today = date[0:4] + date[5:7] + date[8:]
                cursor.execute(
                    "select e_id, e_name, e_date, e_time, e_mode from tenter where e_date = ? and e_id = ?",
                    (access_today, employee_id))
                end = '000000'
                for row in cursor.fetchall():
                    time = row[3]
                    if int(time) < int(WORKING['time']['overNight']):
                        if end < time:
                            end = time
                attend['end'] = end

                if end != '000000':
                    working_hours = 24 + int(attend['end'][0:2]) - int(attend['begin'][0:2]) + \
                                    (int(attend['end'][2:4]) - int(attend['begin'][2:4])) / 60
                else:
                    working_hours = int(attend['end'][0:2]) - int(attend['begin'][0:2]) + \
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
                        insert_data = self.send_notice_email(employee=employee)
                        if insert_data:
                            collection.insert_one(insert_data)

    def send_notice_email(self, employee):
        print('send_notice_email')
        name = employee['name']
        employee_id = employee['employeeId']
        email = employee['email']

        report = self.collection.find_one({'name': name, 'employeeId': employee_id, 'date': {"$lt": self.today}}, sort=[('date', -1)])
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
                   %(name, name, report_date, begin, working_hours, str(status), SERVER_URL + 'calendar')

            subject = '[근태 관리] ' + report_date + ' ' + name + ' ' + str(status)
            sent = send_email(email=email, subject=subject, body=body, include_cc=True)
            if sent:
                return {'date': self.today, 'name': name, 'email': email, 'reportDate': report_date, 'status': status}
            else:
                return sent
        else:
            return False

    def update_devices(self, date=None):
        devices = Device()
        mac_list = self.mac.get_device_list(page='all', date=date)
        for mac in mac_list:
            request_data = {'mac': mac, 'endDate': date}
            devices.post(request_data)

    def schedule(self, employees_list, date=None):
        collection = db['event']
        schedule_dict = {}
        data_list = collection.find({'start': {"$lte": date}, 'end': {"$gt": date}})
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