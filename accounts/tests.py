from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from tenants.models import Tenant
from .models import User

class AccountsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_creates_org_and_user(self):
        data = {
            "username": "hod1",
            "email": "hod1@example.com",
            "password": "pass1234",
            "org_name": "Test School",
            "org_reg_no": "TS-1001",
            "role": "hod"
        }
        resp = self.client.post(reverse("signup"), data, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Tenant.objects.filter(org_code="TS-1001").exists())
        self.assertTrue(User.objects.filter(username="hod1").exists())

    def test_login_sets_cookies(self):
        # first create org and user
        org = Tenant.objects.create(tenant_name="O", org_code="OR-1")
        user = User.objects.create_user(username="u1", password="pwd")
        # Create membership
        from .models import TenantMembership
        TenantMembership.objects.create(user=user, tenant=org, role="hod")
        resp = self.client.post(reverse("token_obtain_pair"), {"username":"u1","password":"pwd"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access", resp.cookies)  # access cookie present
        self.assertIn("refresh", resp.cookies)
