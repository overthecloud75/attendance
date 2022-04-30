from .db import db
from utils import Page
from config import WORKING


class Mac:
    def __init__(self):
        self.collection = db['mac']

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