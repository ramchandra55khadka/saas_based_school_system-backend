from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BookCategoryViewSet,
    BookCopyViewSet,
    BookIssueViewSet,
    BookViewSet,
    LibraryMemberViewSet,
)

router = DefaultRouter()
router.register(r'members', LibraryMemberViewSet, basename='library-member')
router.register(r'categories', BookCategoryViewSet, basename='book-category')
router.register(r'books', BookViewSet, basename='book')
router.register(r'copies', BookCopyViewSet, basename='book-copy')
router.register(r'issues', BookIssueViewSet, basename='book-issue')

urlpatterns = [
    path('', include(router.urls)),
]
