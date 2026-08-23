import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .normalization import normalize_email, normalize_kenyan_phone


class Customer(models.Model):
    """Mutable current customer profile; future Orders must store snapshots."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("display_name", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=~Q(display_name=""),
                name="customer_display_name_not_empty",
            ),
        ]

    def clean(self):
        super().clean()
        self.display_name = self.display_name.strip()
        try:
            self.phone = normalize_kenyan_phone(self.phone)
        except ValidationError as exc:
            raise ValidationError({"phone": exc.messages}) from exc
        self.email = normalize_email(self.email)
        if not self.display_name:
            raise ValidationError({"display_name": "Enter a customer display name."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name


class CustomerAddress(models.Model):
    """Current reusable address; future Orders must copy an immutable snapshot."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="addresses")
    label = models.CharField(max_length=100, blank=True)
    county = models.CharField(max_length=100)
    town_or_area = models.CharField(max_length=160)
    address_line = models.CharField(max_length=500)
    delivery_instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_default", "label", "created_at")
        constraints = [
            models.CheckConstraint(condition=~Q(county=""), name="customer_address_county_not_empty"),
            models.CheckConstraint(condition=~Q(town_or_area=""), name="customer_address_town_not_empty"),
            models.CheckConstraint(condition=~Q(address_line=""), name="customer_address_line_not_empty"),
            models.CheckConstraint(
                condition=Q(is_default=False) | Q(is_active=True),
                name="customer_address_default_requires_active",
            ),
            models.UniqueConstraint(
                fields=("customer",),
                condition=Q(is_default=True),
                name="customer_one_default_address",
            ),
        ]

    def clean(self):
        super().clean()
        self.label = self.label.strip()
        self.county = self.county.strip()
        self.town_or_area = self.town_or_area.strip()
        self.address_line = self.address_line.strip()
        self.delivery_instructions = self.delivery_instructions.strip()
        errors = {}
        for field, message in (
            ("county", "Enter a county."),
            ("town_or_area", "Enter a town or area."),
            ("address_line", "Enter an address."),
        ):
            if not getattr(self, field):
                errors[field] = message
        if self.is_default and not self.is_active:
            errors["is_default"] = "An inactive address cannot be the default address."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        label = self.label or self.town_or_area
        return f"{self.customer.display_name} — {label}"
