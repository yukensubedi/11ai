from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import SignupView, OTPVerifyView, LoginView

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("verify-otp/", OTPVerifyView.as_view(), name="verify-otp"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
]
