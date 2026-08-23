import datetime
import json
from decimal import Decimal, InvalidOperation

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.core import signing
from functools import wraps
from django.conf import settings

from .jalali import (
    JALALI_MONTH_NAMES,
    WEEKDAY_NAMES,
    gregorian_to_jalali,
    jalali_month_length,
    jalali_to_gregorian,
    jalali_weekday,
    today_jalali,
)
from .models import Department, Holiday, WorkDay

VALID_STATUSES = {choice[0] for choice in WorkDay.STATUS_CHOICES}

# ترتیب طبیعی هفته در تقویم شمسی: شنبه تا جمعه. خود گرید با direction: rtl
# ستون شنبه را در سمت راست و جمعه را در سمت چپ نمایش می‌دهد.
WEEKDAY_NAMES_DISPLAY = WEEKDAY_NAMES


def _resolve_month(request):
    """سال/ماه شمسی درخواست‌شده را از querystring می‌خواند و بازه میلادی متناظرش را برمی‌گرداند."""
    today_jy, today_jm, today_jd = today_jalali()
    try:
        jy = int(request.GET.get('y', today_jy))
        jm = int(request.GET.get('m', today_jm))
    except (TypeError, ValueError):
        jy, jm = today_jy, today_jm

    if jm < 1:
        jm = 12
        jy -= 1
    elif jm > 12:
        jm = 1
        jy += 1

    month_length = jalali_month_length(jy, jm)
    gy1, gm1, gd1 = jalali_to_gregorian(jy, jm, 1)
    gy2, gm2, gd2 = jalali_to_gregorian(jy, jm, month_length)
    start_date = datetime.date(gy1, gm1, gd1)
    end_date = datetime.date(gy2, gm2, gd2)

    prev_m, prev_y = (jm - 1, jy) if jm > 1 else (12, jy - 1)
    next_m, next_y = (jm + 1, jy) if jm < 12 else (1, jy + 1)

    return {
        'jy': jy, 'jm': jm,
        'today': (today_jy, today_jm, today_jd),
        'month_length': month_length,
        'first_weekday': jalali_weekday(jy, jm, 1),
        'start_date': start_date,
        'end_date': end_date,
        'prev_y': prev_y, 'prev_m': prev_m,
        'next_y': next_y, 'next_m': next_m,
    }


def _compute_stats(work_days):
    """از یک iterable از رکوردهای WorkDay، تعداد هر وضعیت و مجموع اضافه‌کاری را می‌سازد."""
    stats = {
        'work': 0,
        'night': 0,
        'holiday_work': 0,
        'friday_work': 0,
        'leave': 0,
        'off': 0,
        'overtime_hours': Decimal('0'),
    }
    for wd in work_days:
        stats[wd.status] = stats.get(wd.status, 0) + 1
        if wd.overtime_hours:
            stats['overtime_hours'] += wd.overtime_hours
    return stats


def _holiday_map_for_month(jy, jm):
    """
    نگاشت day_num -> عنوان تعطیلی برای این ماه شمسی. هم تعطیلات «هرساله» (year=None)
    و هم تعطیلات مخصوص همین سال (مثل تعطیلات قمری که ادمین دستی وارد کرده) را شامل می‌شود.
    """
    holidays = Holiday.objects.filter(jalali_month=jm).filter(Q(jalali_year=None) | Q(jalali_year=jy))
    return {h.jalali_day: {'title': h.title, 'kind': h.kind, 'kind_display': h.get_kind_display()} for h in holidays}



MANAGEMENT_COOKIE = 'attendance_management_auth'
MANAGEMENT_COOKIE_SALT = 'attendance.management-auth'

def _is_management_admin(user):
    """Only real administrators may use the separate management area.

    A normal Django staff flag is intentionally NOT sufficient.  The
    management area contains cross-employee data and therefore requires an
    active superuser.  Accounts created through the AdminAccount proxy are
    also created as staff + superuser.
    """
    return bool(user and user.is_active and user.is_staff and user.is_superuser)


def _safe_next_url(request, candidate):
    candidate = (candidate or '').strip()
    if not candidate:
        return reverse('management_dashboard')
    allowed_hosts = {request.get_host()}
    if url_has_allowed_host_and_scheme(candidate, allowed_hosts=allowed_hosts, require_https=request.is_secure()):
        return candidate
    return reverse('management_dashboard')


def _get_management_user(request):
    raw = request.get_signed_cookie(MANAGEMENT_COOKIE, default=None, salt=MANAGEMENT_COOKIE_SALT)
    if not raw:
        return None
    try:
        user = get_user_model().objects.get(pk=int(raw), is_active=True, is_staff=True, is_superuser=True)
        return user if _is_management_admin(user) else None
    except (ValueError, TypeError, get_user_model().DoesNotExist):
        return None

