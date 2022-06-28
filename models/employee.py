from .db import db
from utils import Page


class Employee:
    def __init__(self):
        self.collection = db['employees']

    def get(self, page=1, name=None, date=None):
        if name:
            employee = self.collection.find_one({'name': name})
            return employee
        elif page == 'all':
            employees = self.collection.find(sort=[('name', 1)])
            employees_list = []
            for employee in employees:
                if 'email' in employee and employee['email']:
                    email = employee['email']
                else:
                    email = None
                # 퇴사하지 않은 직원만 포함하기 위해서
                if employee['regular'] != '퇴사':
                    employee_info = {'name': employee['name'], 'employeeId': employee['employeeId'], 'email': email, 'regular': employee['regular'], 'status': employee['status']}
                    if 'beginDate' not in employee and 'endDate' not in employee:
                        employees_list.append(employee_info)
                    elif 'beginDate' in employee and date and date >= employee['beginDate'] and 'endDate' not in employee:
                        employees_list.append(employee_info)
                    else:
                        if 'endDate' in employee and date and date <= employee['endDate']:
                            employees_list.append(employee_info)
            return employees_list
        else:
            data_list = self.collection.find(sort=[('department', 1), ('name', 1)])
            get_page = Page(page)
            return get_page.paginate(data_list)

    def post(self, request_data):
        if 'employeeId' not in request_data:
            data = self.collection.find_one(sort=[('employeeId', -1)])
            request_data['employeeId'] = data['employeeId'] + 1
        self.collection.update_one({'name': request_data['name'], 'employeeId': request_data['employeeId']},
                                   {'$set': request_data}, upsert=True)
