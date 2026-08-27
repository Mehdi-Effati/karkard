from django.db import migrations
from django.db.models import Q


def forwards(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('attendance', 'EmployeeProfile')
    accountant_ids = Profile.objects.filter(is_accountant=True).values_list('user_id', flat=True)
    User.objects.filter(id__in=accountant_ids).update(is_staff=True)


def backwards(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Profile = apps.get_model('attendance', 'EmployeeProfile')
    accountant_ids = Profile.objects.filter(is_accountant=True).values_list('user_id', flat=True)
    User.objects.filter(id__in=accountant_ids, is_superuser=False).update(is_staff=False)


class Migration(migrations.Migration):
    dependencies = [('attendance', '0013_workday_approval_salarydeduction_permissions')]
    operations = [migrations.RunPython(forwards, backwards)]
