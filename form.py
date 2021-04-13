from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, DateField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired, Length, EqualTo, Email

class UserCreateForm(FlaskForm):
    name = StringField('사용자이름', validators=[DataRequired(), Length(min=2, max=5)])
    email = EmailField('이메일', validators=[DataRequired(), Email()])
    password1 = PasswordField('비밀번호', validators=[
        DataRequired(), EqualTo('password2', '비밀번호가 일치하지 않습니다')])
    password2 = PasswordField('비밀번호확인', validators=[DataRequired()])

class UserLoginForm(FlaskForm):
    email = EmailField('이메일', validators=[DataRequired(), Email()])
    password = PasswordField('비밀번호', validators=[DataRequired()])

class EmployeesSubmitForm(FlaskForm):
    name = StringField('name', validators=[DataRequired(), Length(min=2, max=5)])

class DateSubmitForm(FlaskForm):
    startDate = DateField('Pick a Date', format="%m/%d/%Y")
    endDate = DateField('Pick a Date', format="%m/%d/%Y")
