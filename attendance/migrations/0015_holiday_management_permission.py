from django.db import migrations


HOLIDAY_PERMISSION = 'holidays'
FULL_PERMISSION_KEYS = [
    'dashboard', 'employees', 'workdays_view', 'workdays_edit',
    'workdays_approve', 'deductions', 'employees_create', 'payroll',
    HOLIDAY_PERMISSION,
]


def forwards(apps, schema_editor):
    Profile = apps.get_model('attendance', 'EmployeeProfile')
    for profile in Profile.objects.filter(is_accountant=True):
        permissions = list(profile.management_permissions or [])
        # Existing accounts that already had the complete old permission set
        # receive the new holiday permission. Limited accountants remain limited.
        old_full = set(permissions) >= {
            'dashboard', 'employees', 'workdays_view', 'workdays_edit',
            'workdays_approve', 'deductions', 'employees_create', 'payroll',
        }
        if old_full and HOLIDAY_PERMISSION not in permissions:
            profile.management_permissions = permissions + [HOLIDAY_PERMISSION]
            profile.save(update_fields=['management_permissions'])


def backwards(apps, schema_editor):
    Profile = apps.get_model('attendance', 'EmployeeProfile')
    for profile in Profile.objects.filter(is_accountant=True):
        permissions = list(profile.management_permissions or [])
        if HOLIDAY_PERMISSION in permissions:
            profile.management_permissions = [p for p in permissions if p != HOLIDAY_PERMISSION]
            profile.save(update_fields=['management_permissions'])


class Migration(migrations.Migration):
    dependencies = [('attendance', '0014_accountants_are_staff')]
    operations = [migrations.RunPython(forwards, backwards)]
