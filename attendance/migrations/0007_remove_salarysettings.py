from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0006_add_friday_work'),
    ]

    operations = [
        migrations.DeleteModel(
            name='SalarySettings',
        ),
    ]
