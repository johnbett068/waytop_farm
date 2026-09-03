from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.shortcuts import redirect, render

from .forms import StaffProductCreateForm
from .models import Product, ProductPrice, ProductSaleUnit
from .services import create_seedling_product, require_catalog_create, require_catalog_view


@login_required(login_url="accounts:login")
def product_list(request):
    require_catalog_view(request.user)
    units = ProductSaleUnit.objects.prefetch_related(
        Prefetch("prices", queryset=ProductPrice.objects.filter(is_active=True))
    )
    products = Product.objects.prefetch_related(Prefetch("sale_units", queryset=units))
    return render(request, "dashboard/products/list.html", {"products": products})


def _add_service_errors(form, error):
    if hasattr(error, "message_dict"):
        for field, errors in error.message_dict.items():
            target = field if field in form.fields else None
            for message in errors:
                form.add_error(target, message)
    else:
        form.add_error(None, error)


@login_required(login_url="accounts:login")
def product_create(request):
    require_catalog_create(request.user)
    form = StaffProductCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            product, _sale_unit, _price = create_seedling_product(
                actor=request.user, **form.cleaned_data
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            messages.success(request, f"Product {product.name} created.")
            return redirect("dashboard:catalog_products")
    return render(request, "dashboard/products/form.html", {"form": form})

