from django.contrib import admin

from .models import Commitment, CommitmentEvent, CommitmentSupplyEvent


class ReadOnlyCommitmentAdmin(admin.ModelAdmin):
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


@admin.register(Commitment)
class CommitmentAdmin(ReadOnlyCommitmentAdmin):
    list_display = (
        "id",
        "order",
        "order_line",
        "state",
        "committed_quantity",
        "outstanding_quantity",
        "confirmed_at",
        "fifo_sequence",
    )
    list_filter = ("state", "order_line__supply_mode")
    search_fields = ("id", "order__order_number", "order_line__product_sku")


@admin.register(CommitmentEvent)
class CommitmentEventAdmin(ReadOnlyCommitmentAdmin):
    list_display = (
        "id",
        "commitment",
        "previous_state",
        "new_state",
        "commercial_quantity",
        "actor",
        "created_at",
    )
    search_fields = (
        "id",
        "commitment__id",
        "commitment__order__order_number",
        "source_reference",
    )


@admin.register(CommitmentSupplyEvent)
class CommitmentSupplyEventAdmin(ReadOnlyCommitmentAdmin):
    list_display = (
        "id",
        "commitment",
        "commercial_quantity",
        "base_quantity",
        "inventory_movement",
        "actor",
        "created_at",
    )
    search_fields = (
        "id",
        "commitment__id",
        "commitment__order__order_number",
        "inventory_movement__id",
        "source_reference",
    )
