from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


import hashlib, secrets, string

# custom user manager
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must provide an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)  # superusers should always be verified

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)




# Subscription Plan (static config, e.g. Free/Pro/Premium)
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, help_text="Machine-readable key for the plan", blank=True, null=True)
    price = models.DecimalField(
            max_digits=10,
            decimal_places=2,
            default=0.0,
            validators=[MinValueValidator(0)]
        )
    # example: {"max_messages": 100, "analytics": true, "max_spaces": 10}
    features = models.JSONField(default=dict)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


    
# Custom User
class User(AbstractUser, PermissionsMixin):
    username = models.CharField(max_length=150, blank=True)  # keep for admin compatibility
    email = models.EmailField(unique=True, db_index=True)


    # New fields for OTP flow
    is_verified = models.BooleanField(default=False)  
  
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []   

    objects = UserManager()

    def __str__(self):
        return self.email

   
    # Subscription helpers
    @property
    def active_subscription(self):
        """Return the user's current active subscription, or None."""
        return self.subscriptions.filter(is_active=True).order_by("-start_date").first()

    @property
    def plan(self):
        """Shortcut to the user's current plan."""
        sub = self.active_subscription
        return sub.plan if sub else None

    def has_feature(self, feature: str) -> bool:
        """Check if current plan includes a feature flag."""
        plan = self.plan
        if not plan:
            return False
        return plan.features.get(feature, False)

    def feature_limit(self, feature: str) -> int | None:
        """Get numeric limits for a feature (like max_messages)."""
        plan = self.plan
        if not plan:
            return None
        return plan.features.get(feature)

# OTP Model
class OTP(models.Model):
    PURPOSE_CHOICES = [
        ("signup", "Signup Verification"),
        ("password_reset", "Password Reset"),
        ("login", "Login Verification"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    purpose = models.CharField(max_length=32, choices=PURPOSE_CHOICES, default="signup")
    code_hash = models.CharField(max_length=64)   # sha256(code)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    is_used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["user", "purpose", "expires_at"]),
        ]

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def can_attempt(self) -> bool:
        return (not self.is_used) and (not self.is_expired()) and (self.attempt_count < self.max_attempts)

    def increment_attempts(self) -> None:
        self.attempt_count += 1
        self.save(update_fields=["attempt_count"])

    def mark_used(self) -> None:
        self.is_used = True
        self.save(update_fields=["is_used"])

    @staticmethod
    def generate_code(length: int = 6) -> str:
        return "".join(secrets.choice(string.digits) for _ in range(length))

    @staticmethod
    def hash_code(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()
    

class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} → {self.plan.name}"

    def cancel(self):
        """Cancel this subscription (end immediately)."""
        self.is_active = False
        self.end_date = timezone.now()
        self.save(update_fields=["is_active", "end_date"])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "plan"], condition=models.Q(is_active=True), name="unique_active_subscription")
        ]
