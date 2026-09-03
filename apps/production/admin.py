from django.contrib import admin

from .models import (
    NurseryActivity,
    ProductionBatch,
    ProductionBatchEvent,
    ProductionLabour,
    ProductionPurchase,
)


class ReadOnlyProductionAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.has_perm("production.view_operations")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("production.view_operations")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductionBatch)
class ProductionBatchAdmin(ReadOnlyProductionAdmin):
    list_display = ("batch_number", "product", "status", "current_quantity", "expected_ready_date")
    list_filter = ("status",)
    search_fields = ("batch_number", "product__sku", "product__name")


@admin.register(ProductionBatchEvent)
class ProductionBatchEventAdmin(ReadOnlyProductionAdmin):
    list_display = ("batch", "operation", "actor", "created_at")
    list_filter = ("operation",)
    search_fields = ("batch__batch_number", "correlation_id", "idempotency_key")


@admin.register(ProductionPurchase)
class ProductionPurchaseAdmin(ReadOnlyProductionAdmin):
    list_display = ("purchase_date", "item_description", "supplier", "total_cost", "batch")
    list_filter = ("category",)
    search_fields = ("item_description", "supplier", "reference", "batch__batch_number")


@admin.register(ProductionLabour)
class ProductionLabourAdmin(ReadOnlyProductionAdmin):
    list_display = ("work_date", "worker", "activity", "total_cost", "batch")
    list_filter = ("effort_unit",)
    search_fields = ("worker", "activity", "batch__batch_number")


@admin.register(NurseryActivity)
class NurseryActivityAdmin(ReadOnlyProductionAdmin):
    list_display = ("activity_date", "activity_type", "person_or_team", "batch")
    list_filter = ("activity_type",)
    search_fields = ("description", "person_or_team", "batch__batch_number")

