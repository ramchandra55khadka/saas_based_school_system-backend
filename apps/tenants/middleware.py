from django.conf import settings
from django.core.exceptions import DisallowedHost

from .models import Tenant


class TenantMiddleware:
    """Resolve the active school from the request host.

    A request to ``abc-school.edunexus.com`` gets ``request.tenant`` attached
    to the ``Tenant`` whose slug is ``abc-school``. Platform hosts such as the
    bare domain, localhost, and configured API hosts deliberately leave
    ``request.tenant`` unset so platform-level routes keep working.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        slug = self._slug_from_request(request)
        request.tenant_slug = slug
        request.tenant = None

        if slug:
            request.tenant = (
                Tenant.objects.filter(slug__iexact=slug, is_active=True).first()
            )

        return self.get_response(request)

    @classmethod
    def _slug_from_request(cls, request):
        host = cls._forwarded_host(request)
        if not host:
            try:
                host = request.get_host()
            except DisallowedHost:
                return None

        hostname = host.split(':', 1)[0].strip().lower().rstrip('.')
        if not hostname or cls._is_platform_host(hostname):
            return None

        root_domain = getattr(settings, 'TENANT_ROOT_DOMAIN', '').strip().lower()
        if root_domain:
            root_domain = root_domain.lstrip('.')
            suffix = f'.{root_domain}'
            if hostname.endswith(suffix):
                return hostname[: -len(suffix)].split('.')[-1] or None
            return None

        parts = hostname.split('.')
        if len(parts) >= 3:
            return parts[0]
        return None

    @staticmethod
    def _forwarded_host(request):
        return (
            request.META.get('HTTP_X_TENANT_HOST')
            or request.META.get('HTTP_X_FORWARDED_HOST', '').split(',', 1)[0]
        )

    @staticmethod
    def _is_platform_host(hostname):
        platform_hosts = {
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            'testserver',
        }
        configured = getattr(settings, 'TENANT_PLATFORM_HOSTS', [])
        platform_hosts.update(h.lower() for h in configured)
        return hostname in platform_hosts
