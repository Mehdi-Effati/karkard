from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.cache import patch_vary_headers


class SeparateAdminSessionMiddleware(SessionMiddleware):
    """Give Django's technical /admin/ panel its own session cookie.

    The employee application keeps Django's normal session cookie, while the
    built-in Django admin uses ADMIN_SESSION_COOKIE_NAME. This lets one browser
    be logged in as an employee and as a Django admin at the same time without
    either authentication state replacing the other.

    /admin/payroll/ intentionally remains part of the application's management
    realm and continues to use the normal employee session plus management
    identity cookie.
    """

    ADMIN_COOKIE_NAME = 'karkard_admin_sessionid'

    def _is_technical_admin(self, request):
        return request.path == '/admin' or request.path.startswith('/admin/') and not request.path.startswith('/admin/payroll/')

    def _cookie_name(self, request):
        if self._is_technical_admin(request):
            return self.ADMIN_COOKIE_NAME
        return settings.SESSION_COOKIE_NAME

    def process_request(self, request):
        session_key = request.COOKIES.get(self._cookie_name(request))
        request.session = self.SessionStore(session_key)

    def process_response(self, request, response):
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        cookie_name = self._cookie_name(request)
        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            patch_vary_headers(response, ('Cookie',))
            return response

        if accessed:
            patch_vary_headers(response, ('Cookie',))
        if modified and not empty:
            if response.status_code < 500:
                try:
                    request.session.save()
                except Exception:
                    request.session = self.SessionStore()
                    request.session.save()
                response.set_cookie(
                    cookie_name,
                    request.session.session_key,
                    max_age=settings.SESSION_COOKIE_AGE,
                    domain=settings.SESSION_COOKIE_DOMAIN,
                    path=settings.SESSION_COOKIE_PATH,
                    secure=settings.SESSION_COOKIE_SECURE,
                    httponly=settings.SESSION_COOKIE_HTTPONLY,
                    samesite=settings.SESSION_COOKIE_SAMESITE,
                )
        elif cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
        return response
