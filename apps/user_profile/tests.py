"""Tests for personal profiles and the shared onboarding base."""
from django.test import SimpleTestCase

from apps.user_profile.models import UserProfile
from apps.user_profile.serializers import (
    PROFILE_ONBOARD_FIELDS,
    AccountProfileOnboardSerializer,
)


class OnboardingFieldCoverageTests(SimpleTestCase):
    """The onboarding payload must fill every column of the model it owns.

    ``POST .../onboard/`` promises "all the UserProfile fields"; these tests
    fail if a column is added to the model (or dropped from the serializer)
    without the endpoint following along.
    """

    def test_profile_onboard_fields_match_the_model(self):
        """``uuid`` is generated; account/timestamps are bookkeeping."""
        self.assertEqual(
            set(PROFILE_ONBOARD_FIELDS),
            {
                field.name for field in UserProfile._meta.fields
            }
            - {"id", "uuid", "user_account", "created_at", "updated_at"},
        )

    def test_every_profile_column_is_a_declared_input_field(self):
        """``create()`` pops PROFILE_FIELDS, so each must be a declared field."""
        declared = set(AccountProfileOnboardSerializer().fields)
        self.assertTrue(set(PROFILE_ONBOARD_FIELDS) <= declared)
