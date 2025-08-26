from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Subscription, SubscriptionPlan
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


User = get_user_model()

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(**validated_data, password=password)

        # Assign default plan ("Free")
        try:
            free_plan = SubscriptionPlan.objects.get(name="Free")
        except SubscriptionPlan.DoesNotExist:
            free_plan = SubscriptionPlan.objects.create(
                name="Free",
                description="Default free tier",
                price=0,
                features={"max_messages": 10, "analytics": False},
            )
        Subscription.objects.create(user=user, plan=free_plan, is_active=True)

        return user



class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        if not self.user.is_verified:
            raise serializers.ValidationError("Account not verified. Please complete OTP verification.")

        return data