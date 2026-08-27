# Karkard V11

Fixes the V10 regression where accountant users were marked as staff by migration but test-created accountant profiles were not synchronized with `User.is_staff`.

`EmployeeProfile.save()` now guarantees that `is_accountant=True` also sets `User.is_staff=True` while leaving `is_superuser=False` unchanged.

This preserves the intended model:
- Superuser: staff + superuser
- Accountant: staff + not superuser + employee profile accountant
- Regular employee: not staff + not superuser

Accountants remain in employee/workday lists because management employee queries explicitly include accountant staff users.
