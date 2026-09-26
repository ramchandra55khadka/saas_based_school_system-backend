from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class BurstRateThrottle(UserRateThrottle):
    scope = 'burst'


class SustainedRateThrottle(UserRateThrottle):
    scope = 'sustained'


class LoginRateThrottle(AnonRateThrottle):
    scope = 'auth_login'


class RefreshRateThrottle(AnonRateThrottle):
    scope = 'auth_refresh'
