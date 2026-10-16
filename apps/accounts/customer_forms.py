from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from apps.customers.models import Customer
from apps.customers.normalization import normalize_email, normalize_kenyan_phone
from apps.inventory.models import InventoryLocation


class BuyerFields(forms.Form):
    full_name = forms.CharField(label="Full name", max_length=200)
    phone = forms.CharField(label="Phone number", max_length=32, widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}))
    email = forms.EmailField(label="Email (optional)", required=False)

    def clean_phone(self):
        return normalize_kenyan_phone(self.cleaned_data["phone"])

    def clean_email(self):
        return normalize_email(self.cleaned_data.get("email"))


class CustomerRegistrationForm(UserCreationForm, BuyerFields):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "full_name", "phone", "email", "password1", "password2")


class CustomerAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff or user.is_superuser or not Customer.objects.filter(owner=user, is_active=True).exists():
            raise forms.ValidationError("Use a customer account to sign in here. Staff should use staff sign in.", code="invalid_login")


class CustomerProfileForm(BuyerFields):
    county = forms.CharField(max_length=100)
    town_or_area = forms.CharField(label="Town / Area", max_length=160)
    address_line = forms.CharField(label="Locality / landmark", max_length=500,
                                   help_text="Describe where you are based. A village, estate or nearby landmark is enough; a street address is not required.")
    preferred_picking_location = forms.ModelChoiceField(
        label="Preferred picking location", queryset=InventoryLocation.objects.none(),
        empty_label="Choose a picking location", to_field_name="code",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["preferred_picking_location"]
        field.queryset = InventoryLocation.objects.filter(is_active=True, allows_saleable_stock=True).order_by("name", "pk")
        field.label_from_instance = lambda location: location.name
        self.no_locations = not field.queryset.exists()

