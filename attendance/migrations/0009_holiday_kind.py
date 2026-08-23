from django.db import migrations, models


HOLIDAYS_1405 = [
    (1, 1, 'نوروز', 'official'), (1, 2, 'نوروز', 'official'), (1, 3, 'نوروز', 'official'), (1, 4, 'نوروز', 'official'),
    (1, 12, 'روز جمهوری اسلامی ایران', 'official'), (1, 13, 'روز طبیعت', 'official'), (1, 24, 'شهادت امام جعفر صادق (ع)', 'official'),
    (3, 3, 'شهادت امام محمد باقر (ع)', 'official'), (3, 6, 'عید قربان', 'official'),
    (3, 14, 'رحلت امام خمینی (ره) و عید غدیر خم', 'official'), (3, 15, 'قیام ۱۵ خرداد', 'official'),
    (4, 3, 'تاسوعای حسینی', 'official'), (4, 4, 'عاشورای حسینی', 'official'),
    (4, 13, 'تعطیلی سراسری اعلام‌شده', 'government'), (4, 14, 'تعطیلی سراسری اعلام‌شده', 'government'),
    (4, 15, 'تعطیلی سراسری اعلام‌شده', 'government'), (4, 16, 'تعطیلی استان تهران', 'government'),
    (5, 13, 'اربعین حسینی', 'official'), (5, 21, 'رحلت پیامبر اکرم (ص) و شهادت امام حسن مجتبی (ع)', 'official'),
    (5, 22, 'شهادت امام رضا (ع)', 'official'), (5, 30, 'شهادت امام حسن عسکری (ع)', 'official'),
    (6, 8, 'میلاد پیامبر اکرم (ص) و میلاد امام جعفر صادق (ع)', 'official'),
    (8, 22, 'شهادت حضرت فاطمه زهرا (س)', 'official'),
    (10, 2, 'ولادت امام علی (ع) و روز پدر', 'official'), (10, 16, 'مبعث پیامبر اکرم (ص)', 'official'),
    (11, 4, 'ولادت حضرت قائم (عج)', 'official'), (11, 22, 'پیروزی انقلاب اسلامی ایران', 'official'),
    (12, 9, 'شهادت حضرت علی (ع)', 'official'), (12, 19, 'عید سعید فطر', 'official'),
    (12, 20, 'تعطیل به مناسبت عید سعید فطر', 'official'), (12, 29, 'روز ملی شدن صنعت نفت ایران', 'official'),
]


def seed(apps, schema_editor):
    Holiday = apps.get_model('attendance', 'Holiday')
    for month, day, title, kind in HOLIDAYS_1405:
        obj, _ = Holiday.objects.get_or_create(
            jalali_month=month, jalali_day=day, jalali_year=1405,
            defaults={'title': title, 'kind': kind},
        )
        changed = False
        if obj.title != title:
            obj.title = title; changed = True
        if obj.kind != kind:
            obj.kind = kind; changed = True
        if changed:
            obj.save(update_fields=['title', 'kind'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('attendance', '0008_holidays_notes_departments')]
    operations = [
        migrations.AddField(
            model_name='holiday', name='kind',
            field=models.CharField(choices=[('official', 'تعطیل رسمی'), ('government', 'تعطیلی اعلامی دولت')], default='official', max_length=20, verbose_name='نوع تعطیلی'),
        ),
        migrations.RunPython(seed, noop),
    ]
