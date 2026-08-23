from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class WayTopUserAdmin(UserAdmin):
    readonly_fields = ("created_at", "updated_at")
    fieldsets = UserAdmin.fieldsets + (
        ("Record metadata", {"fields": ("created_at", "updated_at")}),
    )
