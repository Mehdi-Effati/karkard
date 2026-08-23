from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import AdminAccount, Department, EmployeeProfile, Holiday, WorkDay

admin.site.site_header = 'پنل مدیریت تقویم کاری'
admin.site.site_title = 'تقویم کاری'
admin.site.index_title = 'مدیریت کارمندان و روزهای کاری'

# صفحه اصلی پنل ادمین را با یک نسخه سفارشی (شامل دکمه لینک به کارکرد کارمندان) نمایش بده
admin.site.index_template = 'attendance/admin_index.html'


@admin.register(WorkDay)
class WorkDayAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'status', 'overtime_hours', 'note', 'updated_at')
    list_filter = ('status', 'user')
    search_fields = ('user__username', 'note')
    date_hierarchy = 'date'
    ordering = ('-date',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee_count')
    search_fields = ('name',)

    def employee_count(self, obj):
        return obj.employees.count()
    employee_count.short_description = 'تعداد کارمندان'


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'jalali_month', 'jalali_day', 'jalali_year')
    list_filter = ('kind', 'jalali_month')
    search_fields = ('title',)
    ordering = ('jalali_month', 'jalali_day')


class EmployeeProfileInline(admin.StackedInline):
    model = EmployeeProfile
    can_delete = False
    verbose_name_plural = 'اطلاعات تکمیلی کارمند (بخش سازمانی)'


# مدل استاندارد User جنگو را دوباره ثبت می‌کنیم تا اینلاین بخش سازمانی رویش نمایش داده شود
admin.site.unregister(User)


@admin.register(User)
class EmployeeUserAdmin(UserAdmin):
    inlines = [EmployeeProfileInline]

    def get_inline_instances(self, request, obj=None):
        # موقع ساخت کاربر جدید (obj=None) اینلاین نشان داده نشود، چون هنوز رکورد User ای برای اتصال نیست
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)


class AdminAccountCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = AdminAccount
        fields = ('username',)


@admin.register(AdminAccount)
class AdminAccountAdmin(UserAdmin):
    """
    بخش ساده «مدیران» در پنل ادمین: فقط برای ساختن سریع یک حساب ادمین جدید
    (کافیست نام کاربری و رمز عبور وارد شود؛ دسترسی staff/superuser خودکار داده می‌شود).
    """
    add_form = AdminAccountCreationForm
    list_display = ('username', 'first_name', 'is_superuser', 'is_active', 'date_joined')
    list_filter = ()
    inlines = []

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_staff=True)

    def save_model(self, request, obj, form, change):
        obj.is_staff = True
        obj.is_superuser = True
        super().save_model(request, obj, form, change)
