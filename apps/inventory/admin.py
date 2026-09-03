from django.contrib import admin

from .models import (
    InventoryItem,
    InventorySupply,
    InventorySupplyEvent,
    InventoryAdjustmentRequest,
    InventoryLocation,
    InventoryMovement,
    InventoryMovementLine,
    Reservation,
    ReservationEvent,
    SourceAllocation,
    SourceAllocationConsumption,
    SourceAllocationOperation,
    StockLot,
    StockPosition,
)


class ReadOnlyInventoryAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.has_perm("inventory.view")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("inventory.view")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InventoryItem)
class InventoryItemAdmin(ReadOnlyInventoryAdmin):
    list_display = ("product", "base_unit", "is_active", "updated_at")
    search_fields = ("product__sku", "product__name", "base_unit")
    list_filter = ("is_active",)


@admin.register(InventorySupply)
class InventorySupplyAdmin(ReadOnlyInventoryAdmin):
    list_display = ("code", "name", "category", "base_unit", "is_active")


@admin.register(InventorySupplyEvent)
class InventorySupplyEventAdmin(ReadOnlyInventoryAdmin):
    list_display = ("supply", "actor", "created_at")


@admin.register(InventoryAdjustmentRequest)
class InventoryAdjustmentRequestAdmin(ReadOnlyInventoryAdmin):
    list_display = ("item", "direction", "base_quantity", "state", "requester", "approver")


@admin.register(InventoryLocation)
class InventoryLocationAdmin(ReadOnlyInventoryAdmin):
    list_display = ("code", "name", "is_active", "allows_saleable_stock", "updated_at")
    search_fields = ("code", "name")
    list_filter = ("is_active", "allows_saleable_stock")


@admin.register(StockLot)
class StockLotAdmin(ReadOnlyInventoryAdmin):
    list_display = ("lot_code", "item", "condition", "expiry_date", "is_active")
    search_fields = ("lot_code", "item__product__sku", "provenance_reference")
    list_filter = ("condition", "is_active")


@admin.register(StockPosition)
class StockPositionAdmin(ReadOnlyInventoryAdmin):
    list_display = ("item", "location", "lot", "on_hand_base_quantity", "version", "updated_at")
    search_fields = ("item__product__sku", "location__code", "lot__lot_code")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(ReadOnlyInventoryAdmin):
    list_display = ("id", "movement_type", "actor", "effective_at", "posted_at")
    search_fields = ("id", "source_type", "source_reference", "correlation_id")
    list_filter = ("movement_type",)


@admin.register(InventoryMovementLine)
class InventoryMovementLineAdmin(ReadOnlyInventoryAdmin):
    list_display = (
        "movement", "line_number", "item", "lot", "quantity",
        "source_location", "destination_location",
    )
    search_fields = ("movement__id", "item__product__sku", "lot__lot_code")


class ReadOnlyCommitmentSupplyAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return request.user.has_perm("commitments.view")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("commitments.view")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reservation)
class ReservationAdmin(ReadOnlyCommitmentSupplyAdmin):
    list_display = (
        "id",
        "commitment",
        "inventory_item",
        "state",
        "initial_base_quantity",
        "remaining_base_quantity",
        "created_at",
    )
    list_filter = ("state",)
    search_fields = ("id", "commitment__id", "commitment__order__order_number")


@admin.register(ReservationEvent)
class ReservationEventAdmin(ReadOnlyCommitmentSupplyAdmin):
    list_display = (
        "id",
        "reservation",
        "action",
        "base_quantity",
        "actor",
        "created_at",
    )
    list_filter = ("action",)
    search_fields = ("id", "reservation__id", "source_reference")


@admin.register(SourceAllocationOperation)
class SourceAllocationOperationAdmin(ReadOnlyCommitmentSupplyAdmin):
    list_display = (
        "id",
        "reservation",
        "kind",
        "actor",
        "created_at",
    )
    list_filter = ("kind",)
    search_fields = ("id", "reservation__id", "source_reference")


@admin.register(SourceAllocation)
class SourceAllocationAdmin(ReadOnlyCommitmentSupplyAdmin):
    list_display = (
        "id",
        "reservation",
        "stock_position",
        "initial_base_quantity",
        "remaining_base_quantity",
        "created_at",
    )
    search_fields = (
        "id",
        "reservation__id",
        "stock_position__item__product__sku",
        "stock_position__location__code",
        "stock_position__lot__lot_code",
    )


@admin.register(SourceAllocationConsumption)
class SourceAllocationConsumptionAdmin(ReadOnlyCommitmentSupplyAdmin):
    list_display = (
        "id",
        "supply_event",
        "allocation",
        "base_quantity",
        "created_at",
    )
    search_fields = (
        "id",
        "supply_event__id",
        "allocation__id",
        "allocation__stock_position__location__code",
        "allocation__stock_position__lot__lot_code",
    )
