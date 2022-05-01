import datetime

from .db import db
from utils import Page


class Board:
    def __init__(self):
        self.collection = db['board']

    def get(self, page=1, start=None, end=None):
        data_list = self.collection.find(sort=[('create_time', -1)])
        get_page = Page(page)
        return get_page.paginate(data_list)

    def get_content(self, create_time=None):
        data = self.collection.find_one({'create_time': create_time})
        return data

    def post(self, request_data):
        if 'create_time' in request_data:
            request_data['update_time'] = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        else:
            request_data['create_time'] = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(request_data)
        self.collection.update_one({'create_time': request_data['create_time']}, {'$set': request_data}, upsert=True)
        return request_data