from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['date']
        verbose_name = 'روز کاری'
        verbose_name_plural = 'روزهای کاری'

    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.get_status_display()}"


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
