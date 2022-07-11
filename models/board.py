import datetime

from .db import BasicModel
from utils import Page


class Board(BasicModel):
    def __init__(self):
        super().__init__(model='board')

    def get(self, page=1, start=None, end=None):
        data_list = self.collection.find(sort=[('create_time', -1)])
        get_page = Page(page)
        return get_page.paginate(data_list)

    def post(self, request_data):
        if 'create_time' in request_data:
            request_data['update_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        else:
            request_data['create_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.collection.update_one({'create_time': request_data['create_time']}, {'$set': request_data}, upsert=True)
        return request_data