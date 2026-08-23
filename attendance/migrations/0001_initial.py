import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='تاریخ (میلادی)')),
                ('status', models.CharField(choices=[('work', 'روز کاری'), ('night', 'شب کاری'), ('holiday_work', 'تعطیل کاری'), ('leave', 'مرخصی'), ('off', 'Off')], default='off', max_length=20, verbose_name='وضعیت روز')),
                ('overtime_hours', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=5, null=True, verbose_name='ساعت اضافه\u200cکاری')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_days', to=settings.AUTH_USER_MODEL, verbose_name='کارمند')),
            ],
            options={
                'verbose_name': 'روز کاری',
                'verbose_name_plural': 'روزهای کاری',
                'ordering': ['date'],
                'unique_together': {('user', 'date')},
            },
        ),
    ]
