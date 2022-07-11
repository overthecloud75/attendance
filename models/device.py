from datetime import date

from .db import BasicModel
from .employee import Employee
from utils import check_time, get_date_several_months_before, Page


# Device
class Device(BasicModel):
    def __init__(self):
        super().__init__(model='device')
        self.employee = Employee()

    def get(self, page=1, date=None):
        if date is None:
            device_list = self.collection.find()
        else:
            date = get_date_several_months_before(date, delta=2)
            device_list = self.collection.find({'endDate': {"$gt": date}})
        if page=='all':
            return device_list
        else:
            get_page = Page(page)
            return get_page.paginate(device_list)

    def new_post(self, request_data): # new device 발견인 경우
        register_date = date.today().strftime('%Y-%m-%d')   # 최초 등록 시간 기록
        request_data = {'mac': request_data['mac'], 'registerDate': register_date, 'endDate': register_date, 'owner': None, 'device': None}
        self.collection.update_one({'mac': request_data['mac']}, {'$set': request_data}, upsert=True)

    def post(self, request_data):
        if 'owner' in request_data and request_data['owner'] == 'None':
            request_data['owner'] = None
        if 'device' in request_data and request_data['device'] == 'None':
            request_data['device'] = None
        if 'owner' in request_data and request_data['owner']:
            employees_list = self.employee.get(page='all')
            for employee in employees_list:
                name = employee['name']
                employee_id = employee['employeeId']
                if request_data['owner'] == name:
                    request_data['employeeId'] = employee_id
        self.collection.update_one({'mac': request_data['mac']}, {'$set': request_data}, upsert=True)

    def by_employees(self, date=None):
        device_list = self.get(page='all', date=date)
        device_dict = {}
        for device in device_list:
            if 'owner' in device:
                if device['owner']:
                    # device가 여러개 있는 경우
                    if device['owner'] in device_dict:
                        device_dict[device['owner']].append(device['mac'])
                    else:
                        device_dict[device['owner']] = [device['mac']]
        return device_dict

