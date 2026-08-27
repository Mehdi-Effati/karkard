import datetime
import json
from decimal import Decimal, InvalidOperation

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
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
from .models import (
    Department, Holiday, WorkDay, EmployeeProfile, SalaryDeduction,
    MANAGEMENT_PERMISSION_KEYS,
)

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



def _parse_user_date(value, default=None):
    """Parse user-facing Jalali dates while preserving ISO Gregorian API/test input.

    The UI sends Jalali dates (e.g. 1405/06/01), while internal links/tests may
    send ISO Gregorian dates (e.g. 2026-08-22).  We must distinguish them before
    converting; treating every four-digit year as Jalali would turn a Gregorian
    year such as 2026 into a completely different date.
    """
    raw = (value or '').strip()
    if not raw:
        return default or datetime.date.today()

    try:
        # ISO/Gregorian input: YYYY-MM-DD. This is also what internal URLs and
        # JSON/API-style clients use, so it must remain unambiguous.
        if '-' in raw:
            parsed = datetime.date.fromisoformat(raw)
            return parsed

        normalized = raw.replace('\u06cc', '/').replace('\u06f0', '0')
        parts = normalized.split('/')
        nums = [int(x) for x in parts]
        if len(nums) != 3:
            raise ValueError('invalid date')

        year, month, day = nums
        # Three-part slash dates are the user-facing Jalali format.
        if 1200 <= year <= 1600:
            gy, gm, gd = jalali_to_gregorian(year, month, day)
            return datetime.date(gy, gm, gd)

        # Accept slash-form Gregorian dates for backwards compatibility.
        return datetime.date(year, month, day)
    except (ValueError, TypeError, IndexError):
        raise ValueError('invalid date')

def _jalali_date_text(value):
    if not value:
        value = datetime.date.today()
    jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
    return f'{jy:04d}/{jm:02d}/{jd:02d}'

def _build_jalali_calendar(user, m):
    records = {
        wd.date: wd for wd in WorkDay.objects.filter(
            user=user, date__range=(m['start_date'], m['end_date'])
        )
    }
    holiday_map = _holiday_map_for_month(m['jy'], m['jm'])
    days = []
    for day_num in range(1, m['month_length'] + 1):
        gy, gm, gd = jalali_to_gregorian(m['jy'], m['jm'], day_num)
        g_date = datetime.date(gy, gm, gd)
        record = records.get(g_date)
        days.append({
            'jalali_day': day_num,
            'jalali_date': f"{m['jy']:04d}/{m['jm']:02d}/{day_num:02d}",
            'gregorian': f'{gy:04d}/{gm:02d}/{gd:02d}',
            'iso_date': g_date.isoformat(),
            'status': record.status if record else None,
            'status_display': record.get_status_display() if record else '',
            'overtime_hours': str(record.overtime_hours) if record and record.overtime_hours else '',
            'note': record.note if record and record.note else '',
            'checked': record is not None,
            'approval_status': record.approval_status if record else '',
            'approval_status_display': record.get_approval_status_display() if record else '',
            'rejection_reason': record.rejection_reason if record else '',
            'record_id': record.id if record else '',
            'holiday_title': holiday_map.get(day_num, {}).get('title', ''),
            'holiday_kind': holiday_map.get(day_num, {}).get('kind', ''),
        })
    weeks = []
    week = [None] * m['first_weekday']
    for day in days:
        week.append(day)
        if len(week) == 7:
            weeks.append(week)
            week = []
    if week:
        week += [None] * (7 - len(week))
        weeks.append(week)
    return weeks


MANAGEMENT_COOKIE = 'attendance_management_auth'
MANAGEMENT_COOKIE_SALT = 'attendance.management-auth'

def _is_management_user(user):
    """Return True for a Django superuser or a designated accountant.

    Accountants are Django staff users, but they are not superusers. They remain
    normal employees for their own attendance calendar while a separate signed
    management cookie grants only the management permissions assigned to them.
    """
    if not user or not user.is_active:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'employee_profile', None)
    return bool(user.is_staff and profile and profile.is_accountant)


def _is_management_admin(user):
    # Backwards-compatible alias used by a few existing callers/tests.
    return _is_management_user(user)


