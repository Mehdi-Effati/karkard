import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0010_remove_known_default_passwords'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workday',
            name='overtime_hours',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=0,
                max_digits=5,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(24),
                ],
                verbose_name='ساعت اضافه‌کاری',
            ),
        ),
    ]
