"""
توابع تبدیل تاریخ میلادی <-> شمسی (جلالی) بدون نیاز به کتابخانه خارجی.
الگوریتم امتحان‌شده و تست‌شده (round-trip) برای بازه سال‌های ۱۹۰۰ تا ۲۱۰۰ میلادی.
"""
import datetime

J_DAYS_IN_MONTH = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
G_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

JALALI_MONTH_NAMES = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]

# شنبه تا جمعه - این ترتیب همان ترتیبی است که در تقویم نمایش داده می‌شود
WEEKDAY_NAMES = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه']


def _is_gregorian_leap(gy):
    return (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)


def gregorian_to_jalali(gy, gm, gd):
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    for i in range(gm2):
        g_day_no += G_DAYS_IN_MONTH[i]
    if gm2 > 1 and _is_gregorian_leap(gy):
        g_day_no += 1
    g_day_no += gd2

    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    for i in range(11):
        if j_day_no < J_DAYS_IN_MONTH[i]:
            jm = i + 1
            jd = j_day_no + 1
            break
        j_day_no -= J_DAYS_IN_MONTH[i]
    else:
        jm = 12
        jd = j_day_no + 1

    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    jy2 = jy - 979
    jm2 = jm - 1
    jd2 = jd - 1
    j_day_no = 365 * jy2 + (jy2 // 33) * 8 + ((jy2 % 33 + 3) // 4)
    for i in range(jm2):
        j_day_no += J_DAYS_IN_MONTH[i]
    j_day_no += jd2

    g_day_no = j_day_no + 79
    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no %= 146097

    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1

    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461

    if g_day_no >= 366:
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no %= 365

    for i in range(12):
        days = G_DAYS_IN_MONTH[i]
        if i == 1 and _is_gregorian_leap(gy):
            days = 29
        if g_day_no < days:
            gm = i + 1
            gd = g_day_no + 1
            break
        g_day_no -= days

    return gy, gm, gd


def is_jalali_leap(jy):
    """آیا سال شمسی جy کبیسه است (اسفند ۳۰ روزه دارد)؟"""
    gy1, gm1, gd1 = jalali_to_gregorian(jy, 12, 30)
    gy2, gm2, gd2 = jalali_to_gregorian(jy + 1, 1, 1)
    d1 = datetime.date(gy1, gm1, gd1)
    d2 = datetime.date(gy2, gm2, gd2)
    return (d2 - d1).days == 1


def jalali_month_length(jy, jm):
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if is_jalali_leap(jy) else 29


def jalali_weekday(jy, jm, jd):
    """برمی‌گرداند اندیس روز هفته با شنبه = 0 تا جمعه = 6"""
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    py_weekday = datetime.date(gy, gm, gd).weekday()  # Monday=0 ... Sunday=6
    # می‌خواهیم شنبه=0 ... جمعه=6
    # پایتون: دوشنبه=0, سه‌شنبه=1, چهارشنبه=2, پنجشنبه=3, جمعه=4, شنبه=5, یکشنبه=6
    mapping = {5: 0, 6: 1, 0: 2, 1: 3, 2: 4, 3: 5, 4: 6}
    return mapping[py_weekday]


def today_jalali():
    t = datetime.date.today()
    return gregorian_to_jalali(t.year, t.month, t.day)


def to_persian_digits(value):
    """تبدیل ارقام انگلیسی به ارقام فارسی برای نمایش زیباتر"""
    fa_digits = '۰۱۲۳۴۵۶۷۸۹'
    return ''.join(fa_digits[int(ch)] if ch.isdigit() else ch for ch in str(value))
