import scapy.layers.l2
from scapy.all import *
import datetime
from datetime import timedelta
import socket
from korean_lunar_calendar import KoreanLunarCalendar

from views.config import page_default
from workingconfig import WORKING, NET, PDST, PSRC


class Page:
    def __init__(self, page):
        self.page = page
        self.per_page = page_default['per_page']
        self.offset = (page - 1) * self.per_page

    def paginate(self, data_list):
        if type(data_list) == list:
            count = len(data_list)
            data_list = data_list[self.offset:self.offset + self.per_page]
        else:
            count = data_list.count()
            data_list = data_list.limit(self.per_page).skip(self.offset)

        total_pages = int(count / self.per_page) + 1
        screen_pages = 10

        if self.page < 1:
            self.page = 1
        elif self.page > total_pages:
            self.page = total_pages

        start_page = (self.page - 1) // screen_pages * screen_pages + 1

        pages = []
        prev_num = start_page - screen_pages
        next_num = start_page + screen_pages

        if start_page - screen_pages > 0:
            has_prev = True
        else:
            has_prev = False
        if start_page + screen_pages > total_pages:
            has_next = False
        else:
            has_next = True
        if total_pages > screen_pages + start_page:
            for i in range(screen_pages):
                pages.append(i + start_page)
        elif total_pages < screen_pages:
            for i in range(total_pages):
                pages.append(i + start_page)
        else:
            for i in range(total_pages - start_page + 1):
                pages.append(i + start_page)

        paging = {'page': self.page,
                  'has_prev': has_prev,
                  'has_next': has_next,
                  'prev_num': prev_num,
                  'next_num': next_num,
                  'count': count,
                  'offset': self.offset,
                  'pages': pages,
                  'screen_pages': screen_pages,
                  'total_pages': total_pages
                  }
        return paging, data_list


def check_holiday(date):
    is_holiday = False
    year = date[0:4]
    month = date[5:7]
    day = date[8:]
    month_day = month + day

    calendar = KoreanLunarCalendar()
    calendar.setSolarDate(int(year), int(month), int(day))
    lunar_month_day = calendar.LunarIsoFormat()
    lunar_month_day = lunar_month_day[5:7] + lunar_month_day[8:]
    if month_day in WORKING['holidays']:
        is_holiday = True
    if lunar_month_day in WORKING['lunarHolidays']:
        is_holiday = True
    date = datetime.datetime(int(year), int(month), int(day), 1, 0, 0)  # str -> datetime으로 변환
    if date.weekday() == 5 or date.weekday() == 6:
        is_holiday = True
    elif date.weekday() == 0:
        # 대체공휴일 적용
        yesterday = date.today() - timedelta(1)
        yesterday = datetimeToDate(yesterday)
        twodaysago = date.today() - timedelta(2)
        twodaysago = datetimeToDate(twodaysago)
        if yesterday in WORKING['alternativeVacation'] or twodaysago in WORKING['alternativeVacation']:
            is_holiday = True
    return is_holiday


def datetimeToDate(date):
    this_month = date.month
    this_day = date.day
    if this_month < 10:
        this_month = '0' + str(this_month)
    else:
        this_month = str(this_month)
    if this_day < 10:
        this_day = '0' + str(this_day)
    else:
        this_day = str(this_day)
    date = this_month + this_day
    return date


def check_time():
    today = datetime.date.today()
    now = datetime.datetime.now()
    hour = now.hour
    today = today.strftime("%Y-%m-%d")
    month = now.month
    year = now.year
    start = datetime.datetime(year, month, 1, 0, 0, 0)
    start = start.strftime("%Y-%m-%d")
    end = datetime.datetime(year, month + 1, 1, 0, 0, 0)
    end = end.strftime("%Y-%m-%d")
    this_month = {'start': start, 'end': end}
    return hour, today, this_month


def check_hour():
    today = datetime.date.today()
    today = today.strftime("%Y-%m-%d")
    now = datetime.datetime.now()
    hour = correct_time(now.hour)
    minute = correct_time(now.minute)
    second = correct_time(now.second)
    return today, hour + minute + second


def correct_time(time):
    if int(time) < 10:
        time = '0' + str(time)
    else:
        time = str(time)
    return time


def request_get(request_data):
    page = int(request_data.get('page', 1))
    name = request_data.get('name', None)
    start = request_data.get('start', None)
    if start:
        if start[4] != '-':
            start = start[6:] + '-' + start[:2] + '-' + start[3:5]
    end = request_data.get('end', None)
    if end:
        if end[4] != '-':
            end = end[6:] + '-' + end[:2] + '-' + end[3:5]
    return page, name, start, end


def request_event(request_data):
    title = request_data.get('title', None)
    start = request_data.get('start', None)
    end = request_data.get('end', None)
    id = request_data.get('id', None)
    if id is not None:
        id = int(id)
    return title, start, end, id


def detect_network():
    network_list = []
    for ip in range(128):
        if ip not in [0, 1, 255]:
            data = check_arp(ip)
            if data:
                network_list.append(data)
    # network_list = check_net()
    return network_list


def check_arp(ip):
    answers = sr1(ARP(op='who-has', psrc=PSRC, pdst=PDST + str(ip)), timeout=1, verbose=False)
    data = {}
    if answers:
        ans = answers[0]
        date, time = check_hour()
        data = {'mac': ans.hwsrc, 'ip': ans.psrc, 'date': date, 'time': time}
    return data


def check_net():
    network_list = []
    ans, noans = scapy.layers.l2.arping(NET, timeout=2, verbose=False)
    for sent, received in ans.res:
        mac = received.hwsrc
        ip = received.psrc
        date, time = check_hour()
        network_list.append({'mac': mac, 'ip': ip, 'date': date, 'time': time})
    return network_list


