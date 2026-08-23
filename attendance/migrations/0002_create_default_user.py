from django.db import migrations


def create_default_user(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    from django.contrib.auth.hashers import make_password

    if not User.objects.filter(username='mehdi').exists():
        User.objects.create(
            username='mehdi',
            password=make_password(None),
            is_staff=True,
            is_superuser=True,
            is_active=True,
            first_name='مهدی',
        )


def remove_default_user(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='mehdi').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
        ('auth', '__first__'),
    ]

    operations = [
        migrations.RunPython(create_default_user, remove_default_user),
    ]
