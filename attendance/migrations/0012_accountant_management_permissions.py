from django.db import migrations, models


ALL_PERMISSIONS = [
    'dashboard',
    'employees',
    'workdays_view',
    'workdays_edit',
    'payroll',
]


def set_default_permissions(apps, schema_editor):
    EmployeeProfile = apps.get_model('attendance', 'EmployeeProfile')
    for profile in EmployeeProfile.objects.all().iterator():
        if profile.management_permissions is None:
            profile.management_permissions = []
            profile.save(update_fields=['management_permissions'])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('attendance', '0011_alter_workday_overtime_hours')]

    operations = [
        migrations.AddField(
            model_name='employeeprofile',
            name='is_accountant',
            field=models.BooleanField(default=False, help_text='اگر فعال باشد، کاربر همچنان کارمند عادی باقی می‌ماند و می‌تواند برای خودش کارکرد ثبت کند؛ در عین حال می‌تواند با دسترسی‌های انتخاب‌شده وارد پنل مدیریت شود.', verbose_name='حسابدار / دسترسی مدیریت'),
        ),
        migrations.AddField(
            model_name='employeeprofile',
            name='management_permissions',
            field=models.JSONField(blank=True, default=list, help_text='برای حسابدار. در صورت خالی بودن هنگام فعال‌سازی حسابدار، همه دسترسی‌های فعلی به‌صورت پیش‌فرض فعال می‌شوند.', verbose_name='دسترسی‌های پنل مدیریت'),
        ),
        migrations.RunPython(set_default_permissions, reverse_noop),
    ]