def _effective_management_permissions(user):
    if not _is_management_user(user):
        return []
    if user.is_superuser:
        return list(MANAGEMENT_PERMISSION_KEYS)
    profile = getattr(user, 'employee_profile', None)
    if not profile:
        return []
    # An accountant with an empty permission list gets the default full access.
    # This keeps the role safe for existing records created before granular
    # permissions were introduced.
    return list(profile.management_permissions or MANAGEMENT_PERMISSION_KEYS)


def _management_permission(user, permission):
    return permission in _effective_management_permissions(user)


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
        user = get_user_model().objects.select_related('employee_profile').get(pk=int(raw), is_active=True)
        return user if _is_management_user(user) else None
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
        request.management_user = management_user
        return view(request, *args, **kwargs)
    return wrapped


def management_permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            management_user = _get_management_user(request)
            if not management_user:
                from urllib.parse import urlencode
                login_url = reverse('management_login')
                return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")
            request.management_user = management_user
            if not _management_permission(management_user, permission):
                return render(request, 'attendance/management/forbidden.html', {
                    'required_permission': permission,
                }, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator

def management_any_permission_required(*permissions):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            management_user = _get_management_user(request)
            if not management_user:
                from urllib.parse import urlencode
                login_url = reverse('management_login')
                return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")
            request.management_user = management_user
            if not any(_management_permission(management_user, p) for p in permissions):
                return render(request, 'attendance/management/forbidden.html', {'required_permission': ' / '.join(permissions)}, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator

def calendar_access_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated or _get_view_as_user(request):
            return view(request, *args, **kwargs)
        return redirect('login')
    return wrapped

def _calendar_actor(request):
    # The employee realm and the management realm are intentionally independent.
    # Opening/logging into Management must NEVER replace request.user. The only
    # way Management can enter an employee calendar is the explicit View-As
    # action, represented by the signed VIEW_AS_COOKIE.
    if request.user.is_authenticated:
        return request.user
    return None

VIEW_AS_COOKIE = 'attendance_view_as'

def _get_view_as_user(request):
    management_user = _get_management_user(request)
    if not management_user or not _management_permission(management_user, 'workdays_edit'):
        return None
    raw = request.get_signed_cookie(VIEW_AS_COOKIE, default=None, salt='attendance.view-as')
    if raw is None:
        return None
    try:
        return _management_employee_queryset().get(pk=int(raw))
    except (ValueError, TypeError, get_user_model().DoesNotExist):
        return None

def _effective_calendar_user(request):
    # Explicit View-As always wins. Otherwise use the normal employee session.
    return _get_view_as_user(request) or _calendar_actor(request)

@calendar_access_required
def calendar_view(request):
    m = _resolve_month(request)
    effective_user = _effective_calendar_user(request)
    management_user = _get_management_user(request)
    view_as_id = effective_user.id if _get_view_as_user(request) else None
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
    deduction_total = SalaryDeduction.objects.filter(
        user=effective_user, date__range=(start_date, end_date)
    ).aggregate(total=Sum('amount')).get('total') or Decimal('0')

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
            'approval_status': record.approval_status if record else '',
            'approval_status_display': record.get_approval_status_display() if record else '',
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
        'deduction_total': deduction_total,
    }
    return render(request, 'attendance/calendar.html', context)


def _management_employee_queryset():
    User = get_user_model()
    # کارمند عادی + حسابدار staff باید هر دو در لیست کارکنان باشند؛
    # staffهای فنی که حسابدار نیستند و superuserها نباید کارمند محسوب شوند.
    return User.objects.filter(
        Q(is_active=True, is_superuser=False),
        Q(is_staff=False) | Q(is_staff=True, employee_profile__is_accountant=True),
    ).select_related('employee_profile__department').order_by('first_name', 'username')

def _approval_queryset_for_manager(manager):
    qs = WorkDay.objects.filter(approval_status=WorkDay.APPROVAL_PENDING).select_related(
        'user', 'user__employee_profile__department'
    ).order_by('date', 'user__first_name', 'user__username')
    if manager.is_superuser:
        return qs
    profile = getattr(manager, 'employee_profile', None)
    if profile and profile.department_id:
        return qs.filter(user__employee_profile__department_id=profile.department_id)
    return qs


def _monthly_deductions(user_ids, start_date, end_date):
    totals = {user_id: Decimal('0') for user_id in user_ids}
    if not user_ids:
        return totals
    for row in SalaryDeduction.objects.filter(
        user_id__in=user_ids, date__range=(start_date, end_date)
    ).values('user_id').annotate(total=Sum('amount')):
        totals[row['user_id']] = row['total'] or Decimal('0')
    return totals


@staff_member_required
def admin_employee_calendar(request, user_id):
    if not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    request.management_user = request.user
    request.management_permissions = list(MANAGEMENT_PERMISSION_KEYS)
    employee = get_object_or_404(_management_employee_queryset(), pk=user_id)
    m = _resolve_month(request)
    return render(request, 'attendance/management/employee_calendar.html', {
        'employee': employee, 'weeks': _build_jalali_calendar(employee, m),
        'weekday_names': WEEKDAY_NAMES_DISPLAY,
        'month_name': JALALI_MONTH_NAMES[m['jm'] - 1], 'jy': m['jy'], 'jm': m['jm'],
        'prev_y': m['prev_y'], 'prev_m': m['prev_m'], 'next_y': m['next_y'], 'next_m': m['next_m'],
        'status_choices': WorkDay.STATUS_CHOICES, 'can_approve': bool(request.user.is_superuser),
        'approval_mode': True, 'admin_mode': True,
    })

@staff_member_required
@require_POST
def admin_approve_workday(request, workday_id):
    if not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    work_day = get_object_or_404(WorkDay.objects.filter(user__in=_management_employee_queryset()), pk=workday_id)
    work_day.approval_status = WorkDay.APPROVAL_APPROVED
    work_day.approved_by = request.user
    work_day.approved_at = timezone.now()
    work_day.rejection_reason = ''
    work_day.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'])
    return redirect('admin_employee_calendar', user_id=work_day.user_id)

@staff_member_required
@require_POST
def admin_reject_workday(request, workday_id):
    if not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    work_day = get_object_or_404(WorkDay.objects.filter(user__in=_management_employee_queryset()), pk=workday_id)
    work_day.approval_status = WorkDay.APPROVAL_REJECTED
    work_day.approved_by = request.user
    work_day.approved_at = timezone.now()
    work_day.rejection_reason = (request.POST.get('reason') or 'نیاز به بررسی مجدد دارد.')[:2000]
    work_day.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'])
    return redirect('admin_employee_calendar', user_id=work_day.user_id)


@management_permission_required('payroll')
def admin_payroll_view(request):
    """
    صفحه مخصوص ادمین: کارکرد (تعداد روزهای هر وضعیت) همه کارمندان برای یک ماه شمسی مشخص.
    فقط برای کاربران فعالِ is_staff و is_superuser قابل مشاهده است (از پنل ادمین لینک می‌شود).
    قابل فیلتر بر اساس بخش سازمانی هم هست (querystring: dept=<id>).
    """
    User = get_user_model()
    m = _resolve_month(request)
    start_date, end_date = m['start_date'], m['end_date']

    employees = _management_employee_queryset()

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
        approval_status=WorkDay.APPROVAL_APPROVED,
    ).order_by('user_id', 'date')
    stats_by_user = {employee_id: _compute_stats([]) for employee_id in employee_ids}
    for work_day in work_days:
        stats = stats_by_user[work_day.user_id]
        stats[work_day.status] = stats.get(work_day.status, 0) + 1
        if work_day.overtime_hours:
            stats['overtime_hours'] += work_day.overtime_hours

    deduction_by_user = _monthly_deductions(employee_ids, start_date, end_date)
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
            'deduction_total': deduction_by_user[employee.id],
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


