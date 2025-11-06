from rest_framework import serializers
from django.contrib.auth import get_user_model
from tenants.models import Tenant
from .models import User
from accounts.models import TenantMembership, RoleChoices



# --------------------------------
# Tenant Serializer (optional for API response)
# --------------------------------
class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["tenant_id", "tenant_name", "org_code", "created_at"]
        read_only_fields = ["tenant_id", "created_at"]


# --------------------------------
# User Serializer
# --------------------------------
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=[r.value for r in RoleChoices])

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "role", "date_joined", "password"
        ]
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
# Signup Serializer (Super-admin creates tenant + initial admin)
# --------------------------------
class SignupSerializer(serializers.Serializer):
    tenant_name = serializers.CharField()
    org_code = serializers.CharField()
    admin_username = serializers.CharField()
    admin_email = serializers.EmailField()
    admin_password = serializers.CharField(write_only=True)

    def create(self, validated_data):
        # 1️⃣ Create Tenant
        tenant = Tenant.objects.create(
            tenant_name=validated_data["tenant_name"],
            org_code=validated_data["org_code"]
        )

        # 2️⃣ Create initial admin user
        admin_user = User.objects.create(
            username=validated_data["admin_username"],
            email=validated_data["admin_email"],
            role=RoleChoices.ADMIN
        )
        admin_user.set_password(validated_data["admin_password"])
        admin_user.save()

        # 3️⃣ Link user to tenant via TenantMembership
        TenantMembership.objects.create(
            user=admin_user,
            tenant=tenant,
            role=RoleChoices.ADMIN,
            is_active=True
        )

        return {"tenant": tenant, "admin_user": admin_user}
