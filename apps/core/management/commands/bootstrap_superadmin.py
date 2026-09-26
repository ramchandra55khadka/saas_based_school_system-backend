"""Create (or update) the platform super admin from SUPERADMIN_* environment variables.

    python manage.py bootstrap_superadmin

Reads SUPERADMIN_USERNAME / SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD from the
environment (or .env via python-decouple). Idempotent: safe to run on every
deploy — it promotes the user to super_admin/staff and (optionally) resets the
password, but never creates duplicates.

This closes the manual-bootstrap gap: onboarding a fresh deployment is now a
single command instead of a hand-typed shell session.
"""
from decouple import config
from django.core.management.base import BaseCommand

from apps.user_account.models import UserAccount


class Command(BaseCommand):
    help = (
        "Create or update the platform super admin from SUPERADMIN_USERNAME / "
        "SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD environment variables."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", default=config("SUPERADMIN_USERNAME", default="superadmin"),
            help="Username of the super admin (default: SUPERADMIN_USERNAME).",
        )
        parser.add_argument(
            "--email", default=config("SUPERADMIN_EMAIL", default="superadmin@example.com"),
            help="Email of the super admin (default: SUPERADMIN_EMAIL).",
        )
        parser.add_argument(
            "--password", default=config("SUPERADMIN_PASSWORD", default=""),
            help="Password (default: SUPERADMIN_PASSWORD). Required when creating a new user.",
        )
        parser.add_argument(
            "--force-password", action="store_true",
            help="Reset the password even if the user already exists.",
        )

    def handle(self, *args, **opts):
        username = opts["username"]
        email = opts["email"]
        password = opts["password"]

        user, created = UserAccount.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        if created and not password:
            self.stderr.write(
                f"User '{username}' does not exist and no password was provided. "
                "Set SUPERADMIN_PASSWORD (or pass --password)."
            )
            raise SystemExit(1)

        # Always reconcile identity fields, so config drift cannot lock the
        # platform admin out.
        user.email = email
        user.is_staff = True
        user.is_superuser = True

        if created or opts["force_password"]:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"{'Created' if created else 'Reset password for'} super admin '{username}' <{email}>"
            ))
        else:
            user.save(update_fields=["email", "is_staff", "is_superuser"])
            self.stdout.write(self.style.SUCCESS(
                f"Super admin '{username}' already exists — ensured email/staff flags."
            ))
