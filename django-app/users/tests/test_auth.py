import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.oath import totp
import time

pytestmark = pytest.mark.django_db


class TestAuthFlow:
    def setup_method(self):
        self.client = APIClient()

    def test_signup_creates_user_and_subscription(self):
        """Signup should create a new user and require OTP before issuing tokens."""
        resp = self.client.post(
            "/auth/signup/",
            {
                "email": "newuser@example.com",
                "password": "strongpass123",
                "first_name": "New",
                "last_name": "User",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["otp_required"] is True
        assert "access" not in data

    def test_login_requires_correct_password(self, django_user_model):
        """Login with wrong password should return 400."""
        django_user_model.objects.create_user(
            email="tester@example.com", password="correctpass"
        )
        resp = self.client.post(
            "/auth/login/",
            {"email": "tester@example.com", "password": "wrongpass"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_without_otp_rejected(self, django_user_model):
        """Login should fail if OTP not verified yet."""
        django_user_model.objects.create_user(
            email="tester2@example.com", password="secret123"
        )
        resp = self.client.post(
            "/auth/login/",
            {"email": "tester2@example.com", "password": "secret123"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_otp_setup_returns_uri(self, django_user_model):
        """OTP setup should generate a TOTP device for authenticated user."""
        user = django_user_model.objects.create_user(
            email="otpuser@example.com", password="mypassword"
        )
        self.client.force_authenticate(user=user)
        resp = self.client.post("/auth/otp/setup/")
        assert resp.status_code == status.HTTP_201_CREATED
        assert "otp_uri" in resp.data

    def test_otp_verify_issues_tokens(self, django_user_model):
        """After OTP verification, user should receive JWT tokens."""
        user = django_user_model.objects.create_user(
            email="otpverify@example.com", password="pass1234"
        )
        device = TOTPDevice.objects.create(user=user, name="default")

        # Generate valid OTP token
        code = totp(device.bin_key, step=device.step, t0=device.t0, digits=6, drift=0)

        self.client.force_authenticate(user=user)
        resp = self.client.post("/auth/otp/verify/", {"code": code})
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "refresh" in resp.data
