from django.contrib import admin

from .models import Payment, PaymentEvidence, PaymentStatusEvent, PaymentVerificationAttempt


class ReadOnlyPaymentAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.has_perm("payments.verify")


@admin.register(Payment)
class PaymentAdmin(ReadOnlyPaymentAdminMixin, admin.ModelAdmin):
    list_display = ("order", "amount", "currency", "method", "state", "created_at")
    list_filter = ("method", "state")
    search_fields = ("order__order_number", "provider_reference")
    readonly_fields = tuple(field.name for field in Payment._meta.fields)


@admin.register(PaymentEvidence)
class PaymentEvidenceAdmin(ReadOnlyPaymentAdminMixin, admin.ModelAdmin):
    list_display = ("payment", "reference_claim", "message_present", "submission_source", "submitted_at")
    list_filter = ("submission_source",)
    search_fields = ("payment__order__order_number", "reference_claim")
    fields = ("id", "payment", "reference_claim", "message_present", "submission_source", "submitted_at")
    readonly_fields = fields

    @admin.display(boolean=True, description="Raw message stored securely")
    def message_present(self, obj):
        return obj.has_message


@admin.register(PaymentVerificationAttempt)
class PaymentVerificationAttemptAdmin(ReadOnlyPaymentAdminMixin, admin.ModelAdmin):
    list_display = ("payment", "outcome", "actor", "created_at")
    list_filter = ("outcome",)
    search_fields = ("payment__order__order_number",)
    readonly_fields = tuple(field.name for field in PaymentVerificationAttempt._meta.fields)


@admin.register(PaymentStatusEvent)
class PaymentStatusEventAdmin(ReadOnlyPaymentAdminMixin, admin.ModelAdmin):
    list_display = ("payment", "previous_state", "new_state", "actor", "created_at")
    list_filter = ("new_state",)
    search_fields = ("payment__order__order_number",)
    readonly_fields = tuple(field.name for field in PaymentStatusEvent._meta.fields)
