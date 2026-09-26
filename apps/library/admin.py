from django.contrib import admin

from .models import Book, BookCategory, BookCopy, BookIssue, LibraryMember


@admin.register(LibraryMember)
class LibraryMemberAdmin(admin.ModelAdmin):
    list_display = ['card_number', 'member_type', 'tenant', 'is_active']
    list_filter = ['tenant', 'member_type', 'is_active']
    search_fields = ['card_number']


@admin.register(BookCategory)
class BookCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant']
    list_filter = ['tenant']
    search_fields = ['name']


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'isbn', 'category', 'tenant']
    list_filter = ['tenant', 'category']
    search_fields = ['title', 'isbn', 'authors']


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ['book', 'accession_number', 'status', 'tenant']
    list_filter = ['tenant', 'status']
    search_fields = ['book__title', 'accession_number']


@admin.register(BookIssue)
class BookIssueAdmin(admin.ModelAdmin):
    list_display = ['member', 'book_copy', 'issued_at', 'due_date', 'returned_at', 'status']
    list_filter = ['tenant', 'status', 'issued_at']
    date_hierarchy = 'issued_at'
