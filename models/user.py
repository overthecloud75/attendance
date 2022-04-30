from werkzeug.security import check_password_hash
import datetime
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

from .db import db
from .mail import send_email
try:
    from mainconfig import SERVER_URL
except Exception as e:
    SERVER_URL = 'http://127.0.0.1:5000/'


class User:
    def __init__(self):
        self.collection = db['user']
        self.error = None

    def get_user(self, request_data):
        return self.collection.find_one({'email': request_data['email']})

    def get_employee(self, request_data):
        collection = db['employees']
        return collection.find_one({'email': request_data['email'], 'name': request_data['name']})

    def generate_confirmation_token(self, email):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps(email)

    def confirm_token(self, token, expiration=3600):
        error = None
        user_data = None
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            email = serializer.loads(
                token,
                max_age=expiration
            )
            if email:
                user_data = self.get_user({'email': email})
                if user_data and not user_data['email_confirmed']:
                    self.collection.update_one({'email': email}, {'$set': {'email_confirmed': True}}, upsert=True)
                elif user_data and user_data['email_confirmed']:
                    error = 'Account already confirmed.'
            else:
                error = 'The confirmation link is invalid or has expired'
        except:
            error = 'The confirmation link is invalid or has expired'
        return error, user_data

    def signup(self, request_data):
        '''
            1. the first user is admin.
            2. from the second user, request_data['email'] must be in the employees data.
        '''
        user_data = self.get_user(request_data)
        if user_data:
            self.error = '이미 존재하는 사용자입니다.'
        else:
            user_data = self.collection.find_one(sort=[('create_time', -1)])
            if user_data:
                employee_data = self.get_employee(request_data)
                if employee_data:
                    user_id = user_data['user_id'] + 1
                    request_data['is_admin'] = False
                else:
                    self.error = '가입 요건이 되지 않습니다.'
                    return self.error
            else:
                user_id = 1
                request_data['is_admin'] = True

            request_data['create_time'] = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            token = self.generate_confirmation_token(request_data['email'])
            result = self.signup_email(request_data, token=token)
            if result:
                request_data['user_id'] = user_id
                request_data['email_confirmed'] = False
                self.collection.insert(request_data)
            else:
                self.error = 'email이 보내지지 않았습니다.'
        return self.error

    def login(self, request_data):
        user_data = self.get_user(request_data)
        if not user_data:
            self.error = "존재하지 않는 사용자입니다."
        elif not check_password_hash(user_data['password'], request_data['password']):
            self.error = "비밀번호가 올바르지 않습니다."
        return self.error, user_data

    def resend(self, email):
        error = None
        user_data = self.get_user({'email': email})
        if user_data:
            request_data = {'name': user_data['name'], 'email': user_data['email']}
            token = self.generate_confirmation_token(email)
            result = self.signup_email(request_data, token=token)
            return error, result
        else:
            return 'email 주소가 잘 못 되었습니다.', False

    def signup_email(self, request_data, token=None):
        name = request_data['name']
        email = request_data['email']
        subject = '[Attendance] 안녕하세요 %s님 site 가입을 환영합니다. \n ' \
                  % (name)
        body = ' 안녕하세요 %s님 \n' \
               'Welcome! Thanks for signing up. Please follow this link to activate your account: \n' \
               '%s \n' \
               % (name, SERVER_URL + 'confirm' + '/' + token)
        return send_email(email=email, subject=subject, body=body, include_cc=False)