@management_permission_required('dashboard')
def management_dashboard(request):
    m = _resolve_month(request)
    employees = _management_employee_queryset()
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
    approval_by_user = {employee_id: {'pending': 0, 'approved': 0, 'rejected': 0} for employee_id in employee_ids}
    for work_day in work_days:
        stats = stats_by_user[work_day.user_id]
        stats[work_day.status] = stats.get(work_day.status, 0) + 1
        if work_day.overtime_hours:
            stats['overtime_hours'] += work_day.overtime_hours
        approval_by_user[work_day.user_id][work_day.approval_status] = approval_by_user[work_day.user_id].get(work_day.approval_status, 0) + 1

    deduction_by_user = _monthly_deductions(employee_ids, m['start_date'], m['end_date'])
    holiday_count = Holiday.objects.filter(jalali_month=m['jm']).filter(
        Q(jalali_year=None) | Q(jalali_year=m['jy'])
    ).count()
    rows = [
        {
            'employee': employee,
            'stats': stats_by_user[employee.id],
            'holiday_count': holiday_count,
            'deduction_total': deduction_by_user[employee.id],
            'approvals': approval_by_user[employee.id],
        }
        for employee in employee_list
    ]
    manager = request.management_user
    pending_count = _approval_queryset_for_manager(manager).count() if _management_permission(manager, 'workdays_approve') else 0
    return render(request, 'attendance/management/dashboard.html', {
        'rows': rows, 'departments': Department.objects.all(), 'selected_dept': dept_id,
        'month_name': JALALI_MONTH_NAMES[m['jm'] - 1], 'jy': m['jy'], 'jm': m['jm'],
        'prev_y': m['prev_y'], 'prev_m': m['prev_m'], 'next_y': m['next_y'], 'next_m': m['next_m'],
        'pending_approval_count': pending_count,
        'can_add_employee': _management_permission(manager, 'employees_create'),
        'can_add_deduction': _management_permission(manager, 'deductions'),
        'can_approve': _management_permission(manager, 'workdays_approve'),
    })


