import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ImmutableFulfillmentQuerySet(models.QuerySet):
    def _reject_write(self):
        raise ValidationError("Fulfillment completion history is immutable.")

    def update(self, **kwargs):
        self._reject_write()

    def delete(self):
        self._reject_write()

    def bulk_create(self, objs, **kwargs):
        self._reject_write()

    def bulk_update(self, objs, fields, **kwargs):
        self._reject_write()


class FulfillmentCompletion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="fulfillment_completion",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fulfillment_completions",
    )
    note = models.TextField(blank=True)
    reference = models.CharField(max_length=160, blank=True)
    correlation_id = models.UUIDField(editable=False)
    idempotency_key = models.UUIDField(editable=False, unique=True)
    request_fingerprint = models.CharField(max_length=64, editable=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableFulfillmentQuerySet.as_manager()

    class Meta:
        ordering = ("-completed_at", "id")
        default_permissions = ()
        permissions = (("complete", "Can complete fulfillment"),)

    def clean(self):
        super().clean()
        self.note = (self.note or "").strip()
        self.reference = (self.reference or "").strip()
        errors = {}
        if self.order_id and self.order.status != "PROCESSING":
            errors["order"] = "Fulfillment completion requires a PROCESSING Order."
        if not self.request_fingerprint:
            errors["request_fingerprint"] = "Fulfillment completion requires a request fingerprint."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        service_write = kwargs.pop("_fulfillment_service_write", False)
        if not service_write or not self._state.adding:
            raise ValidationError("Fulfillment completions are immutable service records.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Fulfillment completions cannot be deleted.")

    def __str__(self):
        return f"Fulfillment completion for {self.order.order_number}"
