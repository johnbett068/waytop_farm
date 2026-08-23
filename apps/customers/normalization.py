import phonenumbers
from django.core.exceptions import ValidationError


def normalize_kenyan_phone(value):
    """Return an optional Kenyan phone number in canonical E.164 form."""
    value = (value or "").strip()
    if not value:
        return ""

    try:
        number = phonenumbers.parse(value, "KE")
    except phonenumbers.NumberParseException as exc:
        raise ValidationError("Enter a valid Kenyan phone number.") from exc

    if (
        number.country_code != 254
        or not phonenumbers.is_possible_number(number)
        or not phonenumbers.is_valid_number(number)
    ):
        raise ValidationError("Enter a valid Kenyan phone number.")

    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def normalize_email(value):
    return (value or "").strip().lower()
