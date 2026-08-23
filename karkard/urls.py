from django.contrib import admin
from django.urls import include, path

from attendance import views as attendance_views

urlpatterns = [
    # این مسیر عمداً قبل از مسیر 'admin/' آمده تا زودتر از urlconf خود ادمین تشخیص داده شود
    path('admin/payroll/', attendance_views.admin_payroll_view, name='admin_payroll'),
    path('management/login/', attendance_views.management_login, name='management_login'),
    path('management/', attendance_views.management_dashboard, name='management_dashboard'),
    path('management/employees/', attendance_views.management_employees, name='management_employees'),
    path('management/employees/<int:user_id>/', attendance_views.management_employee, name='management_employee'),
    path('management/employees/<int:user_id>/view-as/', attendance_views.management_view_as, name='management_view_as'),
    path('management/approvals/', attendance_views.management_approvals, name='management_approvals'),
    path('management/approvals/<int:workday_id>/approve/', attendance_views.management_approve_workday, name='management_approve_workday'),
    path('management/approvals/<int:workday_id>/reject/', attendance_views.management_reject_workday, name='management_reject_workday'),
    path('management/approvals/approve-date/', attendance_views.management_approve_date, name='management_approve_date'),
    path('management/deductions/<int:user_id>/add/', attendance_views.management_add_deduction, name='management_add_deduction'),
    path('management/employees/create/', attendance_views.management_create_employee, name='management_create_employee'),
    path('management/stop-view-as/', attendance_views.management_stop_view_as, name='management_stop_view_as'),
    path('management/logout/', attendance_views.management_logout, name='management_logout'),
    path('admin/', admin.site.urls),
    path('', include('attendance.urls')),
]
