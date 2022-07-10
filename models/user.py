from werkzeug.security import check_password_hash, generate_password_hash
import datetime
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

from .db import BasicModel
from utils import Page
from .mail import send_email
try:
    from mainconfig import SERVER_URL
except Exception as e:
    SERVER_URL = 'http://127.0.0.1:5000/'


class User(BasicModel):
    def __init__(self):
        super().__init__(model='user')

    def get_employee(self, request_data):
        collection = db['employees']
        return collection.find_one({'email': request_data['email'], 'name': request_data['name']})

    def confirm_token(self, token):
        error = None
        user_data = None
        try:
            email = self._token_to_email(token)
            if email:
                user_data = self._get_user({'email': email})
            else:
                error = 'The confirmation link is invalid or has expired'
        except:
            error = 'The confirmation link is invalid or has expired'
        return error, user_data

    def confirm_email(self, user_data):
        error = None
        if not user_data['email_confirmed']:
            self.collection.update_one({'email': user_data['email']}, {'$set': {'email_confirmed': True}}, upsert=True)
        elif user_data['email_confirmed']:
            error = 'Account already confirmed.'
        return error

    def signup(self, request_data):
        '''
            1. the first user is admin.
            2. from the second user, request_data['email'] must be in the employees data.
        '''
        error = None
        user_data = self._get_user(request_data)
        if user_data:
            error = '이미 존재하는 사용자입니다.'
        else:
            user_data = self.collection.find_one(sort=[('create_time', -1)])
            if user_data:
                employee_data = self.get_employee(request_data)
                if employee_data:
                    user_id = user_data['user_id'] + 1
                    request_data['is_admin'] = False
                else:
                    error = '가입 요건이 되지 않습니다.'
                    return error
            else:
                user_id = 1
                request_data['is_admin'] = True

            request_data['create_time'] = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            request_data['user_id'] = user_id
            if user_id == 1:
                request_data['email_confirmed'] = True
                self.collection.insert(request_data)
            else:
                result = self._signup_email(request_data['name'], request_data['email'])
                if result:
                    request_data['email_confirmed'] = False
                    self.collection.insert(request_data)
                else:
                    error = 'email이 보내지지 않았습니다.'
        return error

    def login(self, request_data):
        error = None
        user_data = self._get_user(request_data)
        if not user_data:
            error = "존재하지 않는 사용자입니다."
        elif not check_password_hash(user_data['password'], request_data['password']):
            error = "비밀번호가 올바르지 않습니다."
        return error, user_data

    def reset_password(self, request_data):
        error = None
        user_data = self._get_user({'email': request_data['email']})
        if user_data:
            result = self._reset_password_email(user_data['email'])
            if not result:
                error = 'email이 보내지지 않았습니다.'
        else:
            error = 'email 주소가 잘 못 되었습니다.'
        return error

    def change_password(self, request_data):
        self.collection.update_one({'email': request_data['email']}, {'$set': {'password': request_data['password']}}, upsert=True)

    def resend(self, request_data):
        error = None
        user_data = self._get_user({'email': request_data['email']})
        if user_data and not user_data['email_confirmed']:
            result = self._signup_email(user_data['name'], user_data['email'])
            if not result:
                error = 'email이 보내지지 않았습니다.'
        elif user_data and user_data['email_confirmed']:
            error = 'Account already confirmed.'
        else:
            error = 'email이 보내지지 않았습니다.'
        return error

    def get(self, page=1):
        data_list = self.collection.find(sort=[('name', 1)])
        get_page = Page(page)
        return get_page.paginate(data_list)

    def post(self, request_data):
        error = None
        user_data = self._get_user(request_data)
        if user_data:
           self.collection.update_one({'email': request_data['email']}, {'$set': request_data}, upsert=True)
        else:
            result = self._create_id_email(request_data['name'], request_data['email'])
            if result:
                user_data = self.collection.find_one(sort=[('create_time', -1)])
                request_data['user_id'] = user_data['user_id'] + 1
                request_data['password'] = generate_password_hash('123456')
                request_data['email_confirmed'] = True
                request_data['create_time'] = str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                self.collection.update_one({'email': request_data['email']}, {'$set': request_data}, upsert=True)
            else:
                error = 'email이 보내지지 않았습니다.'
        return error

    def _get_user(self, request_data):
        return self.collection.find_one({'email': request_data['email']})

    def _signup_email(self, name, email):
        token = self._generate_confirmation_token(email)
        subject = '[Attendance] 안녕하세요 %s님 site 가입을 환영합니다. \n '% (name)
        body = ' 안녕하세요 %s님 \n\n' \
               'Welcome! Thanks for signing up. \n' \
               'Please follow this link to activate your account: \n' \
               '%s \n' \
               % (name, SERVER_URL + 'user/email_confirm' + '/' + token)
        return send_email(email=email, subject=subject, body=body, include_cc=False)

    def _reset_password_email(self, email):
        token = self._generate_confirmation_token(email)
        subject = '[Attendance] password 재설정 확인'
        body = ' 안녕하세요 %s님 \n\n' \
               'Please follow this link to reset password: \n' \
               '%s \n' \
               % (email, SERVER_URL + 'user/reset_password' + '/' + token)
        return send_email(email=email, subject=subject, body=body, include_cc=False)

    def _create_id_email(self, name, email):
        subject = '[Attendance] 안녕하세요 %s님 id 생성이 되었습니다.. \n '% (name)
        body = ' 안녕하세요 %s님 \n\n' \
               'id가 생성이 되었습니다. \n' \
               '다음의 site 에서 password 변경 후 사용해 주세요.: \n' \
               '%s \n' \
               % (name, SERVER_URL + 'user/reset_password' + '/')
        return send_email(email=email, subject=subject, body=body, include_cc=False)

    def _generate_confirmation_token(self, email):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps(email)

    def _token_to_email(self, token, expiration=3600):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email = serializer.loads(token, max_age=expiration)
        return email



