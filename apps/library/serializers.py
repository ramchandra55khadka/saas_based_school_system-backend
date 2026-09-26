from rest_framework import serializers

from .models import Book, BookCategory, BookCopy, BookIssue, LibraryMember


class LibraryMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = LibraryMember
        fields = '__all__'
        read_only_fields = ['tenant']


class BookCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCategory
        fields = '__all__'
        read_only_fields = ['tenant']


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = '__all__'
        read_only_fields = ['tenant']


class BookCopySerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCopy
        fields = '__all__'
        read_only_fields = ['tenant']


class BookIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookIssue
        fields = '__all__'
        read_only_fields = ['tenant']
