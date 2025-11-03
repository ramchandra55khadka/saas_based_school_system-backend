from rest_framework import serializers
from .models import User, Organization

# --------------------------------
# Organization Serializer
# --------------------------------
class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "org_name", "org_reg_no", "created_at"]
        read_only_fields = ["id", "created_at"]


# --------------------------------
# User Serializer
# --------------------------------
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    ROLE_CHOICES = ["super-admin", "admin", "hod", "teacher", "student"]
    role = serializers.ChoiceField(choices=ROLE_CHOICES)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name",
                  "role", "organization", "date_joined", "password"]
        read_only_fields = ["id", "date_joined"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


# --------------------------------
# Signup Serializer (Org + Initial Admin)
# --------------------------------
class SignupSerializer(serializers.Serializer):
    org_name = serializers.CharField()
    org_reg_no = serializers.CharField()
    admin_username = serializers.CharField()
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(write_only=True)

    def create(self, validated_data):
        # Create Organization
        org = Organization.objects.create(
            org_name=validated_data["org_name"],
            org_reg_no=validated_data["org_reg_no"]
        )

        # Create initial admin
        user = User.objects.create(
            username=validated_data["admin_username"],
            email=validated_data["admin_email"],
            role="admin",
            organization=org
        )
        user.set_password(validated_data["admin_password"])
        user.save()

        return {"user": user, "org": org}
