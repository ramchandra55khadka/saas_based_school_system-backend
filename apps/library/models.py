from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import ensure_same_tenant, AbstractTenantModel
from apps.staff.models import Staff
from apps.students.models import Student
from utils.abstract_model import AbstractTimeStampedModel
from .constants import (
    BOOK_COPY_DEFAULT_STATUS,
    BOOK_COPY_STATUS_CHOICES,
    BOOK_ISSUE_DEFAULT_STATUS,
    BOOK_ISSUE_RETURNED,
    BOOK_ISSUE_STATUS_CHOICES,
    MEMBER_TYPE_CHOICES,
    MEMBER_TYPE_STAFF,
    MEMBER_TYPE_STUDENT,
)


class LibraryMember(AbstractTenantModel, AbstractTimeStampedModel):
    """A school user who can borrow library resources."""
    member_type = models.CharField(max_length=20, choices=MEMBER_TYPE_CHOICES)
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='library_member',
    )
    staff = models.OneToOneField(
        Staff,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='library_member',
    )
    card_number = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['card_number']
        verbose_name = 'Library Member'
        verbose_name_plural = 'Library Members'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'card_number'],
                name='unique_library_card_per_school',
            )
        ]

    def __str__(self):
        return self.card_number

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'student', 'staff')
        if self.member_type == MEMBER_TYPE_STUDENT and not self.student_id:
            raise ValidationError({'student': 'Student member requires a student profile.'})
        if self.member_type == MEMBER_TYPE_STAFF and not self.staff_id:
            raise ValidationError({'staff': 'Staff member requires a staff profile.'})
        if self.student_id and self.staff_id:
            raise ValidationError('Library member cannot be both student and staff.')


class BookCategory(AbstractTenantModel, AbstractTimeStampedModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Book Category'
        verbose_name_plural = 'Book Categories'
        unique_together = ('tenant', 'name')

    def __str__(self):
        return self.name


class Book(AbstractTenantModel, AbstractTimeStampedModel):
    title = models.CharField(max_length=255)
    isbn = models.CharField(max_length=20, blank=True)
    category = models.ForeignKey(
        BookCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books',
    )
    authors = models.CharField(max_length=255, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    published_year = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['title']
        verbose_name = 'Book'
        verbose_name_plural = 'Books'

    def __str__(self):
        return self.title


class BookCopy(AbstractTenantModel, AbstractTimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='copies')
    accession_number = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=BOOK_COPY_STATUS_CHOICES,
        default=BOOK_COPY_DEFAULT_STATUS,
    )

    class Meta:
        ordering = ['accession_number']
        verbose_name = 'Book Copy'
        verbose_name_plural = 'Book Copies'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'accession_number'],
                name='unique_book_accession_per_school',
            )
        ]

    def __str__(self):
        return f'{self.book.title} - {self.accession_number}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'book')


class BookIssue(AbstractTenantModel, AbstractTimeStampedModel):
    member = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name='issues',
    )
    book_copy = models.ForeignKey(
        BookCopy,
        on_delete=models.CASCADE,
        related_name='issues',
    )
    issued_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_books',
    )
    issued_at = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    returned_at = models.DateField(null=True, blank=True)
    fine_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=BOOK_ISSUE_STATUS_CHOICES,
        default=BOOK_ISSUE_DEFAULT_STATUS,
    )

    class Meta:
        ordering = ['-issued_at']
        verbose_name = 'Book Issue'
        verbose_name_plural = 'Book Issues'

    def __str__(self):
        return f'{self.member} - {self.book_copy}'

    def clean(self):
        super().clean()
        ensure_same_tenant(self, 'member', 'book_copy', 'issued_by')
        if self.status == BOOK_ISSUE_RETURNED and not self.returned_at:
            raise ValidationError({'returned_at': 'Returned issues must include a return date.'})
