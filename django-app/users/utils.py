# utils/otp.py
import logging, hmac
from typing import Tuple, Optional
from django.conf import settings
from django.core import mail, signing
from django.utils import timezone
from datetime import timedelta

from .models import OTP

logger = logging.getLogger(__name__)

SIGNER_SALT = "email-otp-verify"
VERIFICATION_TOKEN_MAX_AGE_SECONDS = 30 * 60  # 30 minutes
DEFAULT_EXP_MINUTES = 5
RESEND_COOLDOWN_SECONDS = 60


def _mask_email(email: str) -> str:
    try:
        name, domain = email.split("@")
        left = name[0] + "***" + (name[-1] if len(name) > 1 else "")
        dom_left, dom_right = domain.split(".", 1)
        return f"{left}@{dom_left[0]}***.{dom_right}"
    except Exception:
        return "***"


def latest_active_otp(user, purpose: str = "signup") -> Optional[OTP]:
    return (
        OTP.objects.filter(user=user, purpose=purpose, is_used=False, expires_at__gt=timezone.now())
        .order_by("-created_at")
        .first()
    )


def can_resend(user, purpose: str = "signup", cooldown_seconds: int = RESEND_COOLDOWN_SECONDS) -> bool:
    last = latest_active_otp(user, purpose)
    if not last:
        return True
    delta = (timezone.now() - last.created_at).total_seconds()
    return delta >= cooldown_seconds


def invalidate_active_otps(user, purpose: str = "signup") -> None:
    OTP.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)


def create_otp(user, purpose: str = "signup", exp_minutes: int = DEFAULT_EXP_MINUTES, max_attempts: int = 5) -> Tuple[OTP, str]:
    """
    Create a fresh OTP after invalidating old active ones.
    """
    invalidate_active_otps(user, purpose)
    code = OTP.generate_code()
    otp = OTP.objects.create(
        user=user,
        purpose=purpose,
        code_hash=OTP.hash_code(code),
        expires_at=timezone.now() + timedelta(minutes=exp_minutes),
        max_attempts=max_attempts,
    )
    return otp, code


def send_otp_email(to_email: str, code: str, purpose: str = "signup", exp_minutes: int = DEFAULT_EXP_MINUTES) -> None:
    # subject = "Your verification code"
    # body = f"Your {purpose} code is: {code}\nIt expires in {exp_minutes} minutes."
    # # Configure EMAIL_BACKEND/DEFAULT_FROM_EMAIL in settings.py
    # mail.send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
    print(f"Simulated email to {to_email}: Your {purpose} code is {code} (expires in {exp_minutes} minutes)")


def issue_verification_token(otp: OTP) -> str:
    payload = {"otp_id": otp.id, "uid": otp.user_id, "purpose": otp.purpose}
    return signing.dumps(payload, salt=SIGNER_SALT)


def read_verification_token(token: str) -> dict:
    return signing.loads(token, salt=SIGNER_SALT, max_age=VERIFICATION_TOKEN_MAX_AGE_SECONDS)


def secure_compare_hash(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(OTP.hash_code(code), code_hash)
