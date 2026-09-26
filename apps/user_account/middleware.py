# user_account/middleware.py
from django.conf import settings
from loguru import logger


class CustomJWTMiddleware:
    """
    Copies JWT from HttpOnly cookie to Authorization header.
    Enables DRF JWTAuthentication to read the token.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Per-request DEBUG logging is a development aid only — it would flood
        # production logs (and leak token prefixes).
        self.verbose = settings.DEBUG

    def __call__(self, request):
        cookie_name = getattr(settings, "JWT_ACCESS_COOKIE", "access")
        token = request.COOKIES.get(cookie_name)

        if self.verbose:
            logger.debug(f"Checking cookie: {cookie_name}")
            if token:
                logger.debug(f"JWT found in cookie: {token[:15]}...")
            else:
                logger.debug("No JWT in cookies")

        # Only set header if not already present
        if token and "HTTP_AUTHORIZATION" not in request.META:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
            if self.verbose:
                logger.debug("Copied JWT to Authorization header")

        return self.get_response(request)


class CookieJWTCSRFMiddleware:
    """Require a double-submit CSRF token for unsafe cookie-auth requests."""

    SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS', 'TRACE'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method.upper() not in self.SAFE_METHODS and self._has_auth_cookie(request):
            cookie_token = request.COOKIES.get(getattr(settings, 'JWT_CSRF_COOKIE', 'csrf_token'))
            header_token = request.META.get('HTTP_X_CSRFTOKEN')
            if not cookie_token or not header_token or cookie_token != header_token:
                from django.http import JsonResponse

                return JsonResponse({'message': 'CSRF verification failed'}, status=403)
        return self.get_response(request)

    @staticmethod
    def _has_auth_cookie(request):
        return bool(
            request.COOKIES.get(getattr(settings, 'JWT_ACCESS_COOKIE', 'access'))
            or request.COOKIES.get(getattr(settings, 'JWT_REFRESH_COOKIE', 'refresh'))
        )
