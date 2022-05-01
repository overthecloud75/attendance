from .db import db
from utils import Page


class Board:
    def __init__(self):
        self.collection = db['board']

    def get(self, page=1, date=None):
        write_list = []
        get_page = Page(page)
        return get_page.paginate(write_list)