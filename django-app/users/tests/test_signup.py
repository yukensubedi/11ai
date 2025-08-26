import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_user_can_signup_with_free_plan():
    client = APIClient()
    response = client.post("/auth/signup/", {
        "email": "newuser@example.com",
        "password": "testpass123",
        "first_name": "John",
        "last_name": "Doe"
    }, format="json")

    assert response.status_code == 201
    assert response.data["otp_required"] is True


def test_signup_requires_password():
    client = APIClient()
    response = client.post("/auth/signup/", {
        "email": "fail@example.com"
    }, format="json")

    assert response.status_code == 400
    assert "password" in response.data["errors"]


def test_signup_returns_message_only():
    client = APIClient()
    response = client.post("/auth/signup/", {
        "email": "autologin@example.com",
        "password": "testpass123"
    }, format="json")

    assert response.status_code == 201
    assert response.data["message"].startswith("Signup successful")
    assert response.data["otp_required"] is True
