from django.contrib import admin

from .models import (
    GoodsReceiptLine, PurchaseOrderEvent, Supplier, SupplierEvent,
    SupplierGoodsReceipt, SupplierPurchaseOrder, SupplierPurchaseOrderLine,
)


class ReadOnlyProcurementAdmin(admin.ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("procurement.view")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


for model in (
    Supplier, SupplierEvent, SupplierPurchaseOrder, SupplierPurchaseOrderLine,
    PurchaseOrderEvent, SupplierGoodsReceipt, GoodsReceiptLine,
):
    admin.site.register(model, ReadOnlyProcurementAdmin)
