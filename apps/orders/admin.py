from django.contrib import admin

from .models import (
    Order,
    OrderAddressSnapshot,
    OrderContactSnapshot,
    OrderLine,
    OrderStatusEvent,
)


class ReadOnlyOrderAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.has_perm("orders.view")


@admin.register(Order)
class OrderAdmin(ReadOnlyOrderAdminMixin, admin.ModelAdmin):
    list_display = (
        "order_number", "channel", "fulfillment_method", "status", "total_amount", "created_at"
    )
    list_filter = ("channel", "fulfillment_method", "status")
    search_fields = ("order_number", "contact_snapshot__name", "contact_snapshot__phone")
    readonly_fields = tuple(field.name for field in Order._meta.fields)


@admin.register(OrderLine)
class OrderLineAdmin(ReadOnlyOrderAdminMixin, admin.ModelAdmin):
    list_display = (
        "order", "line_number", "product_name", "quantity", "supply_mode", "line_total"
    )
    list_filter = ("supply_mode",)
    search_fields = ("order__order_number", "product_sku", "product_name")
    readonly_fields = tuple(field.name for field in OrderLine._meta.fields)


@admin.register(OrderContactSnapshot)
class OrderContactSnapshotAdmin(ReadOnlyOrderAdminMixin, admin.ModelAdmin):
    list_display = ("order", "name", "phone", "email")
    search_fields = ("order__order_number", "name", "phone", "email")
    readonly_fields = tuple(field.name for field in OrderContactSnapshot._meta.fields)


@admin.register(OrderAddressSnapshot)
class OrderAddressSnapshotAdmin(ReadOnlyOrderAdminMixin, admin.ModelAdmin):
    list_display = ("order", "county", "town_or_area")
    search_fields = ("order__order_number", "county", "town_or_area", "address_line")
    readonly_fields = tuple(field.name for field in OrderAddressSnapshot._meta.fields)


@admin.register(OrderStatusEvent)
class OrderStatusEventAdmin(ReadOnlyOrderAdminMixin, admin.ModelAdmin):
    list_display = ("order", "previous_status", "new_status", "actor", "created_at")
    list_filter = ("new_status",)
    search_fields = ("order__order_number",)
    readonly_fields = tuple(field.name for field in OrderStatusEvent._meta.fields)
