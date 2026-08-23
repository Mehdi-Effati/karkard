from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


def approve_existing_workdays(apps, schema_editor):
    WorkDay = apps.get_model('attendance', 'WorkDay')
    WorkDay.objects.all().update(
        approval_status='approved',
        approved_by=None,
        approved_at=None,
        rejection_reason='',
    )


def update_accountant_permissions(apps, schema_editor):
    EmployeeProfile = apps.get_model('attendance', 'EmployeeProfile')
    old_full = {'dashboard', 'employees', 'workdays_view', 'workdays_edit', 'payroll'}
    new_keys = ['dashboard', 'employees', 'workdays_view', 'workdays_edit', 'workdays_approve', 'deductions', 'employees_create', 'payroll']
    for profile in EmployeeProfile.objects.filter(is_accountant=True):
        permissions = profile.management_permissions or []
        # Only upgrade accounts that previously had the complete default set.
        # A deliberately limited accountant must keep exactly the limited access
        # they were assigned. Empty means full by application convention.
        if permissions and set(permissions) == old_full:
            profile.management_permissions = new_keys
            profile.save(update_fields=['management_permissions'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0012_accountant_management_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='workday',
            name='approval_status',
            field=models.CharField(
                choices=[
                    ('pending', 'در انتظار تایید'),
                    ('approved', 'تایید شده'),
                    ('rejected', 'رد شده'),
                ],
                default='pending',
                max_length=20,
                verbose_name='وضعیت تایید',
            ),
        ),
        migrations.AddField(
            model_name='workday',
            name='approved_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان تایید'),
        ),
        migrations.AddField(
            model_name='workday',
            name='approved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='approved_work_days',
                to=settings.AUTH_USER_MODEL,
                verbose_name='تاییدکننده',
            ),
        ),
        migrations.AddField(
            model_name='workday',
            name='rejection_reason',
            field=models.TextField(blank=True, default='', verbose_name='دلیل رد'),
        ),
        migrations.CreateModel(
            name='SalaryDeduction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=0, max_digits=12, validators=[django.core.validators.MinValueValidator(1)], verbose_name='مبلغ کسر حقوق')),
                ('date', models.DateField(verbose_name='تاریخ')),
                ('reason', models.TextField(verbose_name='دلیل کسر حقوق')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_salary_deductions', to=settings.AUTH_USER_MODEL, verbose_name='ثبت‌کننده')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='salary_deductions', to=settings.AUTH_USER_MODEL, verbose_name='کارمند')),
            ],
            options={
                'verbose_name': 'کسر حقوق',
                'verbose_name_plural': 'کسرهای حقوق',
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.RunPython(approve_existing_workdays, noop),
        migrations.RunPython(update_accountant_permissions, noop),
    ]
