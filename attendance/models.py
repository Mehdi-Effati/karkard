from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


MANAGEMENT_PERMISSION_CHOICES = [
    ('dashboard', 'داشبورد کارکرد'),
    ('employees', 'لیست کارمندان'),
    ('workdays_view', 'مشاهده جزئیات کارکرد'),
    ('workdays_edit', 'ویرایش/ثبت کارکرد و ورود به تقویم دیگران'),
    ('workdays_approve', 'تایید/رد کارکرد کارمندان'),
    ('deductions', 'ثبت و مدیریت کسر حقوق'),
    ('employees_create', 'افزودن کارمند جدید'),
    ('payroll', 'گزارش کارکرد (حسابداری)'),
]
MANAGEMENT_PERMISSION_KEYS = tuple(key for key, _label in MANAGEMENT_PERMISSION_CHOICES)


class AdminAccount(User):
    """
    پروکسی روی مدل User جنگو، فقط برای اینکه در پنل ادمین یک بخش جدا و ساده
    برای «افزودن ادمین» داشته باشیم (جدا از فهرست کارمندان عادی).
    هیچ جدول جدیدی در دیتابیس نمی‌سازد.
    """
    class Meta:
        proxy = True
        verbose_name = 'مدیر (Admin)'
        verbose_name_plural = 'مدیران (Admins)'


class WorkDay(models.Model):
    STATUS_WORK = 'work'
    STATUS_NIGHT = 'night'
    STATUS_HOLIDAY_WORK = 'holiday_work'
    STATUS_FRIDAY_WORK = 'friday_work'
    STATUS_LEAVE = 'leave'
    STATUS_OFF = 'off'

    STATUS_CHOICES = [
        (STATUS_WORK, 'روز کاری'),
        (STATUS_NIGHT, 'شب کاری'),
        (STATUS_HOLIDAY_WORK, 'تعطیل کاری'),
        (STATUS_FRIDAY_WORK, 'جمعه کاری'),
        (STATUS_LEAVE, 'مرخصی'),
        (STATUS_OFF, 'Off'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_days', verbose_name='کارمند')
    date = models.DateField(verbose_name='تاریخ (میلادی)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OFF, verbose_name='وضعیت روز')
    overtime_hours = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
        verbose_name='ساعت اضافه‌کاری'
    )
    note = models.TextField(blank=True, default='', verbose_name='یادداشت')
    APPROVAL_PENDING = 'pending'
    APPROVAL_APPROVED = 'approved'
    APPROVAL_REJECTED = 'rejected'
    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, 'در انتظار تایید'),
        (APPROVAL_APPROVED, 'تایید شده'),
        (APPROVAL_REJECTED, 'رد شده'),
    ]
    approval_status = models.CharField(
        max_length=20, choices=APPROVAL_CHOICES, default=APPROVAL_PENDING,
        verbose_name='وضعیت تایید'
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_work_days', verbose_name='تاییدکننده'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان تایید')
    rejection_reason = models.TextField(blank=True, default='', verbose_name='دلیل رد')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['date']
        verbose_name = 'روز کاری'
        verbose_name_plural = 'روزهای کاری'

    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.get_status_display()}"


class SalaryDeduction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='salary_deductions', verbose_name='کارمند')
    amount = models.DecimalField(
        max_digits=12, decimal_places=0, validators=[MinValueValidator(1)],
        verbose_name='مبلغ کسر حقوق'
    )
    date = models.DateField(verbose_name='تاریخ')
    reason = models.TextField(verbose_name='دلیل کسر حقوق')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_salary_deductions', verbose_name='ثبت‌کننده'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'کسر حقوق'
        verbose_name_plural = 'کسرهای حقوق'

    def __str__(self):
        return f"{self.user.username} - {self.amount} - {self.date}"


