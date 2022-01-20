import os
import subprocess
import locale
import scapy.layers.l2
from scapy.all import *
import datetime
from datetime import timedelta
from korean_lunar_calendar import KoreanLunarCalendar

from views.config import page_default
from workingconfig import WORKING, USE_LUNAR_NEW_YEAR, PRIVATE_IP_RANGE
try:
    from mainconfig import NET, PDST, PSRC, NAME_OF_ROUTER
except Exception as e:
    # use your own wifi ip and router name
    # PSRC: server wifi ip
    NET = '192.168.2.1/24'
    PSRC = '192.168.2.2'
    PDST = '192.168.2.'
    NAME_OF_ROUTER = 'default'


class Page:
    def __init__(self, page):
        self.page = page
        self.per_page = page_default['per_page']
        self.offset = (page - 1) * self.per_page

    def paginate(self, data_list, count=None):
        if count:
            pass
        else:
            if type(data_list) == list:
                count = len(data_list)
                data_list = data_list[self.offset:self.offset + self.per_page]
            else:
                count = data_list.count()
                data_list = data_list.limit(self.per_page).skip(self.offset)

        if count != 0:
            if count // self.per_page == 0:
                total_pages = int(count / self.per_page)
            else:
                total_pages = int(count / self.per_page) + 1
        else:
            total_pages = 1
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

    date = datetime.datetime(int(year), int(month), int(day), 1, 0, 0)  # str -> datetime으로 변환

    lunar_calendar = KoreanLunarCalendar()
    lunar_calendar.setSolarDate(int(year), int(month), int(day))
    lunar_month_day = lunar_calendar.LunarIsoFormat()
    lunar_month_day = lunar_month_day[5:7] + lunar_month_day[8:]

    if month_day in WORKING['holidays'] or lunar_month_day in WORKING['lunarHolidays']:
        is_holiday = True
    elif date.weekday() == 5 or date.weekday() == 6:
        is_holiday = True
    elif date.weekday() == 0:
        # 대체공휴일 적용
        yesterday = date - timedelta(days=1)
        yesterday = datetimeToDate(yesterday)
        two_days_ago = date - timedelta(days=2)
        two_days_ago = datetimeToDate(two_days_ago)
        if yesterday in WORKING['alternativeVacation'] or two_days_ago in WORKING['alternativeVacation']:
            is_holiday = True

    if USE_LUNAR_NEW_YEAR:
        if not is_holiday and int(month) < 4:
            # 음력 1월 1일 전날의 날짜를 특정하기 어려워서 아래의 logic을 사용
            # 12월 29일수도 있고 12월 30일일 수도 있음 윤달이 있으면 단순히 처리하기 쉽지 않음
            tomorrow = date + timedelta(days=1)
            tomorrow = datetimeToDate(tomorrow)
            lunar_calendar.setSolarDate(int(year), int(tomorrow[0:2]), int(tomorrow[2:4]))
            lunar_month_day = lunar_calendar.LunarIsoFormat()
            lunar_month_day = lunar_month_day[5:7] + lunar_month_day[8:]
            if lunar_month_day == '0101':
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
    month = month + 1
    if month == 13:
        month = 1
        year = year + 1
    end = datetime.datetime(year, month, 1, 0, 0, 0)
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


def check_wifi_connected():
    os_encoding = locale.getpreferredencoding()
    cmd = 'netsh interface show interface'
    cmd = cmd.split()
    fd_popen = subprocess.Popen(cmd, stdout=subprocess.PIPE).stdout
    data_list = fd_popen.read().decode(os_encoding).strip().split()
    fd_popen.close()

    status_list = []
    interface_list = []
    for data in data_list:
        if '연결' in data or 'connected' in data.lower():
            status_list.append(data.lower())
        if '이더넷' in data or 'ethernet' in data.lower() or 'wi-fi' in data.lower():
            interface_list.append(data.lower())

    connected = False
    for status, interface in zip(status_list, interface_list):
        if interface == 'wi-fi':
            if status == '연결됨' or status == 'connected':
                connected = True

    return connected


def connect_wifi():
    os.system(f'''cmd /c "netsh wlan connect name={NAME_OF_ROUTER}"''')


def check_private_ip(ip):
    ip = ip.split('.')
    private_ip_range = PRIVATE_IP_RANGE.split('.')

    is_private_ip = True
    for i, table in enumerate(private_ip_range):
        if table != '0':
            if ip[i] != private_ip_range[i]:
                is_private_ip = False
                break
    return is_private_ip





