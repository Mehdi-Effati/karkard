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
        self.assertNotContains(response, '@employee')

    def test_view_as_overrides_employee_session_when_management_is_active(self):
        self.client.force_login(self.employee)
        self.client.post(
            reverse('management_login'),
            {'username': 'admin2', 'password': 'AdminPass123!'},
        )
        response = self.client.post(reverse('management_view_as', args=[self.employee.pk]))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('calendar'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.employee.first_name or 'employee')

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
