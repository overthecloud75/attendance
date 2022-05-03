from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, DateField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired, Optional, Length, EqualTo, Email


class UserCreateForm(FlaskForm):
    name = StringField('username', validators=[DataRequired(), Length(min=2, max=5)])
    email = EmailField('email', validators=[DataRequired(), Email()])
    password1 = PasswordField('password', validators=[
        DataRequired(), EqualTo('password2', '비밀번호가 일치하지 않습니다')])
    password2 = PasswordField('confirm password', validators=[DataRequired()])


class UserLoginForm(FlaskForm):
    email = EmailField('email', validators=[DataRequired(), Email()])
    password = PasswordField('password', validators=[DataRequired()])


class ResendForm(FlaskForm):
    email = EmailField('email', validators=[DataRequired(), Email()])


class EmployeeSubmitForm(FlaskForm):
    # Optional - https://wtforms.readthedocs.io/en/2.3.x/validators/
    name = StringField('name', validators=[DataRequired(), Length(min=2, max=5)])
    department = StringField('department', validators=[DataRequired(), Length(min=2, max=10)])
    rank = StringField('rank', validators=[DataRequired(), Length(min=2, max=10)])
    employeeId = StringField('employeeId', validators=[Optional(), Length(min=1, max=4)])
    beginDate = DateField('beginDate', format='%Y-%m-%d', validators=(Optional(),))
    endDate = DateField('endDate', format='%Y-%m-%d', validators=(Optional(),))
    email = EmailField('email', validators=[Optional(), Email()])
    regular = StringField('regular', validators=[])
    status = StringField('status', validators=[])


class PeriodSubmitForm(FlaskForm):
    start = DateField('Pick a Date', format='%Y-%m-%d')
    end = DateField('Pick a Date', format='%Y-%m-%d')


class DateSubmitForm(FlaskForm):
    start = DateField('Pick a Date', format='%Y-%m-%d')


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

