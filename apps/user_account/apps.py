from django.apps import AppConfig


class UserAccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.user_account'
    label = 'user_account'
    verbose_name = 'User Accounts'
