from django.db import migrations


def separate_admin_and_employee(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    from django.contrib.auth.hashers import make_password

    # mehdi از این به بعد فقط یک کارمند عادیست و دسترسی پنل ادمین ندارد
    User.objects.filter(username='mehdi').update(is_staff=False, is_superuser=False)

    # یک حساب ادمین جداگانه و اختصاصی برای ورود به پنل مدیریت
    if not User.objects.filter(username='admin').exists():
        User.objects.create(
            username='admin',
            password=make_password(None),
            is_staff=True,
            is_superuser=True,
            is_active=True,
            first_name='مدیر سیستم',
        )


def reverse_separate(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='mehdi').update(is_staff=True, is_superuser=True)
    User.objects.filter(username='admin').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_adminaccount'),
    ]

    operations = [
        migrations.RunPython(separate_admin_and_employee, reverse_separate),
    ]
