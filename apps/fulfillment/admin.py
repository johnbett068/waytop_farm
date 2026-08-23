from django.contrib import admin

from .models import FulfillmentCompletion


@admin.register(FulfillmentCompletion)
class FulfillmentCompletionAdmin(admin.ModelAdmin):
    list_display = ("order", "completed_by", "reference", "completed_at")
    search_fields = ("order__order_number", "reference")
    readonly_fields = tuple(field.name for field in FulfillmentCompletion._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.has_perm("fulfillment.complete")
