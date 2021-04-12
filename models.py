from werkzeug.security import check_password_hash
import datetime
from pymongo import MongoClient
import pyodbc
import threading

import selenium
from selenium import webdriver
from bs4 import BeautifulSoup
import re
import json

from views.config import page_default
from utils import paginate, checkTime, checkHoliday

from mainconfig import accessDBPwd, calendarUrl, office365, workTime, workStatus

mongoClient = MongoClient('mongodb://localhost:27017/')
db = mongoClient['report']

# connect to access db
# https://stackoverflow.com/questions/50757873/connect-to-ms-access-in-python
# You probably have 32-bit Access (Office) and 64-bit Python. As you know, 32-bit and 64-bit are completely incompatible.
# You need to install 32-bit Python, or upgrade Access (Office) to 64-bit
conn = pyodbc.connect(r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=c:/caps/acserver/access.mdb;PWD=%s' %accessDBPwd)
cursor = conn.cursor()

# db
def post_schedule(scheduleList):
    collection = db['schedule']
    scheduleDict = {}
    for schedule in scheduleList:
        isHoliday = checkHoliday(schedule['date'])
        if not isHoliday:
            collection.update_one({'date':schedule['date'], 'name':schedule['name']}, {'$set':schedule}, upsert=True)
    return scheduleDict

def get_schedule(date=None, startDate=None, endDate=None):
    collection = db['schedule']
    if startDate is None:
        scheduleDict = {}
        data_list = collection.find({'date':date})
        for data in data_list:
            scheduleDict[data['name']] = data['status']
        return scheduleDict
    else:
        schedule = []
        data_list = collection.find({'date':{"$gte":startDate, "$lte":endDate}})
        for data in data_list:
            title = data['name'] + ' / ' + data['status']
            start = data['date']
            schedule.append({'title':title, 'start':start})
        return schedule

def get_calendarFromSharePoint():
    driver = webdriver.Chrome(executable_path='chromedriver')
    driver.get(url=calendarUrl)

    driver.implicitly_wait(time_to_wait=10)

    email = driver.find_element_by_xpath('//*[@id="i0116"]')
    email.send_keys(office365['email'])

    button1 = driver.find_element_by_xpath('//*[@id="idSIButton9"]')
    button1.click()

    password = driver.find_element_by_xpath('//*[@id="i0118"]')
    password.send_keys(office365['password'])
    driver.implicitly_wait(time_to_wait=10)

    btn_click = 0
    while btn_click < 2:
        try:
            button2 = driver.find_element_by_xpath('//*[@id="idSIButton9"]')
            button2.click()
        except selenium.common.exceptions.StaleElementReferenceException as e:
            pass
        else:
            btn_click = btn_click + 1

    driver.implicitly_wait(time_to_wait=15)
    html = driver.page_source

    soup = BeautifulSoup(html, 'html.parser')
    script_blocks = soup.find_all('script', {'type': 'text/javascript'})

    re_string = re.compile('"Strings":(.*)}')
    re_date = re.compile('\d{4}-\d{2}-\d{2}')

    scheduleList = []
    employees = get_employees(page='all')

    for script in script_blocks:
        stringList = re_string.findall(str(script))
        if stringList:
            stringList = stringList[0].split('}')
            stringList = json.loads(stringList[0])
            isOrderEmployee = True
            # employee - date - employee - employee  상황에 대한 fix
            for i, text in enumerate(stringList):
                for employee in employees:
                    if employee['name'] in text:
                        status = '기타'
                        for type in workStatus:
                            if type in text:
                                status = type
                        if not isOrderEmployee:
                            scheduleList[-1]['date'] = scheduleList[-2]['date']
                        scheduleList.append({'name': employee['name'], 'status': status})
                        isOrderEmployee = False

                date = re_date.findall(text)
                if date:
                    date = date[0]
                    if text == date:
                        if 'date' not in scheduleList[-1]:
                            scheduleList[-1]['date'] = date
                        else:
                            if date == scheduleList[-1]['date']:
                                pass
                            else:
                                # employee - date - date 상황
                                schedule = scheduleList[-1].copy()
                                schedule['date'] = date
                                scheduleList.append(schedule)
                        isOrderEmployee = True
    driver.quit()
    if scheduleList:
        post_schedule(scheduleList)

def saveDB():
    hour, today = checkTime()
    isHoliday = checkHoliday(today)
    if not isHoliday and hour > 6:
        accessDay = today[0:4] + today[5:7] + today[8:] # accessDay 형식으로 변환
        cursor.execute("select e_name, e_date, e_time from tenter where e_date = ?", accessDay)
        get_calendarFromSharePoint()
        scheduleDict = get_schedule(date=today)

        attend = {}
        employees = get_employees(page='all')
        for employee in employees:
            name = employee['name']
            attend[name] = {'date':today, 'name':name, 'begin':None, 'end':None}
            if hour >= 18:
                attend[name]['workingHours'] = 0
                attend[name]['status'] = ('미출근', 3)
            elif hour >= workTime['beginTime'] / 10000:
                attend[name]['status'] = ('지각', 1)
            else:
                attend[name]['status'] = ('출근전', 2)

        for name in scheduleDict:
            status = scheduleDict[name]
            if name not in attend:
                attend[name] = {'date':today, 'name':name, 'begin':None, 'end':None}
            attend[name]['status'] = None
            attend[name]['reason'] = status
            if hour >= 18:
                attend[name]['workingHours'] = workStatus[status]
            else:
                attend[name]['workingHours'] = None

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
                    if name not in scheduleDict:
                        if int(attend[name]['begin']) > workTime['beginTime']:
                            attend[name]['status'] = ('지각', 1)
                        else:
                            attend[name]['status'] = ('정상출근', 0)
                        if int(time) > int(attend[name]['end']):
                            attend[name]['end'] = time

                        workingHours = round(int(attend[name]['end'][0:2]) - int(attend[name]['begin'][0:2]) +
                                             (int(attend[name]['end'][2:4]) - int(attend[name]['begin'][2:4])) / 60, 1)
                        if int(attend[name]['end']) > workTime['lunchFinishTime']:
                            workingHours = workingHours - 1
                        attend[name]['workingHours'] = workingHours
            else:
                attend[name]['begin'] = time
                if hour >= 18:
                    attend[name]['end'] = time
                else:
                    attend[name]['end'] = None
                if name not in scheduleDict:
                    if int(attend[name]['begin']) > workTime['beginTime']:
                        attend[name]['status'] = ('지각', 1)
                    else:
                        attend[name]['status'] = ('정상출근', 0)

        collection = db['report']
        for name in attend:
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

def post_employees(request_data):
    collection = db['employees']
    collection.update_one({'name':request_data}, {'$set':request_data}, upsert=True)

def get_employees(page=1):
    collection = db['employees']
    if page == 'all':
        data_list = []
        employees = collection.find(sort=[('name', 1)])
        for employee in employees:
            data_list.append({'name':employee['name']})
        return data_list
    else:
        per_page = page_default['per_page']
        offset = (page - 1) * per_page
        data_list = collection.find(sort=[('name', 1)]).limit(per_page).skip(offset)
        count = data_list.count()
        paging = paginate(page, per_page, count)
        return paging, data_list

# report
def get_attend(page=1, startDate=None, endDate=None):
    per_page = page_default['per_page']
    offset = (page - 1) * per_page
    _, today = checkTime()
    collection = db['report']
    if startDate:
        data_list = collection.find({'date':{"$gte":startDate, "$lte":endDate}}, sort=[('name', 1), ('date', 1)])
    else:
        data_list = collection.find({'date':today}, sort=[('name', 1)])
    count = data_list.count()
    data_list = data_list.limit(per_page).skip(offset)
    paging = paginate(page, per_page, count)
    return paging, today, data_list

# calendar
def get_calendar():
    _, today = checkTime()
    return today