def management_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        management_user = _get_management_user(request)
        if not management_user:
            from urllib.parse import urlencode
            login_url = reverse('management_login')
            return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")
        # Management has its own authentication realm. Never use request.user
        # (the employee Django session) to render or authorize management pages.
        request.management_user = management_user
        return view(request, *args, **kwargs)
    return wrapped

def calendar_access_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated or _get_management_user(request):
            return view(request, *args, **kwargs)
        return redirect('login')
    return wrapped

def _calendar_actor(request):
    # Management and employee authentication are separate realms. If a valid
    # management authentication cookie exists, it is the actor for management
    # navigation, even when an employee Django session also exists in the
    # browser. A View-As cookie can then explicitly switch the calendar target.
    management_user = _get_management_user(request)
    if management_user:
        return management_user
    if request.user.is_authenticated:
        return request.user
    return None

VIEW_AS_COOKIE = 'attendance_view_as'

def _get_view_as_user(request):
    if not _get_management_user(request):
        return None
    raw = request.get_signed_cookie(VIEW_AS_COOKIE, default=None, salt='attendance.view-as')
    if raw is None:
        return None
    try:
        return get_user_model().objects.get(pk=int(raw), is_active=True, is_staff=False)
    except (ValueError, TypeError, get_user_model().DoesNotExist):
        return None

def _effective_calendar_user(request):
    return _get_view_as_user(request) or _calendar_actor(request)

@calendar_access_required
def calendar_view(request):
    m = _resolve_month(request)
    effective_user = _effective_calendar_user(request)
    management_user = _get_management_user(request)
    view_as_id = effective_user.id if management_user and effective_user != management_user else None
    jy, jm = m['jy'], m['jm']
    today_jy, today_jm, today_jd = m['today']
    month_length = m['month_length']
    first_weekday = m['first_weekday']
    start_date, end_date = m['start_date'], m['end_date']

    records = {
        wd.date: wd
        for wd in WorkDay.objects.filter(user=effective_user, date__range=(start_date, end_date))
    }

    stats = _compute_stats(records.values())
    holiday_map = _holiday_map_for_month(jy, jm)

    days = []
    for day_num in range(1, month_length + 1):
        gy, gm, gd = jalali_to_gregorian(jy, jm, day_num)
        g_date = datetime.date(gy, gm, gd)
        record = records.get(g_date)
        days.append({
            'jalali_day': day_num,
            'gregorian': f'{gy:04d}/{gm:02d}/{gd:02d}',
            'iso_date': g_date.isoformat(),
            'is_today': (jy, jm, day_num) == (today_jy, today_jm, today_jd),
            'status': record.status if record else None,
            'overtime_hours': str(record.overtime_hours) if record and record.overtime_hours else '',
            'note': record.note if record and record.note else '',
            'checked': record is not None,
            'holiday_title': holiday_map.get(day_num, {}).get('title', ''),
            'holiday_kind': holiday_map.get(day_num, {}).get('kind', ''),
            'holiday_kind_display': holiday_map.get(day_num, {}).get('kind_display', ''),
            'is_past_or_today': (jy, jm, day_num) <= (today_jy, today_jm, today_jd),
        })

    # --- یادآوری روزهای ثبت‌نشده (فقط برای روزهایی که گذشته‌اند، تا امروز) ---
    is_future_month = (jy, jm) > (today_jy, today_jm)
    unrecorded_count = 0
    if not is_future_month:
        for day in days:
            if day['is_past_or_today'] and not day['checked'] and not day['holiday_title'] and not jalali_weekday(jy, jm, day['jalali_day']) == 6:
                unrecorded_count += 1

    # ساخت هفته‌ها در ترتیب طبیعی شنبه تا جمعه؛ CSS مسئول RTL بودن نمایش است.
    # این کار باعث می‌شود جای هر تاریخ دقیقاً زیر نام همان روز هفته بماند.
    weeks = []
    week = [None] * first_weekday
    for day in days:
        week.append(day)
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        while len(week) < 7:
            week.append(None)
        weeks.append(week)

    context = {
        'weeks': weeks,
        'weekday_names': WEEKDAY_NAMES_DISPLAY,
        'month_name': JALALI_MONTH_NAMES[jm - 1],
        'jy': jy,
        'jm': jm,
        'prev_y': m['prev_y'],
        'prev_m': m['prev_m'],
        'next_y': m['next_y'],
        'next_m': m['next_m'],
        'status_choices': WorkDay.STATUS_CHOICES,
        'stats': stats,
        'total_recorded_days': stats['work'] + stats['night'] + stats['holiday_work'] + stats['friday_work'] + stats['leave'] + stats['off'],
        'unrecorded_count': unrecorded_count,
        'effective_user': effective_user,
        'is_viewing_employee': bool(view_as_id),
    }
    return render(request, 'attendance/calendar.html', context)


