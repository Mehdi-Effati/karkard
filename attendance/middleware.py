from .views import _get_management_user
from .models import MANAGEMENT_PERMISSION_KEYS


class ManagementIdentityMiddleware:
    """Expose the independent management identity on every management request.

    The employee Django session (request.user) is intentionally not used as the
    management identity.  Initialising the attribute here also makes templates
    safe on production requests where no management cookie exists.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.management_user = None
        request.management_permissions = []
        if request.path.startswith('/management/') or request.path.startswith('/admin/payroll/'):
            request.management_user = _get_management_user(request)
            if request.management_user:
                if request.management_user.is_superuser:
                    request.management_permissions = list(MANAGEMENT_PERMISSION_KEYS)
                else:
                    profile = getattr(request.management_user, 'employee_profile', None)
                    request.management_permissions = list(profile.management_permissions or MANAGEMENT_PERMISSION_KEYS) if profile else []
        return self.get_response(request)
