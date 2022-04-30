from .user import User
from .employee import Employee
from .device import Device
from .mac import Mac
from .report import Report
from .event import Event

from config import USE_WIFI_ATTENDANCE, USE_NOTICE_EMAIL, EMAIL_NOTICE_BASE, WORKING
try:
    from mainconfig import ACCOUNT
except Exception as e:
    ACCOUNT = {
        'email': 'test@test.co.kr',
        'password': '*******',
    }
try:
    from mainconfig import CC
except Exception as e:
    # CC: cc email when notice email
    CC = None
    # CC = 'test@test.co.kr'


def get_setting():
    return USE_WIFI_ATTENDANCE, USE_NOTICE_EMAIL, ACCOUNT, CC, WORKING