@management_permission_required('employees')
def management_employees(request):
    User = get_user_model()
    employees = _management_employee_queryset()
    return render(request, 'attendance/management/employees.html', {'employees': employees, 'can_add_employee': _management_permission(request.management_user, 'employees_create')})


@management_permission_required('workdays_view')
def management_employee(request, user_id):
    User = get_user_model()
    employee = get_object_or_404(_management_employee_queryset(), pk=user_id)
    m = _resolve_month(request)
    days = WorkDay.objects.filter(user=employee, date__range=(m['start_date'], m['end_date']))
    deductions_qs = SalaryDeduction.objects.filter(user=employee, date__range=(m['start_date'], m['end_date'])).select_related('created_by').order_by('-date', '-created_at')
    deduction_total = deductions_qs.aggregate(total=Sum('amount')).get('total') or Decimal('0')
    deductions = []
    for deduction in deductions_qs:
        jy, jm, jd = gregorian_to_jalali(deduction.date.year, deduction.date.month, deduction.date.day)
        deductions.append({'obj': deduction, 'jalali_date': f'{jy:04d}/{jm:02d}/{jd:02d}'})
    return render(request, 'attendance/management/employee.html', {
        'employee': employee, 'stats': _compute_stats(days), 'deduction_total': deduction_total,
        'deductions': deductions,
        'can_manage_deductions': _management_permission(request.management_user, 'deductions'),
        'month_name': JALALI_MONTH_NAMES[m['jm'] - 1],
        'jy': m['jy'], 'jm': m['jm'], 'prev_y': m['prev_y'], 'prev_m': m['prev_m'], 'next_y': m['next_y'], 'next_m': m['next_m'],
    })


@management_any_permission_required('workdays_view', 'workdays_approve')
def management_employee_calendar(request, user_id):
    employee = get_object_or_404(_management_employee_queryset(), pk=user_id)
    m = _resolve_month(request)
    return render(request, 'attendance/management/employee_calendar.html', {
        'employee': employee,
        'weeks': _build_jalali_calendar(employee, m),
        'weekday_names': WEEKDAY_NAMES_DISPLAY,
        'month_name': JALALI_MONTH_NAMES[m['jm'] - 1], 'jy': m['jy'], 'jm': m['jm'],
        'prev_y': m['prev_y'], 'prev_m': m['prev_m'], 'next_y': m['next_y'], 'next_m': m['next_m'],
        'status_choices': WorkDay.STATUS_CHOICES,
        'can_approve': _management_permission(request.management_user, 'workdays_approve'),
        # This page belongs to the Management realm. Even for a superuser,
        # approval actions must use the Management endpoints/session, not /admin/.
        'admin_mode': False,
        'approval_mode': True,
    })


