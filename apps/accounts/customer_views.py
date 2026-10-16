from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from apps.customers.accounts import owned_customer, profile_address, missing_profile_fields, register_customer, save_customer_profile
from .customer_forms import CustomerRegistrationForm, CustomerAuthenticationForm, CustomerProfileForm


class CustomerLoginView(LoginView):
    template_name = "accounts/customer_login.html"
    authentication_form = CustomerAuthenticationForm

    def get_success_url(self):
        return reverse_lazy("accounts:customer_profile")


class CustomerLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:customer_login")


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard:dashboard" if request.user.is_staff else "accounts:customer_profile")
    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = register_customer(form)
        except IntegrityError:
            form.add_error(None, "This account could not be created. Please check your username and try again.")
        else:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("accounts:customer_profile")
    return render(request, "accounts/customer_register.html", {"form": form})


@login_required(login_url="accounts:customer_login")
@require_http_methods(["GET", "POST"])
def profile(request):
    customer = owned_customer(request.user)
    address = profile_address(customer)
    initial = {"full_name": customer.display_name, "phone": customer.phone, "email": customer.email,
               "preferred_picking_location": customer.preferred_picking_location.code if customer.preferred_picking_location_id else ""}
    if address:
        initial.update({key: getattr(address, key) for key in ("county", "town_or_area", "address_line")})
    form = CustomerProfileForm(request.POST if request.method == "POST" else None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            save_customer_profile(user=request.user, data=form.cleaned_data)
        except ValidationError as error:
            if hasattr(error, "message_dict"):
                for key, errors in error.message_dict.items():
                    form.add_error(key if key in form.fields else None, errors)
            else:
                form.add_error(None, error)
        else:
            messages.success(request, "Your account details have been saved.")
            return redirect("accounts:customer_profile")
    return render(request, "accounts/customer_profile.html", {
        "form": form, "missing_fields": missing_profile_fields(request.user),
    })
