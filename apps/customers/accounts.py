"""Customer-owned account operations; no order or payment side effects."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.inventory.models import InventoryLocation
from .models import Customer, CustomerAddress
from .normalization import normalize_kenyan_phone


def owned_customer(user, *, lock=False):
    if not user.is_authenticated or not user.is_active or user.is_staff or user.is_superuser:
        raise PermissionDenied("A customer account is required.")
    query = Customer.objects.select_for_update() if lock else Customer.objects
    try:
        return query.get(owner=user, is_active=True)
    except Customer.DoesNotExist as error:
        raise PermissionDenied("No active customer profile is associated with this account. Contact our team.") from error


@transaction.atomic
def register_customer(form):
    if not form.is_valid():
        raise ValidationError("Please correct the registration details.")
    user = form.save(commit=False)
    user.is_staff = False
    user.is_superuser = False
    user.save()
    Customer.objects.create(owner=user, display_name=form.cleaned_data["full_name"],
                            phone=form.cleaned_data["phone"], email=form.cleaned_data["email"])
    return user


def profile_address(customer):
    return customer.addresses.filter(is_active=True, is_default=True).first()


def missing_profile_fields(user):
    customer = owned_customer(user)
    missing = []
    if not customer.display_name.strip():
        missing.append("Full name")
    try:
        if not normalize_kenyan_phone(customer.phone):
            missing.append("Phone number")
    except ValidationError:
        missing.append("Phone number")
    address = profile_address(customer)
    if not address or not all(getattr(address, key).strip() for key in ("county", "town_or_area", "address_line")):
        missing.append("Your location")
    if not InventoryLocation.objects.filter(pk=customer.preferred_picking_location_id,
                                            is_active=True, allows_saleable_stock=True).exists():
        missing.append("Preferred picking location")
    return missing


@transaction.atomic
def save_customer_profile(*, user, data):
    # Serialize edits of this customer's contact and default location together.
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    customer = owned_customer(user, lock=True)
    location = InventoryLocation.objects.select_for_update().filter(
        pk=data["preferred_picking_location"].pk, is_active=True, allows_saleable_stock=True,
    ).first()
    if location is None:
        raise ValidationError({"preferred_picking_location": "This picking location is no longer available. Please choose another."})
    phone = normalize_kenyan_phone(data["phone"])
    if not phone:
        raise ValidationError({"phone": "Enter a valid Kenyan phone number."})
    customer.display_name = data["full_name"]
    customer.phone = phone
    customer.email = data["email"]
    customer.preferred_picking_location = location
    customer.save()
    address = profile_address(customer) or CustomerAddress(customer=customer, is_default=True)
    for key in ("county", "town_or_area", "address_line"):
        setattr(address, key, data[key])
    address.save()
    return customer