@management_required
def admin_payroll_view(request):
    """
    صفحه مخصوص ادمین: کارکرد (تعداد روزهای هر وضعیت) همه کارمندان برای یک ماه شمسی مشخص.
    فقط برای کاربران فعالِ is_staff و is_superuser قابل مشاهده است (از پنل ادمین لینک می‌شود).
    قابل فیلتر بر اساس بخش سازمانی هم هست (querystring: dept=<id>).
    """
    User = get_user_model()
    m = _resolve_month(request)
    start_date, end_date = m['start_date'], m['end_date']

    employees = User.objects.filter(is_active=True, is_staff=False).order_by('username')

    dept_id = request.GET.get('dept', '').strip()
    if dept_id:
        try:
            employees = employees.filter(employee_profile__department_id=int(dept_id))
        except (ValueError, TypeError):
            pass

    employee_list = list(employees)
    employee_ids = [employee.id for employee in employee_list]
    work_days = WorkDay.objects.filter(
        user_id__in=employee_ids,
        date__range=(start_date, end_date),
    ).order_by('user_id', 'date')
    stats_by_user = {employee_id: _compute_stats([]) for employee_id in employee_ids}
    for work_day in work_days:
        stats = stats_by_user[work_day.user_id]
        stats[work_day.status] = stats.get(work_day.status, 0) + 1
        if work_day.overtime_hours:
            stats['overtime_hours'] += work_day.overtime_hours

    rows = []
    for employee in employee_list:
        stats = stats_by_user[employee.id]
        dept_name = ''
        profile = getattr(employee, 'employee_profile', None)
        if profile and profile.department:
            dept_name = profile.department.name
        rows.append({
            'employee': employee,
            'department': dept_name,
            'stats': stats,
        })

    context = {
        'month_name': JALALI_MONTH_NAMES[m['jm'] - 1],
        'jy': m['jy'],
        'jm': m['jm'],
        'prev_y': m['prev_y'],
        'prev_m': m['prev_m'],
        'next_y': m['next_y'],
        'next_m': m['next_m'],
        'rows': rows,
        'departments': Department.objects.all(),
        'selected_dept': dept_id,
    }
    return render(request, 'admin/payroll.html', context)


@management_required
def management_dashboard(request):
    User = get_user_model()
    m = _resolve_month(request)
    employees = User.objects.filter(is_active=True, is_staff=False).select_related('employee_profile__department').order_by('first_name', 'username')
    dept_id = request.GET.get('dept', '').strip()
    if dept_id:
        try:
            employees = employees.filter(employee_profile__department_id=int(dept_id))
        except (ValueError, TypeError):
            pass
    employee_list = list(employees)
    employee_ids = [employee.id for employee in employee_list]
    work_days = WorkDay.objects.filter(
        user_id__in=employee_ids,
        date__range=(m['start_date'], m['end_date']),
    ).order_by('user_id', 'date')
    stats_by_user = {employee_id: _compute_stats([]) for employee_id in employee_ids}
    for work_day in work_days:
        stats = stats_by_user[work_day.user_id]
        stats[work_day.status] = stats.get(work_day.status, 0) + 1
        if work_day.overtime_hours:
            stats['overtime_hours'] += work_day.overtime_hours

    holiday_count = Holiday.objects.filter(jalali_month=m['jm']).filter(
        Q(jalali_year=None) | Q(jalali_year=m['jy'])
    ).count()
    rows = [
        {'employee': employee, 'stats': stats_by_user[employee.id], 'holiday_count': holiday_count}
        for employee in employee_list
    ]
    return render(request, 'attendance/management/dashboard.html', {
        'rows': rows, 'departments': Department.objects.all(), 'selected_dept': dept_id,
        'month_name': JALALI_MONTH_NAMES[m['jm'] - 1], 'jy': m['jy'], 'jm': m['jm'],
        'prev_y': m['prev_y'], 'prev_m': m['prev_m'], 'next_y': m['next_y'], 'next_m': m['next_m'],
    })


@management_required
def management_employees(request):
    User = get_user_model()
    employees = User.objects.filter(is_active=True, is_staff=False).select_related('employee_profile__department').order_by('first_name', 'username')
    return render(request, 'attendance/management/employees.html', {'employees': employees})


@management_required
def management_employee(request, user_id):
    User = get_user_model()
    employee = get_object_or_404(User.objects.select_related('employee_profile__department'), pk=user_id, is_active=True, is_staff=False)
    m = _resolve_month(request)
    days = WorkDay.objects.filter(user=employee, date__range=(m['start_date'], m['end_date']))
    return render(request, 'attendance/management/employee.html', {
        'employee': employee, 'stats': _compute_stats(days), 'month_name': JALALI_MONTH_NAMES[m['jm'] - 1],
        'jy': m['jy'], 'jm': m['jm'], 'prev_y': m['prev_y'], 'prev_m': m['prev_m'], 'next_y': m['next_y'], 'next_m': m['next_m'],
    })


