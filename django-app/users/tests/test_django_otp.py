import pytest
import pyotp
import base64
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django_otp.plugins.otp_totp.models import TOTPDevice

User = get_user_model()

@pytest.mark.django_db
def test_otp_setup_and_verify():
    user = User.objects.create_user(email="otpuser@example.com", password="testpass")
    client = APIClient()
    client.force_authenticate(user=user)

    # Setup OTP
    response = client.post("/auth/otp/setup/")
    assert response.status_code == 201
    assert "otp_uri" in response.data

    device = TOTPDevice.objects.get(user=user)

    # ✅ Convert bin_key → base32 secret for pyotp
    base32_secret = base64.b32encode(device.bin_key).decode("utf-8")

    # Generate a valid TOTP
    totp = pyotp.TOTP(base32_secret, digits=6, interval=device.step)
    token = totp.now()

    # Verify OTP
    response = client.post("/auth/otp/verify/", {"code": token})
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data
