import datetime
from mainconfig import holidays

def paginate(page, per_page, count):
    offset = (page - 1) * per_page
    total_pages = int(count / per_page) + 1
    screen_pages = 10

    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    start_page = (page - 1) // screen_pages * screen_pages + 1

    pages = []
    prev_num = start_page - screen_pages
    next_num = start_page + screen_pages

    if start_page - screen_pages > 0:
        has_prev = True
    else:
        has_prev = False
    if start_page + screen_pages > total_pages:
        has_next = False
    else:
        has_next = True
    if total_pages > screen_pages + start_page:
        for i in range(screen_pages):
            pages.append(i + start_page)
    elif total_pages < screen_pages:
        for i in range(total_pages):
            pages.append(i + start_page)
    else:
        for i in range(total_pages - start_page + 1):
            pages.append(i + start_page)
    paging = {'page':page,
              'has_prev':has_prev,
              'has_next':has_next,
              'prev_num':prev_num,
              'next_num':next_num,
              'count':count,
              'offset':offset,
              'pages':pages,
              'screen_pages':screen_pages,
              'total_pages':total_pages
              }
    return paging

def checkHoliday(date):
    isHoliday = False
    month = date[5:7]
    day = date[8:]
    monthDay = month + day
    if monthDay in holidays:
        isHoliday = True
    date = datetime.datetime(int(date[0:4]), int(month), int(day), 1, 0, 0)  # str -> datetime으로 변환
    if date.weekday() == 5 or date.weekday() == 6:
        isHoliday = True
    return isHoliday

def checkTime():
    today = datetime.date.today()
    now = datetime.datetime.now()
    hour = now.hour
    today = today.strftime("%Y-%m-%d")
    '''
    month = now.month
    year = now.year
    firstDay = datetime.datetime(year, month, 1, 0, 0, 0)
    firstDay = firstDay.strftime("%m/%d/%Y")
    lastDay = datetime.datetime(year, month + 1, 1, 0, 0, 0) - datetime.timedelta(seconds=30)
    lastDay = lastDay.strftime("%m/%d/%Y")
    thisMonth = {'firstDay':firstDay, 'lastDay':lastDay}'''
    return hour, today

def request_get(request_data):
    page = int(request_data.get('page', 1))
    name = request_data.get('name', None)
    startDate = request_data.get('startDate', None)
    if startDate:
        if startDate[4] != '-':
            startDate = startDate[6:] + '-' + startDate[:2] + '-' + startDate[3:5]
    endDate = request_data.get('endDate', None)
    if endDate:
        if endDate[4] != '-':
            endDate = endDate[6:] + '-' + endDate[:2] + '-' + endDate[3:5]
    return page, name, startDate, endDate
