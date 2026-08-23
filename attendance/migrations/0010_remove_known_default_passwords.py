from django.contrib.auth.hashers import check_password, make_password
from django.db import migrations


def secure_known_defaults(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    known_defaults = {
        'mehdi': 'DecaeseD',
        'admin': 'AdminPass123!',
    }
    for username, password in known_defaults.items():
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            continue
        if check_password(password, user.password):
            user.password = make_password(None)
            user.save(update_fields=['password'])


class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0009_holiday_kind'),
    ]

    operations = [
        migrations.RunPython(secure_known_defaults, migrations.RunPython.noop),
    ]