class Department(models.Model):
    """بخش/تیم سازمانی برای دسته‌بندی کارمندها (مثلا تولید، اداری، فروش)."""
    name = models.CharField(max_length=100, unique=True, verbose_name='نام بخش')

    class Meta:
        verbose_name = 'بخش'
        verbose_name_plural = 'بخش‌ها'
        ordering = ['name']

    def __str__(self):
        return self.name


class EmployeeProfile(models.Model):
    """اطلاعات تکمیلی هر کارمند، جدا از مدل User جنگو (بخش سازمانی)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile', verbose_name='کارمند')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='employees', verbose_name='بخش'
    )
    is_accountant = models.BooleanField(
        default=False, verbose_name='حسابدار / دسترسی مدیریت',
        help_text='اگر فعال باشد، کاربر همچنان کارمند عادی باقی می‌ماند و می‌تواند برای خودش کارکرد ثبت کند؛ در عین حال می‌تواند با دسترسی‌های انتخاب‌شده وارد پنل مدیریت شود.'
    )
    management_permissions = models.JSONField(
        default=list, blank=True, verbose_name='دسترسی‌های پنل مدیریت',
        help_text='برای حسابدار. در صورت خالی بودن هنگام فعال‌سازی حسابدار، همه دسترسی‌های فعلی به‌صورت پیش‌فرض فعال می‌شوند.'
    )

    def save(self, *args, **kwargs):
        # حسابدار از نظر Django یک Staff User است، اما Superuser نیست.
        # این هم‌زمانی باعث می‌شود حسابدار هم در پنل مدیریت احراز هویت شود
        # و هم به‌عنوان کارمند در لیست کارکرد باقی بماند.
        if self.is_accountant and not self.user.is_staff:
            self.user.is_staff = True
            self.user.save(update_fields=['is_staff'])
        super().save(*args, **kwargs)

    def has_management_permission(self, permission):
        if not self.is_accountant:
            return False
        return permission in (self.management_permissions or [])

    def grant_full_management_access(self):
        self.management_permissions = list(MANAGEMENT_PERMISSION_KEYS)

    class Meta:
        verbose_name = 'پروفایل کارمند'
        verbose_name_plural = 'پروفایل‌های کارمندان'

    def __str__(self):
        return self.user.username


class Holiday(models.Model):
    KIND_OFFICIAL = 'official'
    KIND_GOVERNMENT = 'government'
    KIND_CHOICES = [(KIND_OFFICIAL, 'تعطیل رسمی'), (KIND_GOVERNMENT, 'تعطیلی اعلامی دولت')]
    """
    یک روز تعطیل رسمی. اگر year خالی باشد یعنی «هرساله تکرار می‌شود» (مثل نوروز، ۱۳ فروردین، ۲۲ بهمن...)
    و بر اساس ماه/روز شمسی در هر سالی اعمال می‌شود. اگر year مقدار داشته باشد فقط برای همان سال است
    (مناسب تعطیلات قمری مثل عید فطر، عاشورا، عرفه... که هر سال شمسی تاریخشان جابه‌جا می‌شود).
    """
    title = models.CharField(max_length=200, verbose_name='عنوان تعطیلی')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_OFFICIAL, verbose_name='نوع تعطیلی')
    jalali_month = models.PositiveSmallIntegerField(verbose_name='ماه شمسی (۱ تا ۱۲)')
    jalali_day = models.PositiveSmallIntegerField(verbose_name='روز شمسی (۱ تا ۳۱)')
    jalali_year = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='سال شمسی (خالی = هرساله تکرار شود)'
    )

    class Meta:
        verbose_name = 'تعطیل رسمی'
        verbose_name_plural = 'تعطیلات رسمی'
        ordering = ['jalali_month', 'jalali_day']

    def __str__(self):
        year_part = f'{self.jalali_year}/' if self.jalali_year else 'هرساله '
        return f'{year_part}{self.jalali_month:02d}/{self.jalali_day:02d} — {self.title}'
