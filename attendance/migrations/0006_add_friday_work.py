from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0005_separate_admin_and_employee'),
    ]

    operations = [
        migrations.AddField(
            model_name='salarysettings',
            name='friday_day_rate',
            field=models.DecimalField(decimal_places=0, default=0, max_digits=14, verbose_name='حقوق پایه هر جمعه\u200cکاری (تومان)'),
        ),
        migrations.AlterField(
            model_name='workday',
            name='status',
            field=models.CharField(
                choices=[
                    ('work', 'روز کاری'),
                    ('night', 'شب کاری'),
                    ('holiday_work', 'تعطیل کاری'),
                    ('friday_work', 'جمعه کاری'),
                    ('leave', 'مرخصی'),
                    ('off', 'Off'),
                ],
                default='off',
                max_length=20,
                verbose_name='وضعیت روز',
            ),
        ),
    ]
