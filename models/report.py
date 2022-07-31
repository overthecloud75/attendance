import pyodbc
from collections import OrderedDict
import random

from utils import check_time, check_holiday, get_delta_day, date_range, Page
from .db import db, BasicModel
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
from config import USE_WIFI_ATTENDANCE, USE_NOTICE_EMAIL, EMAIL_NOTICE_BASE, WORKING, ALTERNATIVE_MILITARY_ATTEND_MODE

# connect to access db
# https://stackoverflow.com/questions/50757873/connect-to-ms-access-in-python
# You probably have 32-bit Access (Office) and 64-bit Python. As you know, 32-bit and 64-bit are completely incompatible.
# You need to install 32-bit Python, or upgrade Access (Office) to 64-bit
conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=c:/caps/acserver/access.mdb;PWD=%s' %ACCESS_DB_PWD)
cursor = conn.cursor()


class Report(BasicModel):
    def __init__(self):
        super().__init__(model='reports')
        self.employee = Employee()
        self.mac = Mac()

        self.hour, self.today, self.this_month = check_time()

    def attend(self, page=None, name=None, start=None, end=None):
        if page == 'all':
            attend_list = []
            employee = self.employee.get(name=name)
            if employee:
                if employee['regular'] == '병특' and ALTERNATIVE_MILITARY_ATTEND_MODE:
                    data_list = self._altertative_military_attend(employee, start, end)
                else:
                    if start and end:
                        data_list = self.collection.find({'date': {'$gte': start, '$lte': end}, 'name': name},
                                                     sort=[('name', 1), ('date', 1)])
                    elif start or end:
                        data_list = []
                    else:
                        data_list = self.collection.find({'name': name}, sort=[('date', 1)])

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
            if name:
                employee = self.employee.get(name=name)
                if employee and employee['regular'] == '병특' and ALTERNATIVE_MILITARY_ATTEND_MODE:
                    data_list = self._altertative_military_attend(employee, start, end)
                else:
                    data_list = self.collection.find({'date': {'$gte': start, '$lte': end}, 'name': name},
                                                     sort=[('name', 1), ('date', -1)])
            else:
                data_list = self.collection.find({'date': {'$gte': start, '$lte': end}},
                                                 sort=[('name', 1), ('date', -1)])

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
                        if '_id' in data:
                            del data['_id']
                        if 'status' in data:
                            if data['status']:
                                summary[data['status']] = summary[data['status']] + 1
                        if 'reason' in data and data['reason']:
                            summary[data['reason']] = summary[data['reason']] + 1
                        summary['totalWorkingHours'] = summary['totalWorkingHours'] + data['workingHours']
                    attend_list.append(data)
                summary = self._get_summary(summary)
                return paging, self.today, attend_list, summary
            else:
                return paging, self.today, data_list, summary

    def summary(self, page=1, start=None, end=None):

        data_list = None
        summary_list = []
        if start and end:
            data_list = self.collection.find({'date': {'$gte': start, '$lte': end}}, sort=[('name', 1), ('date', -1)])
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
                        if data['status']:
                            summary[name][data['status']] = summary[name][data['status']] + 1
                    if 'reason' in data and data['reason'] and data['reason'] in summary[name]:
                        summary[name][data['reason']] = summary[name][data['reason']] + 1
                    summary[name]['totalWorkingHours'] = summary[name]['totalWorkingHours'] + data['workingHours']
            for name in summary:
                summary[name] = self._get_summary(summary[name])
                summary_list.append(summary[name])
        if page == 'all':
            return summary_list
        else:
            get_page = Page(page)
            return get_page.paginate(summary_list)

    def update(self, date=None):
        '''
            1. device 정보 update (오늘 날짜인 경우만 update)
            2. 평일인 경우 이전 출근 기록에 지각, 미출근 등에 대해서 통지 메일 송부 (오늘 날짜인 경우만 update)
            3. 지문 인식기 근태 기록 확인
            4. wifi 근태 기록 확인
            5. overnight 근무가 확인 되는 경우 이전 날짜 근태 기록 update
        '''
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

            if not is_holiday:
                employees_list = self.employee.get(page='all', date=date)
                schedule_dict = self._schedule(employees_list, date=date)
                # special holiday가 있는 경우 제외
                if 'holiday' not in schedule_dict:
                    for employee in employees_list:
                        name = employee['name']
                        employee_id = employee['employeeId']
                        regular = employee['regular']
                        if employee['mode'] in WORKING['status']:
                            reason = employee['mode']
                        else:
                            reason = None
                        # 같은 employee_id 인데 이름이 바뀌는 경우 발생
                        attend[name] = {'date': date, 'name': name, 'employeeId': employee_id, 'begin': None, 'end': None, 'reason': reason, 'regular': regular}
                    # update 날짜가 오늘 날짜인 경우만 진행
                    if date == self.today:
                        self._update_devices(date=date)
                        self._notice_email(employees_list=employees_list)

            # 지문 인식 출퇴근 기록
            attend, overnight_employees = self.fingerprint_attend(attend, date, hour)

            # 지문 인식기 + wifi 출퇴근 기록
            attend = self._fingerprint_or_wifi(attend, date)

            # attend
            for name in attend:
                if name in schedule_dict:
                    status = schedule_dict[name]
                    attend[name]['status'] = None
                    attend[name]['reason'] = status
                    if hour >= 18:
                        if '반차' in status:  # status가 2개 이상으로 표시된 경우 ex) 반차, 정기점검
                            status = '반차'
                            attend[name]['reason'] = status
                        attend[name]['workingHours'] = WORKING['status'][status]
                    else:
                        attend[name]['workingHours'] = None
                elif attend[name]['reason']:
                    attend[name]['status'] = None
                    if hour >= 18:
                        attend[name]['workingHours'] = WORKING['status'][attend[name]['reason']]
                    else:
                        attend[name]['workingHours'] = None # 파견인 경우 18시 전에 workingHours에 대한 내용이 없어서 추가
                elif attend[name]['begin']:
                    if not is_holiday:
                        if 'regular' in attend[name] and attend[name]['regular'] in WORKING['update'] and \
                                int(attend[name]['begin']) > int(WORKING['time']['beginTime']):
                            # fulltime job만 지각 처리
                            attend[name]['status'] = '지각'
                        else:
                            attend[name]['status'] = '정상출근'
                    else:
                        attend[name]['status'] = '정상출근'
                    if hour >= 18:
                        attend[name]['workingHours'] = self._calculate_working_hours(attend[name]['begin'], attend[name]['end'], overnight=False)
                    else:
                        attend[name]['workingHours'] = None
                else:
                    if not is_holiday:
                        if hour >= 18:
                            attend[name]['workingHours'] = 0
                            attend[name]['status'] = '미출근'
                        elif hour >= int(WORKING['time']['beginTime']) / 10000:
                            attend[name]['workingHours'] = None
                            attend[name]['status'] = '지각'
                        else:
                            attend[name]['workingHours'] = None
                            attend[name]['status'] = '출근전'
                    else:
                        attend[name]['status'] = '정상출근'
                try:
                    if 'regular' in attend[name] and attend[name]['regular'] not in WORKING['update'] and \
                            attend[name]['status'] not in ['정상출근'] :
                        # fulltime이 아닌 직원에 대해 미출근과 출근전인 경우 기록하지 않음
                        # 주말인 경우 employee 정보 수집을 하지 않기 때문에 regular key가 없을 수 있음
                        # employee 등록이 안 된 경우 regular key가 없을 수 있음
                        pass
                    else:
                        self.collection.update_one({'date': date, 'name': name}, {'$set': attend[name]}, upsert=True)
                except Exception as e:
                    print('error', e)
                    print(attend[name])

            '''
                 1. overnight 근무자에 대해서 이전 날짜 update
            '''
            if overnight_employees:
                self._update_overnight(overnight_employees, date=date)

    def update_date(self, start=None, end=None):
        data_list = self.collection.find({'date': {"$gte": start, "$lt": end}})
        date_list = []
        for data in data_list:
            if data['date'] not in date_list:
                date_list.append(data['date'])
        for date in date_list:
            self.update(date=date)

    def fingerprint_attend(self, attend, date, hour):
        overnight_employees = []

        access_today = date[0:4] + date[5:7] + date[8:]  # access_day 형식으로 변환
        cursor.execute("select e_id, e_name, e_date, e_time, e_mode from tenter where e_date = ?", access_today)

        for row in cursor.fetchall():
            employee_id = row[0]
            name = row[1]
            time = row[3]
            mode = int(row[4])
            # card 출근자 name = ''
            if name != '':
                if int(time) > int(WORKING['time']['overNight']):  # overnight가 아닌 것에 대한 기준
                    if name not in attend:
                        attend[name] = {'date': date, 'name': name, 'employeeId': int(employee_id), 'begin': None,
                                        'end': None, 'reason': None}
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
                    print('overnight', employee_id, time)
                    if employee_id not in overnight_employees:
                        overnight_employees.append(employee_id)
        return attend, overnight_employees

    def wifi_attend(self, page=1, start=None, end=None):
        wifi_list = []
        devices = Device()
        device_list = devices.get(page='all', date=start)
        device_dict = {}
        for device in device_list:
            device_dict[device['mac']] = device

        paging, mac_list = self.mac.get_device_list(page=page, date=start)

        for mac in mac_list:
            begin, end = self.mac.get([mac], date=start)
            device = device_dict[mac]
            if begin:
                wifi_list.append({'mac': mac, 'date': start, 'begin': begin, 'end': end, 'owner': device['owner'], 'device': device['device'],})
        return paging, wifi_list

    def _fingerprint_or_wifi(self, attend, date):
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
        return attend

    def _get_summary(self, summary):
        summary['totalWorkingDay'] = summary['totalDay']
        for status in summary:
            if status in WORKING['offDay']:
                summary['totalWorkingDay'] = summary['totalWorkingDay'] - summary[status] * WORKING['offDay'][status]
        summary['totalWorkingDay'] = round(summary['totalWorkingDay'], 2)
        summary['totalWorkingHours'] = round(summary['totalWorkingHours'], 2)
        summary['휴가'] = summary['휴가'] + summary['연차'] + summary['월차']
        summary['외근'] = summary['외근'] + summary['출장'] + summary['미팅'] + summary['설명회'] + summary['평가']
        del summary['연차']
        del summary['월차']
        del summary['출장']
        del summary['미팅']
        del summary['설명회']
        del summary['평가']
        return summary

    def _calculate_working_hours(self, begin, end, overnight=False):
        working_hours = (int(end[0:2]) - int(begin[0:2])) + \
                        (int(end[2:4]) - int(begin[2:4])) / 60
        if overnight:
            working_hours = working_hours + 24
            if int(WORKING['time']['lunchTime']) > int(begin):
                working_hours = working_hours - 1
        else:
            if int(end) > int(WORKING['time']['lunchFinishTime']) and \
                    int(WORKING['time']['lunchTime']) > int(begin):
                working_hours = working_hours - 1
        working_hours = round(working_hours, 1)
        return working_hours

    def _update_overnight(self, overnight_employees, date=None):
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

                attend['workingHours'] = self._calculate_working_hours(attend['begin'], end, overnight=True)
                self.collection.update_one({'date': attend['date'], 'employeeId': int(employee_id)}, {'$set': attend},
                                           upsert=True)

    def _notice_email(self, employees_list=[]):
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
                        insert_data = self._send_notice_email(employee=employee)
                        if insert_data:
                            collection.insert_one(insert_data)

    def _send_notice_email(self, employee):
        name = employee['name']
        employee_id = employee['employeeId']
        email = employee['email']
        regular = employee['regular']

        report = self.collection.find_one({'name': name, 'employeeId': employee_id, 'date': {"$lt": self.today}}, sort=[('date', -1)])
        report_date = report['date']
        begin = report['begin']
        if begin is not None:
            begin = begin[0:2] + ':' + begin[2:4] + ':' + begin[4:6]
        status = report['status']
        working_hours = report['workingHours']
        if status in EMAIL_NOTICE_BASE and regular in WORKING['update']:
            print('send_notice_email', self.today, name)
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
                   %(name, name, report_date, begin, working_hours, str(status), SERVER_URL + 'schedule')

            subject = '[근태 관리] ' + report_date + ' ' + name + ' ' + str(status)
            sent = send_email(email=email, subject=subject, body=body, include_cc=True)
            if sent:
                return {'date': self.today, 'name': name, 'email': email, 'reportDate': report_date, 'status': status}
            else:
                return sent
        else:
            return False

    def _update_devices(self, date=None):
        devices = Device()
        mac_list = self.mac.get_device_list(page='all', date=date)
        for mac in mac_list:
            request_data = {'mac': mac, 'endDate': date}
            devices.post(request_data)

    def _schedule(self, employees_list, date=None):
        collection = db['event']
        schedule_dict = {}
        data_list = collection.find({'start': {"$lte": date}, 'end': {"$gt": date}})
        for data in data_list:
            if data['title'] in WORKING['specialHolidays']:
                schedule_dict = {'holiday': data['title']}
                break
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

    def _altertative_military_attend(self, employee, start, end):
        date_list = date_range(start, end)
        data_list = []
        name = employee['name']
        for date in date_list:
            if date > self.today:
                break
            if 'endDate' in employee and date > employee['endDate']:
                break
            data = self.collection.find_one({'date': date, 'name': name})
            if data is None:
                data = {'date': date, 'name': name, 'begin': None, 'employeeId': employee['employeeId'], 'end': None,
                        'reason': '휴일', 'workingHours': None, 'status': None}
            else:
                if data['reason'] == '파견':
                    data['begin'] = '08' + self._random_attend(30, add=30) + self._random_attend(60)
                    data['end'] = '18' + self._random_attend(60) + self._random_attend(60)
                    data['workingHours'] = self._calculate_working_hours(data['begin'], data['end'], overnight=False)
                    data['status'] = '정상출근'
                    data['reason'] = None
            data_list.append(data)
        return data_list

    def _random_attend(self, range, add=0):
        time = random.randrange(0, range) + add
        if time >= 10:
            str_time = str(time)
        else:
            str_time = '0'+str(time)
        return str_time
