from django.contrib import admin

from .models import Customer, CustomerAddress


class PreserveCustomerHistoryAdminMixin:
    def has_delete_permission(self, request, obj=None):
        return False


class CustomerAddressInline(admin.TabularInline):
    model = CustomerAddress
    extra = 0
    can_delete = False
    fields = ("label", "county", "town_or_area", "address_line", "is_active", "is_default")


@admin.register(Customer)
class CustomerAdmin(PreserveCustomerHistoryAdminMixin, admin.ModelAdmin):
    list_display = ("display_name", "phone", "email", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("display_name", "phone", "email")
    readonly_fields = ("owner", "created_at", "updated_at")
    inlines = (CustomerAddressInline,)


@admin.register(CustomerAddress)
class CustomerAddressAdmin(PreserveCustomerHistoryAdminMixin, admin.ModelAdmin):
    list_display = ("customer", "label", "county", "town_or_area", "is_active", "is_default", "updated_at")
    list_filter = ("is_active", "is_default", "county")
    search_fields = ("customer__display_name", "customer__phone", "address_line", "town_or_area", "county")
    autocomplete_fields = ("customer",)
    readonly_fields = ("created_at", "updated_at")
