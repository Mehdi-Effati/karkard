import django.contrib.auth.models
from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('attendance', '0003_salarysettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminAccount',
            fields=[],
            options={
                'verbose_name': 'مدیر (Admin)',
                'verbose_name_plural': 'مدیران (Admins)',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('auth.user',),
        ),
    ]
