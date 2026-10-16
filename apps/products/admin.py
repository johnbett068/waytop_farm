from django.contrib import admin

from .models import Product, ProductPrice, ProductSaleUnit


class PreserveCatalogHistoryAdminMixin:
    def has_delete_permission(self, request, obj=None):
        return False


class ProductSaleUnitInline(admin.TabularInline):
    model = ProductSaleUnit
    extra = 0
    can_delete = False
    fields = ("name", "base_quantity", "is_active")


@admin.register(Product)
class ProductAdmin(PreserveCatalogHistoryAdminMixin, admin.ModelAdmin):
    list_display = ("sku", "name", "category", "base_inventory_unit", "is_active", "is_published", "updated_at")
    list_filter = ("category", "is_active", "is_published")
    search_fields = ("sku", "name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = (ProductSaleUnitInline,)


@admin.register(ProductSaleUnit)
class ProductSaleUnitAdmin(PreserveCatalogHistoryAdminMixin, admin.ModelAdmin):
    list_display = ("name", "product", "base_quantity", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "product__name", "product__sku")
    autocomplete_fields = ("product",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProductPrice)
class ProductPriceAdmin(PreserveCatalogHistoryAdminMixin, admin.ModelAdmin):
    list_display = ("sale_unit", "amount", "currency", "effective_start", "effective_end", "is_active")
    list_filter = ("currency", "is_active")
    search_fields = ("sale_unit__name", "sale_unit__product__name", "sale_unit__product__sku")
    autocomplete_fields = ("sale_unit",)
    readonly_fields = ("created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields.extend(("sale_unit", "amount", "currency", "effective_start"))
            if obj.effective_end is not None:
                fields.append("effective_end")
        return fields