@management_permission_required('workdays_edit')
@require_POST
def management_view_as(request, user_id):
    User = get_user_model()
    employee = get_object_or_404(_management_employee_queryset(), pk=user_id)
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
        if _is_management_user(user):
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
            'approval_status': WorkDay.APPROVAL_PENDING,
            'approved_by': None,
            'approved_at': None,
            'rejection_reason': '',
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


@management_permission_required('workdays_approve')
def management_approvals(request):
    manager = request.management_user
    User = get_user_model()
    search = (request.GET.get('q') or '').strip()
    employees = _management_employee_queryset()
    if search:
        employees = employees.filter(
            Q(first_name__icontains=search) | Q(last_name__icontains=search) |
            Q(username__icontains=search) | Q(employee_profile__department__name__icontains=search)
        )
    if not manager.is_superuser:
        profile = getattr(manager, 'employee_profile', None)
        if profile and profile.department_id:
            employees = employees.filter(employee_profile__department_id=profile.department_id)
        else:
            employees = employees.none()
    pending_counts = {row['user_id']: row['count'] for row in WorkDay.objects.filter(
        approval_status=WorkDay.APPROVAL_PENDING, user__in=employees
    ).values('user_id').annotate(count=Count('id'))}
    employee_cards = []
    for employee in employees:
        count = pending_counts.get(employee.id, 0)
        employee_cards.append({'employee': employee, 'pending': count})
    return render(request, 'attendance/management/approvals.html', {
        'employee_cards': employee_cards,
        'search': search,
        'pending_total': sum(pending_counts.values()),
    })


@management_permission_required('workdays_approve')
@require_POST
def management_approve_workday(request, workday_id):
    manager = request.management_user
    work_day = get_object_or_404(_approval_queryset_for_manager(manager), pk=workday_id)
    work_day.approval_status = WorkDay.APPROVAL_APPROVED
    work_day.approved_by = manager
    work_day.approved_at = timezone.now()
    work_day.rejection_reason = ''
    work_day.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'])
    return redirect(f"{reverse('management_approvals')}?date={work_day.date.isoformat()}")


@management_permission_required('workdays_approve')
@require_POST
def management_reject_workday(request, workday_id):
    manager = request.management_user
    work_day = get_object_or_404(_approval_queryset_for_manager(manager), pk=workday_id)
    reason = (request.POST.get('reason') or '').strip()
    if not reason:
        reason = 'نیاز به بررسی مجدد دارد.'
    work_day.approval_status = WorkDay.APPROVAL_REJECTED
    work_day.approved_by = manager
    work_day.approved_at = timezone.now()
    work_day.rejection_reason = reason[:2000]
    work_day.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at'])
    return redirect(f"{reverse('management_approvals')}?date={work_day.date.isoformat()}")


@management_permission_required('workdays_approve')
@require_POST
def management_approve_date(request):
    manager = request.management_user
    raw_date = (request.POST.get('date') or '').strip()
    try:
        selected = _parse_user_date(raw_date)
    except ValueError:
        return redirect('management_approvals')
    now = timezone.now()
    count = _approval_queryset_for_manager(manager).filter(date=selected).update(
        approval_status=WorkDay.APPROVAL_APPROVED,
        approved_by=manager,
        approved_at=now,
        rejection_reason='',
    )
    messages.success(request, f'{count} مورد برای این روز تایید شد.')
    return redirect(f"{reverse('management_approvals')}?date={selected.isoformat()}")


def _parse_deduction_amount(raw):
    value = Decimal((raw or '').strip().replace(',', '').replace('۰','0').replace('۱','1').replace('۲','2').replace('۳','3').replace('۴','4').replace('۵','5').replace('۶','6').replace('۷','7').replace('۸','8').replace('۹','9').replace('٫','.'))
    if value <= 0:
        raise InvalidOperation
    # New UI: million Toman (0.2 => 200,000; 1 => 1,000,000).
    # Keep compatibility with legacy clients that submit Toman directly.
    return value.quantize(Decimal('1')) if value >= Decimal('100000') else (value * Decimal('1000000')).quantize(Decimal('1'))


