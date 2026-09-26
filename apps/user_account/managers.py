from django.contrib.auth.models import UserManager


class UserAccountManager(UserManager):
    """User manager that keeps Django auth internals on uuid.

    The application login is tenant + email. ``username`` is a generated/display
    field and is intentionally not globally unique, so Django's USERNAME_FIELD is
    ``uuid``. Existing call sites may still pass ``username=...`` to set that
    display value.
    """

    def create_user(self, uuid=None, email=None, password=None, **extra_fields):
        return self._create_user(uuid, email, password, **extra_fields)

    def create_superuser(self, uuid=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(uuid, email, password, **extra_fields)

    def _create_user(self, uuid, email, password, **extra_fields):
        email = self.normalize_email(email)
        username = extra_fields.pop('username', None)
        if not username:
            username = self.model.generate_unique_username(email)
        # Only forward ``uuid`` when the caller actually supplied one. Passing
        # ``uuid=None`` explicitly would override the field's ``default=uuid4``
        # and violate the NOT NULL constraint.
        if uuid is not None:
            extra_fields['uuid'] = uuid
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
