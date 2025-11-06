# from django.conf import settings
# from django.utils.deprecation import MiddlewareMixin
# from .models import Organization


# class JwtCookieMiddleware(MiddlewareMixin):
#     """
#     Copies HttpOnly JWT cookies into Authorization header.
#     """

#     def process_request(self, request):
#         access_cookie = request.COOKIES.get(getattr(settings, "JWT_ACCESS_COOKIE", "access"))
#         if access_cookie and "HTTP_AUTHORIZATION" not in request.META:
#             request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_cookie}"





# accounts/middleware.py
import jwt
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()


class JWTCookieToHeaderMiddleware(MiddlewareMixin):
    """
    Moves JWT from HttpOnly cookie → Authorization header.
    Enables DRF JWTAuthentication to read token.
    """
    def process_request(self, request):
        cookie_name = getattr(settings, "JWT_ACCESS_COOKIE", "access_token")
        token = request.COOKIES.get(cookie_name)
        if token and "HTTP_AUTHORIZATION" not in request.META:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"


class JWTAuthenticationMiddleware(MiddlewareMixin):
    """
    Authenticates user from JWT (header or cookie) and injects active_tenant_id.
    Works with HttpOnly cookies + DRF.
    """
    def process_request(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            request.user = None
            return

        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token expired")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Invalid token")

        try:
            request.user = User.objects.only("id").get(id=payload["user_id"])
        except User.DoesNotExist:
            raise AuthenticationFailed("User not found")

        # Forward tenant claim
        request.active_tenant_id = payload.get("active_tenant_id")