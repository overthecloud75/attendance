import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
try:
    from mainconfig import ACCOUNT, MAIL_SERVER
except Exception as e:
    # try your own Access_DB_PWD and ACCOUNT
    ACCOUNT = {
        'email': 'test@test.co.kr',
        'password': '*******',
    }
    MAIL_SERVER = {'host': 'smtp.office365.com', 'port': 587}
    SERVER_URL = 'http://127.0.0.1:5000/'
try:
    from mainconfig import CC
except Exception as e:
    # CC: cc email when notice email
    CC = None
    # CC = 'test@test.co.kr'


def send_email(email=None, subject=None, body=None, include_cc=False):
    mimemsg = MIMEMultipart()
    mimemsg['From'] = ACCOUNT['email']
    mimemsg['To'] = email
    if include_cc and CC is not None:
        mimemsg['Cc'] = CC
    mimemsg['Subject'] = subject
    mimemsg.attach(MIMEText(body, 'plain'))
    try:
        connection = smtplib.SMTP(host=MAIL_SERVER['host'], port=MAIL_SERVER['port'])
        connection.starttls()
        connection.login(ACCOUNT['email'], ACCOUNT['password'])
        connection.send_message(mimemsg)
        connection.quit()
        return True

    except Exception as e:
        print(e)
        return False
