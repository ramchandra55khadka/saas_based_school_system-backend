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
