from .db import db
from .report import Report
from utils import request_event


class Event:
    def __init__(self):
        self.collection = db['event']

    def get(self, args):
        _, start, end, _ = request_event(args)
        data_list = []
        if start is not None and end is not None:
            data_list = self.collection.find({'start': {"$gte": start, "$lt": end}}, sort=[('id', 1)])
        return data_list

    def insert(self, args):
        title, start, end, event_id = request_event(args)
        request_data = {'title': title, 'start': start, 'end': end, 'id': event_id}

        if event_id is None:
            data = self.collection.find_one(sort=[('id', -1)])
            if data:
                request_data['id'] = data['id'] + 1
            else:
                request_data['id'] = 1
            self.collection.insert_one(request_data)
        else:
            self.collection.update_one({'id': event_id}, {'$set': request_data}, upsert=True)
        # calendar 일정이 변경 되면 그에 따라서 report 내용도 update 하기 위함
        self.update_report(start=start, end=end)

    def delete(self, args):
        title, _, _, event_id = request_event(args)

        data = self.collection.find_one({'id': event_id})
        start = data['start']
        end = data['end']
        self.collection.delete_one({'id': event_id})

        # calendar 일정이 변경 되면 그에 따라서 report 내용도 update 하기 위함
        self.update_report(start=start, end=end)
        return start, end

    def drop(self, args):
        start, end = self.delete(args)
        title, event_id, delta = request_delta(args)
        start = get_delta_day(start, delta=delta)
        end = get_delta_day(end, delta=delta)

        request_data = {'title': title, 'start': start, 'end': end, 'id': event_id}
        self.collection.update_one({'id': event_id}, {'$set': request_data}, upsert=True)

        # calendar 일정이 변경 되면 그에 따라서 report 내용도 update 하기 위함
        self.update_report(start=start, end=end)

    def update_report(self, start=None, end=None):
        if start is not None and end is not None:
            report = Report()
            report.update_date(start=start, end=end)