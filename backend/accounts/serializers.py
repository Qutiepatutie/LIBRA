from rest_framework import serializers

from .models import UserLogin, UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "first_name",
            "last_name",
            "program",
            "id_number",
        ]


class UserLoginSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = UserLogin
        fields = [
            "id",
            "email",
            "role",
            "profile",
        ]