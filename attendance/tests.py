from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, DEBUG=True)
class ManagementSecurityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.employee = User.objects.create_user(username='employee', password='EmployeePass123!')
        self.staff = User.objects.create_user(username='staff', password='StaffPass123!', is_staff=True)
        self.admin = User.objects.create_user(
            username='admin2', password='AdminPass123!', is_staff=True, is_superuser=True
        )

    def test_employee_cannot_access_management_dashboard(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('management_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('management_login'), response['Location'])

    def test_staff_without_superuser_cannot_access_management(self):
        response = self.client.post(
            reverse('management_login'),
            {'username': 'staff', 'password': 'StaffPass123!'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'اجازه ورود')
        self.assertNotIn('attendance_management_auth', self.client.cookies)

    def test_superuser_can_access_management(self):
        response = self.client.post(
            reverse('management_login'),
            {'username': 'admin2', 'password': 'AdminPass123!'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('management_dashboard'))
        response = self.client.get(reverse('management_dashboard'))
        self.assertEqual(response.status_code, 200)


    def test_management_uses_management_identity_not_employee_session(self):
        # Simulate the real bug: an employee Django session remains while the
        # administrator authenticates into the separate management realm.
        self.client.force_login(self.employee)
        self.client.post(
            reverse('management_login'),
            {'username': 'admin2', 'password': 'AdminPass123!'},
        )
        response = self.client.get(reverse('management_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin2')
        # The employee is intentionally still listed in the management dashboard;
        # this assertion must verify the management identity, not the employee list.
        self.assertContains(response, 'admin2')

    def test_management_login_does_not_replace_employee_session(self):
        self.client.force_login(self.employee)
        self.client.post(
            reverse('management_login'),
            {'username': 'admin2', 'password': 'AdminPass123!'},
        )
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'employee عزیز')
        self.assertNotContains(response, 'admin2 عزیز')

    def test_view_as_is_explicit_and_separate_from_employee_session(self):
        self.client.force_login(self.employee)
        self.client.post(
            reverse('management_login'),
            {'username': 'admin2', 'password': 'AdminPass123!'},
        )
        response = self.client.post(reverse('management_view_as', args=[self.staff.pk]))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(reverse('management_view_as', args=[self.employee.pk]))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'employee عزیز')

    def test_management_logout_does_not_logout_employee(self):
        self.client.force_login(self.employee)
        self.client.post(reverse('management_login'), {'username': 'admin2', 'password': 'AdminPass123!'})
        response = self.client.post(reverse('management_logout'))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'employee عزیز')

    def test_employee_logout_does_not_logout_management(self):
        self.client.post(reverse('management_login'), {'username': 'admin2', 'password': 'AdminPass123!'})
        self.client.force_login(self.employee)
        self.client.post(reverse('logout'))
        response = self.client.get(reverse('management_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'admin2')

    def test_view_as_requires_post(self):
        self.client.post(
            reverse('management_login'),
            {'username': 'admin2', 'password': 'AdminPass123!'},
        )
        response = self.client.get(reverse('management_view_as', args=[self.employee.pk]))
        self.assertEqual(response.status_code, 405)

    def test_view_as_cannot_target_staff_accounts(self):
        self.client.post(
            reverse('management_login'),
            {'username': 'admin2', 'password': 'AdminPass123!'},
        )
        response = self.client.post(reverse('management_view_as', args=[self.staff.pk]))
        self.assertEqual(response.status_code, 404)

    def test_external_next_is_rejected(self):
        response = self.client.post(
            reverse('management_login') + '?next=https://evil.example/',
            {'username': 'admin2', 'password': 'AdminPass123!', 'next': 'https://evil.example/'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('management_dashboard'))

@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, DEBUG=True)
class AccountantRoleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.accountant = User.objects.create_user(
            username='accountant', password='AccountantPass123!', first_name='حسابدار'
        )
        self.employee = User.objects.create_user(
            username='employee2', password='EmployeePass123!', first_name='کارمند'
        )
        self.admin = User.objects.create_user(
            username='root', password='RootPass123!', is_staff=True, is_superuser=True,
            first_name='مدیر اصلی'
        )
        from .models import EmployeeProfile, MANAGEMENT_PERMISSION_KEYS
        self.accountant_profile = EmployeeProfile.objects.create(
            user=self.accountant,
            is_accountant=True,
            management_permissions=list(MANAGEMENT_PERMISSION_KEYS),
        )
        EmployeeProfile.objects.create(user=self.employee)

    def management_login(self, username, password):
        return self.client.post(
            reverse('management_login'),
            {'username': username, 'password': password},
        )

    def test_accountant_can_enter_management_without_becoming_staff_or_superuser(self):
        self.assertFalse(self.accountant.is_staff)
        self.assertFalse(self.accountant.is_superuser)
        response = self.management_login('accountant', 'AccountantPass123!')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('management_dashboard'))
        response = self.client.get(reverse('management_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'حسابدار')

    def test_accountant_remains_in_employee_list(self):
        self.management_login('accountant', 'AccountantPass123!')
        response = self.client.get(reverse('management_employees'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'حسابدار')
        self.assertContains(response, '@accountant')

    def test_accountant_can_use_own_employee_calendar_and_record_work(self):
        self.client.force_login(self.accountant)
        response = self.client.post(
            reverse('save_day'),
            data='{"date":"2026-08-22","status":"work","overtime_hours":"2"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        from .models import WorkDay
        self.assertTrue(WorkDay.objects.filter(user=self.accountant, overtime_hours=2).exists())

    def test_limited_accountant_gets_only_assigned_management_permissions(self):
        self.accountant_profile.management_permissions = ['employees']
        self.accountant_profile.save(update_fields=['management_permissions'])
        self.management_login('accountant', 'AccountantPass123!')
        self.assertEqual(self.client.get(reverse('management_employees')).status_code, 200)
        self.assertEqual(self.client.get(reverse('management_dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin_payroll')).status_code, 403)

    def test_limited_accountant_cannot_view_as_another_employee(self):
        self.accountant_profile.management_permissions = ['employees', 'workdays_view']
        self.accountant_profile.save(update_fields=['management_permissions'])
        self.management_login('accountant', 'AccountantPass123!')
        response = self.client.post(reverse('management_view_as', args=[self.employee.pk]))
        self.assertEqual(response.status_code, 403)

    def test_full_accountant_can_view_as_employee(self):
        self.management_login('accountant', 'AccountantPass123!')
        response = self.client.post(reverse('management_view_as', args=[self.employee.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('calendar'))
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)

    def test_superuser_always_has_full_management_access(self):
        self.management_login('root', 'RootPass123!')
        for url_name in ('management_dashboard', 'management_employees', 'admin_payroll'):
            self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)


@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False, DEBUG=True)
class ApprovalDeductionAndEmployeeCreationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        from .models import EmployeeProfile, Department, WorkDay, MANAGEMENT_PERMISSION_KEYS
        self.manager = User.objects.create_user(username='manager', password='ManagerPass123!', first_name='سرپرست')
        self.employee = User.objects.create_user(username='worker', password='WorkerPass123!', first_name='کارمند')
        self.department = Department.objects.create(name='تولید')
        EmployeeProfile.objects.create(user=self.manager, is_accountant=True, department=self.department, management_permissions=list(MANAGEMENT_PERMISSION_KEYS))
        EmployeeProfile.objects.create(user=self.employee, department=self.department)
        self.WorkDay = WorkDay

    def login_management(self):
        return self.client.post(reverse('management_login'), {'username': 'manager', 'password': 'ManagerPass123!'})

    def test_new_workday_is_pending_and_manager_can_approve(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse('save_day'), data='{"date":"2026-08-22","status":"work","overtime_hours":"2"}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        wd = self.WorkDay.objects.get(user=self.employee)
        self.assertEqual(wd.approval_status, self.WorkDay.APPROVAL_PENDING)
        self.login_management()
        response = self.client.get(reverse('management_approvals') + '?date=2026-08-22')
        self.assertContains(response, 'کارمند')
        self.client.post(reverse('management_approve_workday', args=[wd.pk]))
        wd.refresh_from_db()
        self.assertEqual(wd.approval_status, self.WorkDay.APPROVAL_APPROVED)
        self.assertEqual(wd.approved_by, self.manager)

    def test_editing_workday_sends_it_back_to_pending(self):
        wd = self.WorkDay.objects.create(user=self.employee, date='2026-08-22', status='work', approval_status=self.WorkDay.APPROVAL_APPROVED)
        self.client.force_login(self.employee)
        self.client.post(reverse('save_day'), data='{"date":"2026-08-22","status":"night","overtime_hours":"1"}', content_type='application/json')
        wd.refresh_from_db()
        self.assertEqual(wd.approval_status, self.WorkDay.APPROVAL_PENDING)

    def test_management_can_add_deduction_and_dashboard_shows_total(self):
        self.login_management()
        response = self.client.post(reverse('management_add_deduction', args=[self.employee.pk]), {'amount':'1500000','date':'2026-08-22','reason':'خسارت'})
        self.assertEqual(response.status_code, 302)
        from .models import SalaryDeduction
        self.assertTrue(SalaryDeduction.objects.filter(user=self.employee, amount=1500000).exists())
        response = self.client.get(reverse('management_dashboard') + '?y=1405&m=5')
        self.assertContains(response, '1500000')

    def test_employee_can_add_self_deduction(self):
        self.client.force_login(self.employee)
        response = self.client.post(reverse('employee_add_self_deduction'), {'amount':'500000','date':'2026-08-22','reason':'ثبت توسط خودم'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('calendar'))
        from .models import SalaryDeduction
        self.assertTrue(SalaryDeduction.objects.filter(user=self.employee, amount=500000, created_by=self.employee).exists())

    def test_manager_can_create_employee_from_management(self):
        self.login_management()
        response = self.client.post(reverse('management_create_employee'), {'first_name':'نیروی جدید','last_name':'آزمایشی','username':'newworker','password':'NewWorkerPass123!','department':str(self.department.pk)})
        self.assertEqual(response.status_code, 302)
        User = get_user_model()
        new_user = User.objects.get(username='newworker')
        self.assertFalse(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)
        self.assertEqual(new_user.employee_profile.department, self.department)