@management_required
@require_POST
def management_view_as(request, user_id):
    User = get_user_model()
    employee = get_object_or_404(User, pk=user_id, is_active=True, is_staff=False)
    response = redirect('calendar')
    response.set_signed_cookie(
        VIEW_AS_COOKIE, str(employee.id), salt='attendance.view-as',
        httponly=True, samesite='Lax',
        secure=getattr(settings, 'SESSION_COOKIE_SECURE', False), path='/',
    )
    return response


@management_required
@require_POST
def management_stop_view_as(request):
    response = redirect('management_dashboard')
    response.delete_cookie(VIEW_AS_COOKIE)
    return response

@management_required
@require_POST
def management_logout(request):
    response = redirect('management_login')
    response.delete_cookie(MANAGEMENT_COOKIE, path='/')
    response.delete_cookie(VIEW_AS_COOKIE, path='/')
    return response

def management_login(request):
    requested_next = request.GET.get('next', request.POST.get('next', ''))
    safe_next = _safe_next_url(request, requested_next)
    if _get_management_user(request):
        return redirect(safe_next)
    error = None
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if _is_management_admin(user):
            response = redirect(safe_next)
            response.set_signed_cookie(
                MANAGEMENT_COOKIE, str(user.pk), salt=MANAGEMENT_COOKIE_SALT,
                httponly=True, samesite='Lax',
                secure=getattr(settings, 'SESSION_COOKIE_SECURE', False), path='/',
            )
            return response
        error = 'این حساب اجازه ورود به پنل مدیریت را ندارد.' if user and user.is_active else 'نام کاربری یا رمز عبور مدیر معتبر نیست.'
    return render(request, 'attendance/management/login.html', {'error': error, 'next': requested_next})


@calendar_access_required
@require_POST
def save_day(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'داده ارسالی نامعتبر است.'}, status=400)

    iso_date = payload.get('date')
    status = (payload.get('status') or '').strip()
    overtime_raw = (payload.get('overtime_hours') or '').strip()
    note = (payload.get('note') or '').strip()

    if not iso_date:
        return JsonResponse({'ok': False, 'error': 'تاریخ مشخص نشده است.'}, status=400)

    try:
        the_date = datetime.date.fromisoformat(iso_date)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'فرمت تاریخ نامعتبر است.'}, status=400)

    if status and status not in VALID_STATUSES:
        return JsonResponse({'ok': False, 'error': 'وضعیت انتخاب‌شده نامعتبر است.'}, status=400)

    overtime_hours = None
    if overtime_raw:
        try:
            overtime_hours = Decimal(overtime_raw)
            if overtime_hours < 0 or overtime_hours > Decimal('24'):
                raise InvalidOperation
        except InvalidOperation:
            return JsonResponse({'ok': False, 'error': 'ساعت اضافه‌کاری نامعتبر است.'}, status=400)

    # حداقل یکی از دو فیلد (وضعیت/اضافه‌کاری) باید پر شده باشد؛ یادداشت به‌تنهایی کافی نیست
    if not status and not overtime_hours:
        return JsonResponse(
            {'ok': False, 'error': 'باید حداقل یکی از وضعیت روز یا ساعت اضافه‌کاری را وارد کنید.'},
            status=400,
        )

    # اگر فقط ساعت اضافه‌کاری وارد شده و وضعیتی انتخاب نشده، طبق تعریف پروژه پیش‌فرض «off» است
    final_status = status if status else WorkDay.STATUS_OFF

    work_day, _created = WorkDay.objects.update_or_create(
        user=_effective_calendar_user(request),
        date=the_date,
        defaults={
            'status': final_status,
            'overtime_hours': overtime_hours if overtime_hours is not None else 0,
            'note': note,
        },
    )

    return JsonResponse({
        'ok': True,
        'date': iso_date,
        'status': work_day.status,
        'status_display': work_day.get_status_display(),
        'overtime_hours': str(work_day.overtime_hours) if work_day.overtime_hours else '',
        'note': work_day.note,
    })


@calendar_access_required
@require_POST
def delete_day(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'داده ارسالی نامعتبر است.'}, status=400)

    iso_date = payload.get('date')
    if not iso_date:
        return JsonResponse({'ok': False, 'error': 'تاریخ مشخص نشده است.'}, status=400)

    try:
        the_date = datetime.date.fromisoformat(iso_date)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'فرمت تاریخ نامعتبر است.'}, status=400)

    WorkDay.objects.filter(user=_effective_calendar_user(request), date=the_date).delete()
    return JsonResponse({'ok': True, 'date': iso_date})
