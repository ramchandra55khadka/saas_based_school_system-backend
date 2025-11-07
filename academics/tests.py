from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse
from tenants.models import Tenant
from accounts.models import User, TenantMembership
from .models import Course

class AcademicsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # create two orgs
        self.org1 = Tenant.objects.create(tenant_name="Org1", org_code="O1")
        self.org2 = Tenant.objects.create(tenant_name="Org2", org_code="O2")
        # hod user in org1
        self.hod = User.objects.create_user(username="hod1", password="pwd", role="hod")
        TenantMembership.objects.create(user=self.hod, tenant=self.org1, role="hod")
        # teacher in org1
        self.teacher = User.objects.create_user(username="t1", password="pwd", role="teacher")
        TenantMembership.objects.create(user=self.teacher, tenant=self.org1, role="teacher")
        # student in org1
        self.student = User.objects.create_user(username="s1", password="pwd", role="student")
        TenantMembership.objects.create(user=self.student, tenant=self.org1, role="student")
        # hod in org2
        self.hod2 = User.objects.create_user(username="hod2", password="pwd", role="hod")
        TenantMembership.objects.create(user=self.hod2, tenant=self.org2, role="hod")

    def obtain_cookie(self, username, password):
        resp = self.client.post(reverse("token_obtain_pair"), {"username": username, "password": password}, format="json")
        self.assertEqual(resp.status_code, 200)
        # cookies set by view
        access_cookie = resp.client.cookies.get("access")
        self.assertIsNotNone(access_cookie)
        return resp.client.cookies

    def test_hod_can_create_course_and_batch(self):
        cookies = self.obtain_cookie("hod1", "pwd")
        # set cookie in client for subsequent requests
        self.client.cookies = cookies
        # create course
        resp = self.client.post(reverse("course-list"), {"name": "Math", "code": "M101", "credits": 4}, format="json")
        self.assertEqual(resp.status_code, 201)
        # create batch
        resp = self.client.post(reverse("batch-list"), {"name":"B1","academic_year":"2024","total_students":30,"section":"A","program":"Science"}, format="json")
        self.assertEqual(resp.status_code, 201)

    def test_student_cannot_create_course(self):
        cookies = self.obtain_cookie("s1", "pwd")
        self.client.cookies = cookies
        resp = self.client.post(reverse("course-list"), {"name": "Eng","code":"E101"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_tenant_isolation(self):
        # hod1 creates a course in org1
        cookies1 = self.obtain_cookie("hod1", "pwd")
        self.client.cookies = cookies1
        self.client.post(reverse("course-list"), {"name":"Org1Course","code":"OC1"}, format="json")
        # hod2 creates course in org2
        cookies2 = self.obtain_cookie("hod2", "pwd")
        self.client.cookies = cookies2
        self.client.post(reverse("course-list"), {"name":"Org2Course","code":"OC2"}, format="json")

        # list courses as hod1 -> only Org1Course
        self.client.cookies = cookies1
        resp = self.client.get(reverse("course-list"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(any(c["code"] == "OC1" for c in data))
        self.assertFalse(any(c["code"] == "OC2" for c in data))
