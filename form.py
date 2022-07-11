from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, DateField, SelectField, BooleanField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired, Optional, Length, EqualTo, Email

from config import EMPLOYEES_STATUS, APPROVAL_REASON


class UserCreateForm(FlaskForm):
    name = StringField('username', validators=[DataRequired(), Length(min=2, max=5)])
    email = EmailField('email', validators=[DataRequired(), Email()])
    password1 = PasswordField('password', validators=[
        DataRequired(), EqualTo('password2', '비밀번호가 일치하지 않습니다')])
    password2 = PasswordField('confirm password', validators=[DataRequired()])


class UserUpdateForm(FlaskForm):
    name = StringField('username', validators=[DataRequired(), Length(min=2, max=5)])
    email = EmailField('email', validators=[DataRequired(), Email()])
    is_admin = BooleanField('is_admin', validators=[Optional()])


class UserLoginForm(FlaskForm):
    email = EmailField('email', validators=[DataRequired(), Email()])
    password = PasswordField('password', validators=[DataRequired()])


class EmailForm(FlaskForm):
    email = EmailField('email', validators=[DataRequired(), Email()])


class PasswordResetForm(FlaskForm):
    password1 = PasswordField('password', validators=[
        DataRequired(), EqualTo('password2', '비밀번호가 일치하지 않습니다')])
    password2 = PasswordField('confirm password', validators=[DataRequired()])


class EmployeeSubmitForm(FlaskForm):
    # Optional - https://wtforms.readthedocs.io/en/2.3.x/validators/
    name = StringField('name', validators=[DataRequired(), Length(min=2, max=5)])
    employeeId = StringField('employeeId', validators=[DataRequired(), Length(min=1, max=4)])
    email = EmailField('email', validators=[Optional(), Email()])
    beginDate = DateField('beginDate', format='%Y-%m-%d', validators=(Optional(),))
    endDate = DateField('endDate', format='%Y-%m-%d', validators=(Optional(),))
    department = SelectField('department', choices=[(i, i) for i in EMPLOYEES_STATUS['department']])
    position = SelectField('position', choices=[(i, i) for i in EMPLOYEES_STATUS['position']])
    rank = StringField('rank', validators=[DataRequired(), Length(min=2, max=10)])
    regular = SelectField('regular', choices=[(i, i) for i in EMPLOYEES_STATUS['regular']])
    mode = SelectField('mode', choices=[(i, i) for i in EMPLOYEES_STATUS['mode']])


class PeriodSubmitForm(FlaskForm):
    start = DateField('Pick a Date', format='%Y-%m-%d')
    end = DateField('Pick a Date', format='%Y-%m-%d')


class DeviceSubmitForm(FlaskForm):
    mac = StringField('mac', validators=[DataRequired(), Length(min=2, max=30)])
    registerDate = DateField('registerDate', format='%Y-%m-%d', validators=(Optional(),))
    endDate = DateField('endDate', format='%Y-%m-%d', validators=(Optional(),))
    owner = StringField('owner', validators=[])
    device = StringField('device', validators=[])


class WriteSubmitForm(FlaskForm):
    name = StringField('name', validators=[DataRequired(), Length(min=2, max=5)])
    title = StringField('title', validators=[DataRequired(), Length(min=2, max=100)])
    content = StringField('content', validators=[DataRequired(), Length(min=2, max=1000)])


class ApprovalSubmitForm(FlaskForm):
    name = StringField('name', validators=[DataRequired(), Length(min=2, max=5)])
    email = EmailField('email', validators=[DataRequired(), Email()])
    approver = StringField('approver', validators=[DataRequired(), Length(min=2, max=5)])
    start = DateField('start', format='%Y-%m-%d', validators=(Optional(),))
    end = DateField('end', format='%Y-%m-%d', validators=(Optional(),))
    reason = SelectField('reason', choices=[(i, i) for i in APPROVAL_REASON])
    detail = StringField('detail', validators=[DataRequired(), Length(min=2, max=100)])


