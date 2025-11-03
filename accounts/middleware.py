from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from .models import Organization


class JwtCookieMiddleware(MiddlewareMixin):
    """
    Copies HttpOnly JWT cookies into Authorization header.
    """

    def process_request(self, request):
        access_cookie = request.COOKIES.get(getattr(settings, "JWT_ACCESS_COOKIE", "access"))
        if access_cookie and "HTTP_AUTHORIZATION" not in request.META:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_cookie}"


class CurrentOrgMiddleware(MiddlewareMixin):
    """
    Resolves current organization from header, query param, or user.
    """
    def process_request(self, request):
        request.org = None
        reg = request.headers.get("X-ORG-REG") or request.GET.get("org")

        if reg:
            request.org = Organization.objects.filter(org_reg_no=reg).first()
            return

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            request.org = getattr(user, "organization", None)
