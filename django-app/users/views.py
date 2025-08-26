# views.py
import logging
from django.core import signing
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import (
    ValidationError, NotFound, Throttled, PermissionDenied
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import SignupSerializer, CustomTokenObtainPairSerializer
from .models import OTP
from .utils import (
    create_otp, send_otp_email, can_resend,
    issue_verification_token, read_verification_token,
    secure_compare_hash, _mask_email, DEFAULT_EXP_MINUTES
)

logger = logging.getLogger(__name__)
User = get_user_model()


class SignupView(generics.CreateAPIView):
    """
    Signup:
    - Creates user
    - Creates one-time OTP (hashed + expiry + attempts)
    - Enforces resend cooldown via latest active OTP timestamp
    - Emails OTP
    - Returns signed verification_token (client keeps it for verify/resend)
    """
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp_send"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        if not can_resend(user, "signup"):
            logger.info("Signup OTP blocked by cooldown for %s", _mask_email(user.email))
            raise Throttled(detail="Please wait before requesting another code.")

        try:
            otp, code = create_otp(user, purpose="signup")
            send_otp_email(user.email, code, purpose="signup", exp_minutes=DEFAULT_EXP_MINUTES)
            token = issue_verification_token(otp)

            logger.info("Signup OTP created and emailed to %s", _mask_email(user.email))
            resp = {
                "message": "Signup successful. We emailed you a verification code.",
                "verification_token": token,
            }

            from django.conf import settings
            if getattr(settings, "DEBUG", False):
                resp["__debug_only_otp"] = code

            return Response(resp, status=status.HTTP_201_CREATED)

        except Exception as exc:
            logger.error("Signup OTP flow failed for %s: %s", _mask_email(user.email), str(exc), exc_info=True)
            raise ValidationError("Could not send verification code.")


class ResendOTPView(APIView):
    """
    Resend OTP:
    - Requires verification_token (prevents email re-post + enumeration)
    - Cooldown enforced
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp_send"

    def post(self, request):
        token = request.data.get("verification_token")
        if not token:
            raise ValidationError("verification_token is required.")

        try:
            data = read_verification_token(token)
            user = User.objects.get(pk=data["uid"])
        except (signing.BadSignature, signing.SignatureExpired):
            logger.warning("Resend OTP: invalid/expired token")
            raise ValidationError("Invalid or expired verification token.")
        except User.DoesNotExist:
            logger.warning("Resend OTP: user not found")
            raise NotFound("User not found.")

        if user.is_verified:
            raise ValidationError("Account already verified. Please log in.")

        if not can_resend(user, "signup"):
            logger.info("Resend OTP blocked by cooldown for %s", _mask_email(user.email))
            raise Throttled(detail="Please wait before requesting another code.")

        try:
            otp, code = create_otp(user, purpose="signup")
            send_otp_email(user.email, code, purpose="signup", exp_minutes=DEFAULT_EXP_MINUTES)
            new_token = issue_verification_token(otp)

            logger.info("Resent OTP to %s", _mask_email(user.email))
            resp = {"message": "A new verification code has been sent.", "verification_token": new_token}

            from django.conf import settings
            if getattr(settings, "DEBUG", False):
                resp["__debug_only_otp"] = code

            return Response(resp, status=200)

        except Exception as exc:
            logger.error("Resend OTP failed for %s: %s", _mask_email(user.email), str(exc), exc_info=True)
            raise ValidationError("Could not send verification code.")


class OTPVerifyView(APIView):
    """
    Verify OTP:
    - Accepts { verification_token, otp }
    - Locks after too many attempts (per-OTP)
    - Marks user verified + returns JWT tokens on success
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp_verify"

    def post(self, request):
        token = request.data.get("verification_token")
        code = request.data.get("otp")

        if not token or not code:
            raise ValidationError("verification_token and otp are required.")

        try:
            data = read_verification_token(token)
            otp = OTP.objects.select_related("user").get(id=data["otp_id"], user_id=data["uid"], purpose="signup")
        except (signing.BadSignature, signing.SignatureExpired):
            logger.warning("OTP verify: invalid/expired token")
            raise ValidationError("Invalid or expired verification token.")
        except OTP.DoesNotExist:
            logger.warning("OTP verify: otp not found for token")
            raise ValidationError("Invalid OTP request.")

        user = otp.user

        if user.is_verified:
            logger.info("OTP verify: already verified for %s", _mask_email(user.email))
            raise ValidationError("Account already verified. Please log in.")

        if not otp.can_attempt():
            logger.warning("OTP verify blocked (expired/used/too many attempts) for %s", _mask_email(user.email))
            raise ValidationError("Code expired or too many attempts. Request a new one.")

        if not secure_compare_hash(str(code), otp.code_hash):
            otp.increment_attempts()
            logger.warning(
                "Invalid OTP attempt for %s (attempt %s/%s)",
                _mask_email(user.email), otp.attempt_count, otp.max_attempts
            )
            raise ValidationError("Invalid code.")

        # success
        otp.mark_used()
        user.is_verified = True
        user.save(update_fields=["is_verified"])

        refresh = RefreshToken.for_user(user)
        logger.info("OTP verified successfully for %s", _mask_email(user.email))

        return Response(
            {
                "message": "Verification successful.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=200,
        )


class LoginView(TokenObtainPairView):
    """
    JWT login (blocked for unverified users via CustomTokenObtainPairSerializer)
    """
    serializer_class = CustomTokenObtainPairSerializer
