from apps.core.mixins import TenantViewSet

from .models import Book, BookCategory, BookCopy, BookIssue, LibraryMember
from .serializers import (
    BookCategorySerializer,
    BookCopySerializer,
    BookIssueSerializer,
    BookSerializer,
    LibraryMemberSerializer,
)


class LibraryMemberViewSet(TenantViewSet):
    queryset = LibraryMember.objects.select_related('student', 'staff')
    serializer_class = LibraryMemberSerializer


class BookCategoryViewSet(TenantViewSet):
    queryset = BookCategory.objects.all()
    serializer_class = BookCategorySerializer


class BookViewSet(TenantViewSet):
    queryset = Book.objects.select_related('category')
    serializer_class = BookSerializer


class BookCopyViewSet(TenantViewSet):
    queryset = BookCopy.objects.select_related('book')
    serializer_class = BookCopySerializer


class BookIssueViewSet(TenantViewSet):
    queryset = BookIssue.objects.select_related('member', 'book_copy', 'issued_by')
    serializer_class = BookIssueSerializer
