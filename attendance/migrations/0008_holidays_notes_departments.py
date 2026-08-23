import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


FIXED_HOLIDAYS = [
    # (ماه، روز، عنوان) — تعطیلات ثابت شمسی که هرسال در همان تاریخ تکرار می‌شوند
    (1, 1, 'عید نوروز'),
    (1, 2, 'عید نوروز'),
    (1, 3, 'عید نوروز'),
    (1, 4, 'عید نوروز'),
    (1, 12, 'روز جمهوری اسلامی ایران'),
    (1, 13, 'روز طبیعت (سیزده‌به‌در)'),
    (3, 14, 'رحلت امام خمینی (ره)'),
    (3, 15, 'قیام ۱۵ خرداد'),
    (11, 22, 'پیروزی انقلاب اسلامی'),
    (12, 29, 'روز ملی شدن صنعت نفت ایران'),
]


def seed_fixed_holidays(apps, schema_editor):
    Holiday = apps.get_model('attendance', 'Holiday')
    for month, day, title in FIXED_HOLIDAYS:
        Holiday.objects.get_or_create(
            jalali_month=month, jalali_day=day, jalali_year=None, title=title,
        )


def remove_fixed_holidays(apps, schema_editor):
    Holiday = apps.get_model('attendance', 'Holiday')
    Holiday.objects.filter(jalali_year=None).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('attendance', '0007_remove_salarysettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='workday',
            name='note',
            field=models.TextField(blank=True, default='', verbose_name='یادداشت'),
        ),
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='نام بخش')),
            ],
            options={
                'verbose_name': 'بخش',
                'verbose_name_plural': 'بخش\u200cها',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='EmployeeProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employees', to='attendance.department', verbose_name='بخش')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='employee_profile', to=settings.AUTH_USER_MODEL, verbose_name='کارمند')),
            ],
            options={
                'verbose_name': 'پروفایل کارمند',
                'verbose_name_plural': 'پروفایل\u200cهای کارمندان',
            },
        ),
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان تعطیلی')),
                ('jalali_month', models.PositiveSmallIntegerField(verbose_name='ماه شمسی (۱ تا ۱۲)')),
                ('jalali_day', models.PositiveSmallIntegerField(verbose_name='روز شمسی (۱ تا ۳۱)')),
                ('jalali_year', models.PositiveIntegerField(blank=True, null=True, verbose_name='سال شمسی (خالی = هرساله تکرار شود)')),
            ],
            options={
                'verbose_name': 'تعطیل رسمی',
                'verbose_name_plural': 'تعطیلات رسمی',
                'ordering': ['jalali_month', 'jalali_day'],
            },
        ),
        migrations.RunPython(seed_fixed_holidays, remove_fixed_holidays),
    ]