@management_permission_required('deductions')
@require_POST
def management_add_deduction(request, user_id):
    employee = get_object_or_404(_management_employee_queryset(), pk=user_id)
    amount_raw = (request.POST.get('amount') or '').strip().replace(',', '')
    reason = (request.POST.get('reason') or '').strip()
    date_raw = (request.POST.get('date') or '').strip()
    try:
        amount = _parse_deduction_amount(amount_raw)
    except (InvalidOperation, ValueError):
        messages.error(request, 'مبلغ کسر حقوق نامعتبر است.')
        return redirect('management_dashboard')
    try:
        deduction_date = _parse_user_date(date_raw)
    except ValueError:
        messages.error(request, 'تاریخ کسر حقوق نامعتبر است.')
        return redirect('management_dashboard')
    if not reason:
        messages.error(request, 'دلیل کسر حقوق را وارد کنید.')
        return redirect('management_dashboard')
    SalaryDeduction.objects.create(user=employee, amount=amount, date=deduction_date, reason=reason[:2000], created_by=request.management_user)
    messages.success(request, 'کسر حقوق با موفقیت ثبت شد.')
    return redirect('management_dashboard')


@management_permission_required('deductions')
@require_POST
def management_edit_deduction(request, deduction_id):
    deduction = get_object_or_404(SalaryDeduction, pk=deduction_id)
    employee = get_object_or_404(_management_employee_queryset(), pk=deduction.user_id)
    try:
        amount = _parse_deduction_amount(request.POST.get('amount'))
        deduction_date = _parse_user_date((request.POST.get('date') or '').strip())
    except (InvalidOperation, ValueError):
        messages.error(request, 'مبلغ یا تاریخ کسر حقوق نامعتبر است.')
        return redirect('management_employee', user_id=employee.pk)
    reason = (request.POST.get('reason') or '').strip()
    if not reason:
        messages.error(request, 'دلیل کسر حقوق را وارد کنید.')
        return redirect('management_employee', user_id=employee.pk)
    deduction.amount = amount
    deduction.date = deduction_date
    deduction.reason = reason[:2000]
    deduction.save(update_fields=['amount', 'date', 'reason', 'updated_at'])
    messages.success(request, 'کسر حقوق با موفقیت اصلاح شد.')
    return redirect('management_employee', user_id=employee.pk)


@management_permission_required('deductions')
@require_POST
def management_delete_deduction(request, deduction_id):
    deduction = get_object_or_404(SalaryDeduction, pk=deduction_id)
    employee_id = deduction.user_id
    get_object_or_404(_management_employee_queryset(), pk=employee_id)
    deduction.delete()
    messages.success(request, 'کسر حقوق حذف شد.')
    return redirect('management_employee', user_id=employee_id)


@login_required
@require_POST
def employee_add_self_deduction(request):
    return HttpResponseForbidden('ثبت کسر حقوق توسط کارمند مجاز نیست.')



@management_permission_required('employees_create')
@require_POST
def management_create_employee(request):
    User = get_user_model()
    username = (request.POST.get('username') or '').strip()
    password = request.POST.get('password') or ''
    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    email = (request.POST.get('email') or '').strip()
    department_id = (request.POST.get('department') or '').strip()
    if not username or not password or not first_name:
        messages.error(request, 'نام کاربری، نام و رمز عبور الزامی است.')
        return redirect('management_dashboard')
    if User.objects.filter(username=username).exists():
        messages.error(request, 'این نام کاربری قبلاً ثبت شده است.')
        return redirect('management_dashboard')
    if len(password) < 8:
        messages.error(request, 'رمز عبور باید حداقل ۸ کاراکتر باشد.')
        return redirect('management_dashboard')
    department = None
    if department_id:
        try:
            department = Department.objects.get(pk=int(department_id))
        except (Department.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'بخش انتخاب‌شده معتبر نیست.')
            return redirect('management_dashboard')
    with transaction.atomic():
        employee = User.objects.create_user(
            username=username, password=password, first_name=first_name,
            last_name=last_name, email=email, is_active=True,
            is_staff=False, is_superuser=False,
        )
        EmployeeProfile.objects.create(user=employee, department=department)
    messages.success(request, f'کارمند «{employee.get_full_name() or employee.username}» اضافه شد.')
    return redirect('management_dashboard')
