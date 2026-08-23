from django.db import migrations, models


def create_default_salary_settings(apps, schema_editor):
    SalarySettings = apps.get_model('attendance', 'SalarySettings')
    if not SalarySettings.objects.filter(pk=1).exists():
        SalarySettings.objects.create(
            pk=1,
            work_day_rate=0,
            night_day_rate=0,
            holiday_day_rate=0,
            overtime_hour_rate=0,
        )


def remove_default_salary_settings(apps, schema_editor):
    SalarySettings = apps.get_model('attendance', 'SalarySettings')
    SalarySettings.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_create_default_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalarySettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('work_day_rate', models.DecimalField(decimal_places=0, default=0, max_digits=14, verbose_name='حقوق پایه هر روز کاری (تومان)')),
                ('night_day_rate', models.DecimalField(decimal_places=0, default=0, max_digits=14, verbose_name='حقوق پایه هر شب کاری (تومان)')),
                ('holiday_day_rate', models.DecimalField(decimal_places=0, default=0, max_digits=14, verbose_name='حقوق پایه هر روز تعطیل\u200cکاری (تومان)')),
                ('overtime_hour_rate', models.DecimalField(decimal_places=0, default=0, max_digits=14, verbose_name='نرخ هر ساعت اضافه\u200cکاری (تومان)')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'تنظیمات حقوق و دستمزد',
                'verbose_name_plural': 'تنظیمات حقوق و دستمزد',
            },
        ),
        migrations.RunPython(create_default_salary_settings, remove_default_salary_settings),
    ]
