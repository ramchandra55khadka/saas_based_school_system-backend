from django.contrib.auth.models import UserManager


class UserAccountManager(UserManager):
    """Default manager for :class:`~user_account.models.UserAccount`.

    Subclasses Django's ``UserManager`` unchanged so ``create_user`` /
    ``create_superuser`` keep their usual username+email+password semantics
    (login still verifies the stored password hash through ``ModelBackend``).
    Having a dedicated class gives the account model a home for future
    helpers, e.g. verified-account querysets.
    """
