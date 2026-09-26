"""Regression tests for the communication module.

Despite the names, the five create endpoints all write an
``AbstractTenantModel`` row. ``AbstractTenantModel`` has no default tenant, so
an override of ``perform_create`` that only stamps ``sender``/``user``/etc.
leaves ``tenant_id`` NULL and the INSERT fails with an IntegrityError. The
fix: every override must also pass ``tenant=self.request.tenant``.

``StudentPost.student`` / ``TeacherAnnouncement.teacher`` are server-assigned
(the caller's own ``Student`` / ``Teacher`` record, never a client-supplied
id), and edits/deletes are limited to the author plus admin/principal/HOD.
"""
from django.urls import reverse

from apps.communication.models import Message, StudentPost, TeacherAnnouncement
from apps.core.tests import BaseTenantAPITestCase
from apps.students.models import Student
from apps.user_account.models import RoleChoices, TenantMembership
from apps.user_profile.models import UserProfile


class MessageTests(BaseTenantAPITestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls._subscribe(cls.tenant_a)
        cls.recipient = cls._user(
            "msg_recipient", "msg-recipient-pass-123", RoleChoices.TEACHER,
            "msg_recipient@example.com", is_superuser=False,
        )
        TenantMembership.objects.create(
            user=cls.recipient, tenant=cls.tenant_a, role=RoleChoices.TEACHER,
        )

    def test_admin_can_create_a_message_to_a_member(self):
        self.login(*self.admin_a_creds)
        response = self.client.post(
            reverse("message-list"),
            {
                "recipient": self.recipient.id,
                "subject": "Hello",
                "content": "Test body",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        msg = Message.objects.get(pk=response.data["id"])
        self.assertEqual(msg.tenant, self.tenant_a)
        self.assertEqual(msg.sender, self.admin_a)
        self.assertEqual(msg.recipient, self.recipient)

    def test_sending_to_a_non_member_is_rejected_with_400(self):
        self.login(*self.admin_a_creds)
        # admin_b belongs to tenant_b, not tenant_a.
        response = self.client.post(
            reverse("message-list"),
            {"recipient": self.admin_b.id, "subject": "Hi", "content": "body"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.content)


class StudentPostTests(BaseTenantAPITestCase):
    """Students create posts; the API links their own ``Student`` record."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls._subscribe(cls.tenant_a)
        cls.student_profile, _ = UserProfile.objects.get_or_create(
            user_account=cls.student_a,
            defaults={"first_name": "Student", "last_name": "A"},
        )
        cls.student_record = Student.objects.create(
            tenant=cls.tenant_a, user_profile=cls.student_profile, roll_number=1,
        )
        # Right role, but no Student row: create must fail with a clear 400.
        cls.student_b = cls._user(
            "student_b", "student-b-pass-123", RoleChoices.STUDENT,
            "student_b@example.com",
        )
        TenantMembership.objects.create(
            user=cls.student_b, tenant=cls.tenant_a, role=RoleChoices.STUDENT,
        )

    def _create(self, **extra):
        payload = {"title": "Homework help", "content": "Meet in the library."}
        payload.update(extra)
        return self.client.post(reverse("student-post-list"), payload, format="json")

    def test_student_can_create_a_post_linked_to_their_own_record(self):
        self.login(*self.student_a_creds)
        response = self._create()
        self.assertEqual(response.status_code, 201, response.content)
        post = StudentPost.objects.get(pk=response.data["id"])
        self.assertEqual(post.tenant, self.tenant_a)
        self.assertEqual(post.student, self.student_record)
        self.assertTrue(response.data["is_author"])
        self.assertEqual(response.data["student"], self.student_record.id)

    def test_client_cannot_forge_the_student_field(self):
        """``student`` is read-only: a supplied id must be ignored."""
        self.login(*self.student_a_creds)
        response = self._create(student=999999)
        self.assertEqual(response.status_code, 201, response.content)
        post = StudentPost.objects.get(pk=response.data["id"])
        self.assertEqual(post.student, self.student_record)

    def test_non_student_cannot_create_a_student_post(self):
        self.login(*self.teacher_a_creds)
        response = self._create()
        self.assertEqual(response.status_code, 403, response.content)

    def test_student_without_a_linked_profile_gets_a_clear_400(self):
        self.login("student_b", "student-b-pass-123")
        response = self._create()
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("No student record is linked", str(response.data["student"]))

    def test_author_can_edit_and_delete_their_post(self):
        post = StudentPost.objects.create(
            tenant=self.tenant_a, student=self.student_record,
            title="Old", content="Old body",
        )
        self.login(*self.student_a_creds)
        patch = self.client.patch(
            reverse("student-post-detail", args=[post.id]),
            {"title": "New"}, format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.content)
        delete = self.client.delete(reverse("student-post-detail", args=[post.id]))
        self.assertEqual(delete.status_code, 204, delete.content)

    def test_another_member_cannot_edit_someone_elses_post(self):
        post = StudentPost.objects.create(
            tenant=self.tenant_a, student=self.student_record,
            title="Mine", content="Mine",
        )
        self.login(*self.parent_a_creds)
        patch = self.client.patch(
            reverse("student-post-detail", args=[post.id]),
            {"title": "Hijacked"}, format="json",
        )
        self.assertEqual(patch.status_code, 403, patch.content)
        delete = self.client.delete(reverse("student-post-detail", args=[post.id]))
        self.assertEqual(delete.status_code, 403, delete.content)

    def test_admin_can_moderate_any_post(self):
        post = StudentPost.objects.create(
            tenant=self.tenant_a, student=self.student_record,
            title="Post", content="Body",
        )
        self.login(*self.admin_a_creds)
        patch = self.client.patch(
            reverse("student-post-detail", args=[post.id]),
            {"content": "Edited by admin"}, format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.content)

    def test_other_schools_post_is_invisible_to_this_admin(self):
        self._subscribe(self.tenant_b)  # else the feature gate answers first
        post = StudentPost.objects.create(
            tenant=self.tenant_a, student=self.student_record,
            title="Alpha only", content="…",
        )
        self.login(*self.admin_b_creds)  # admin of tenant_b
        patch = self.client.patch(
            reverse("student-post-detail", args=[post.id]),
            {"title": "Nope"}, format="json",
        )
        self.assertEqual(patch.status_code, 404, patch.content)

    def test_list_marks_the_callers_own_posts_as_author(self):
        StudentPost.objects.create(
            tenant=self.tenant_a, student=self.student_record,
            title="Mine", content="…",
        )
        self.login(*self.parent_a_creds)
        response = self.client.get(reverse("student-post-list"))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data), 1)
        self.assertFalse(response.data[0]["is_author"])


class TeacherAnnouncementTests(BaseTenantAPITestCase):
    """Teaching staff announce; the API links their own ``Teacher`` record."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls._subscribe(cls.tenant_a)
        # Base fixture already builds cls.teacher_a_profile (a Teacher in tenant_a).
        # Right role, but no Teacher row: create must fail with a clear 400.
        cls.teacher_norow = cls._user(
            "teacher_norow", "teacher-norow-pass-123", RoleChoices.TEACHER,
            "teacher_norow@example.com",
        )
        TenantMembership.objects.create(
            user=cls.teacher_norow, tenant=cls.tenant_a, role=RoleChoices.TEACHER,
        )

    def _create(self, **extra):
        payload = {"title": "Field trip", "content": "Forms due Friday."}
        payload.update(extra)
        return self.client.post(reverse("teacher-announcement-list"), payload, format="json")

    def test_teacher_can_create_an_announcement_linked_to_their_record(self):
        self.login(*self.teacher_a_creds)
        response = self._create()
        self.assertEqual(response.status_code, 201, response.content)
        row = TeacherAnnouncement.objects.get(pk=response.data["id"])
        self.assertEqual(row.tenant, self.tenant_a)
        self.assertEqual(row.teacher, self.teacher_a_profile)
        self.assertTrue(response.data["is_author"])

    def test_client_cannot_forge_the_teacher_field(self):
        self.login(*self.teacher_a_creds)
        response = self._create(teacher=999999)
        self.assertEqual(response.status_code, 201, response.content)
        row = TeacherAnnouncement.objects.get(pk=response.data["id"])
        self.assertEqual(row.teacher, self.teacher_a_profile)

    def test_student_cannot_create_a_teacher_announcement(self):
        self.login(*self.student_a_creds)
        response = self._create()
        self.assertEqual(response.status_code, 403, response.content)

    def test_teaching_role_without_a_teaching_record_gets_a_clear_400(self):
        self.login("teacher_norow", "teacher-norow-pass-123")
        response = self._create()
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("No teaching record is linked", str(response.data["teacher"]))

    def test_author_can_edit_and_delete_their_announcement(self):
        row = TeacherAnnouncement.objects.create(
            tenant=self.tenant_a, teacher=self.teacher_a_profile,
            title="Old", content="Old body",
        )
        self.login(*self.teacher_a_creds)
        patch = self.client.patch(
            reverse("teacher-announcement-detail", args=[row.id]),
            {"title": "New"}, format="json",
        )
        self.assertEqual(patch.status_code, 200, patch.content)
        delete = self.client.delete(reverse("teacher-announcement-detail", args=[row.id]))
        self.assertEqual(delete.status_code, 204, delete.content)

    def test_student_cannot_edit_a_teacher_announcement(self):
        row = TeacherAnnouncement.objects.create(
            tenant=self.tenant_a, teacher=self.teacher_a_profile,
            title="Mine", content="Mine",
        )
        self.login(*self.student_a_creds)
        patch = self.client.patch(
            reverse("teacher-announcement-detail", args=[row.id]),
            {"title": "Hijacked"}, format="json",
        )
        self.assertEqual(patch.status_code, 403, patch.content)