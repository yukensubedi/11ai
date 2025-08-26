from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, SubscriptionPlan, Subscription


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ("id", "email", "plan", "is_verified", "is_staff", "is_superuser")
    list_filter = ("is_staff", "is_superuser")
    search_fields = ("email",)
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email_verified")}),
        ("Subscriptions", {"fields": ()}),  # plan is derived
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "is_staff", "is_superuser")}),
    )


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "plan", "is_active", "start_date", "end_date")
    list_filter = ("is_active", "plan")
    search_fields = ("user__email",)
