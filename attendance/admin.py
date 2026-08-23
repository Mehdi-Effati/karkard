from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import User

from .models import AdminAccount, Department, EmployeeProfile, Holiday, WorkDay, SalaryDeduction, MANAGEMENT_PERMISSION_CHOICES, MANAGEMENT_PERMISSION_KEYS

admin.site.site_header = 'پنل مدیریت تقویم کاری'
admin.site.site_title = 'تقویم کاری'
admin.site.index_title = 'مدیریت کارمندان و روزهای کاری'

# صفحه اصلی پنل ادمین را با یک نسخه سفارشی (شامل دکمه لینک به کارکرد کارمندان) نمایش بده
admin.site.index_template = 'attendance/admin_index.html'


@admin.register(WorkDay)
class WorkDayAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'status', 'approval_status', 'approved_by', 'overtime_hours', 'note', 'updated_at')
    list_filter = ('status', 'approval_status', 'user')
    search_fields = ('user__username', 'note')
    date_hierarchy = 'date'
    ordering = ('-date',)




@admin.register(SalaryDeduction)
class SalaryDeductionAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'amount', 'reason', 'created_by', 'created_at')
    list_filter = ('date',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'reason')
    date_hierarchy = 'date'
    ordering = ('-date', '-created_at')
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


class EmployeeProfileForm(forms.ModelForm):
    management_permissions = forms.MultipleChoiceField(
        label='دسترسی‌های پنل مدیریت حسابدار',
        choices=MANAGEMENT_PERMISSION_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='اگر حسابدار فعال باشد و هیچ گزینه‌ای انتخاب نشود، همه دسترسی‌های فعلی به‌صورت پیش‌فرض فعال می‌شوند. سوپریوزر همیشه دسترسی کامل دارد.',
    )

    class Meta:
        model = EmployeeProfile
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['management_permissions'] = self.instance.management_permissions or []

    def clean_management_permissions(self):
        values = self.cleaned_data.get('management_permissions') or []
        return list(values)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_accountant') and not cleaned.get('management_permissions'):
            cleaned['management_permissions'] = list(MANAGEMENT_PERMISSION_KEYS)
        return cleaned


class EmployeeProfileInline(admin.StackedInline):
    model = EmployeeProfile
    form = EmployeeProfileForm
    can_delete = False
    verbose_name_plural = 'اطلاعات کارمند و سطح دسترسی حسابداری'
    fieldsets = (
        ('اطلاعات سازمانی', {'fields': ('department',)}),
        ('دسترسی حسابداری', {
            'fields': ('is_accountant', 'management_permissions'),
            'description': 'کاربر حسابدار همچنان کارمند عادی است و می‌تواند برای خودش شیفت ثبت کند. فقط دسترسی‌های انتخاب‌شده را در پنل مدیریت دریافت می‌کند.',
        }),
    )


# مدل استاندارد User جنگو را دوباره ثبت می‌کنیم تا اینلاین بخش سازمانی رویش نمایش داده شود
admin.site.unregister(User)


@admin.register(User)
class EmployeeUserAdmin(UserAdmin):
    inlines = [EmployeeProfileInline]
    list_display = ('username', 'full_name', 'is_accountant', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'employee_profile__is_accountant')
    search_fields = ('username', 'first_name', 'last_name', 'email')

    @admin.display(boolean=True, description='حسابدار')
    def is_accountant(self, obj):
        profile = getattr(obj, 'employee_profile', None)
        return bool(profile and profile.is_accountant)

    @admin.display(description='نام')
    def full_name(self, obj):
        return obj.get_full_name() or obj.username

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
