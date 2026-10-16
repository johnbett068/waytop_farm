from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from .forms import StaffProductCreateForm, StaffProductEditForm, StaffSaleUnitEditForm, StaffPriceForm, ProductImageUploadForm, ProductImageMetadataForm, ProductFirstImageForm
from .models import Product, ProductPrice, ProductSaleUnit, ProductImage
from .images import upload_product_image, update_product_image, delete_product_image, _require_image_edit, create_product_with_first_image
from .services import require_catalog_create, require_catalog_view, edit_product, edit_sale_unit, add_product_price, _require_permission
from .readiness import product_readiness


@login_required(login_url="accounts:login")
def product_list(request):
    require_catalog_view(request.user)
    units = ProductSaleUnit.objects.prefetch_related(
        Prefetch("prices", queryset=ProductPrice.objects.all())
    )
    products = Product.objects.prefetch_related(Prefetch("sale_units", queryset=units))
    for product in products:
        product.readiness = product_readiness(product)
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
    form = StaffProductCreateForm(request.POST if request.method == "POST" else None)
    image_form = ProductFirstImageForm(request.POST if request.method == "POST" else None,
                                       request.FILES if request.method == "POST" else None, prefix="first-image")
    if request.method == "POST" and all((form.is_valid(), image_form.is_valid())):
        try:
            product, _sale_unit, _price = create_product_with_first_image(
                actor=request.user, **form.cleaned_data, **image_form.cleaned_data
            )
        except ValidationError as error:
            _add_service_errors(form, error)
        except OSError:
            image_form.add_error("image", "The image could not be stored. The Product was not created. Please select the image and try again.")
        else:
            messages.success(request, f"Product {product.name} created.")
            return redirect("dashboard:catalog_product_detail", product.pk)
    return render(request, "dashboard/products/form.html", {"form": form, "image_form": image_form})


@login_required(login_url="accounts:login")
def product_edit(request, product_id):
    require_catalog_view(request.user)
    _require_permission(request.user, "products.change_product")
    product = get_object_or_404(Product, pk=product_id)
    action = request.POST.get("action", "save_product") if request.method == "POST" else None
    form = StaffProductEditForm(request.POST if action == "save_product" else None, instance=product)
    image_context, response = _product_images(request, product, action, "dashboard:catalog_product_edit")
    if response is not None:
        return response
    unit_rows = []
    for unit in product.sale_units.all():
        bound = action == "save_sale_unit" and request.POST.get("sale_unit_id") == str(unit.pk)
        unit_form = StaffSaleUnitEditForm(request.POST if bound else None, instance=unit, prefix=f"unit-{unit.pk}")
        unit_rows.append({"unit": unit, "form": unit_form})
    if action == "save_sale_unit":
        _require_permission(request.user, "products.change_productsaleunit")
        unit = get_object_or_404(ProductSaleUnit, pk=request.POST.get("sale_unit_id"), product=product)
        unit_form = next(row["form"] for row in unit_rows if row["unit"].pk == unit.pk)
        if unit_form.is_valid():
            try:
                edit_sale_unit(product_id=product.pk, sale_unit_id=unit.pk, actor=request.user, **unit_form.cleaned_data)
            except ValidationError as error:
                _add_service_errors(unit_form, error)
            else:
                messages.success(request, "Sale unit saved.")
                return redirect("dashboard:catalog_product_edit", product.pk)
    if action == "save_product" and form.is_valid():
        try:
            edit_product(product_id=product.pk, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _add_service_errors(form, error)
        else:
            messages.success(request, "Product configuration saved.")
            return redirect("dashboard:catalog_product_edit", product.pk)
    return render(request, "dashboard/products/edit.html", {
        "product": product, "form": form, "unit_rows": unit_rows, **image_context,
    })


def _product_images(request, product, action, return_route):
    upload_form = ProductImageUploadForm(request.POST if action == "upload_image" else None,
                                         request.FILES if action == "upload_image" else None, prefix="upload")
    records = list(product.images.all())
    image_rows = []
    for record in records:
        bound = action == "update_image" and request.POST.get("image_id") == str(record.pk)
        metadata = ProductImageMetadataForm(request.POST if bound else None, prefix=f"image-{record.pk}",
                                             initial={"alt_text": record.alt_text, "sort_order": record.sort_order})
        image_rows.append({"record": record, "url": record.display_url, "form": metadata})
    context = {"image_rows": image_rows, "upload_form": upload_form, "image_error": ""}
    if action not in (None, "price", "save_product", "save_sale_unit"):
        _require_image_edit(request.user)
        try:
            if action == "upload_image":
                if upload_form.is_valid():
                    upload_product_image(product_id=product.pk, actor=request.user, **upload_form.cleaned_data)
                    messages.success(request, "Product image uploaded.")
                    return context, redirect(return_route, product.pk)
            elif action in ("update_image", "delete_image"):
                record = get_object_or_404(ProductImage, pk=request.POST.get("image_id"), product=product)
                if action == "delete_image":
                    delete_product_image(product_id=product.pk, image_id=record.pk, actor=request.user)
                else:
                    metadata = next(row["form"] for row in image_rows if row["record"].pk == record.pk)
                    if not metadata.is_valid():
                        raise ValidationError("Review the image details below.")
                    update_product_image(product_id=product.pk, image_id=record.pk, actor=request.user, **metadata.cleaned_data)
                messages.success(request, "Product images updated.")
                return context, redirect(return_route, product.pk)
            else:
                raise ValidationError("Unknown Product image action.")
        except ValidationError as error:
            context["image_error"] = "; ".join(error.messages)

        except OSError:
            context["image_error"] = "The image could not be stored. Please select it and try again."
    return context, None


@login_required(login_url="accounts:login")
def product_detail(request, product_id):
    require_catalog_view(request.user)
    product = get_object_or_404(Product, pk=product_id)
    action = request.POST.get("action", "price") if request.method == "POST" else None
    form = StaffPriceForm(request.POST if action == "price" else None, product=product)
    image_context, response = _product_images(request, product, action, "dashboard:catalog_product_detail")
    if response is not None:
        return response
    if request.method == "POST":
        if action == "price":
            _require_permission(request.user, "products.add_productprice")
            if form.is_valid():
                try:
                    values = dict(form.cleaned_data)
                    unit = values.pop("sale_unit_id")
                    add_product_price(sale_unit_id=unit.pk, actor=request.user, **values)
                except ValidationError as error:
                    _add_service_errors(form, error)
                else:
                    messages.success(request, "Price added. Existing price history was preserved.")
                    return redirect("dashboard:catalog_product_detail", product.pk)
    return render(request, "dashboard/products/detail.html", {
        "product": product, "readiness": product_readiness(product), "form": form,
        "prices": ProductPrice.objects.filter(sale_unit__product=product).select_related("sale_unit"),
        **image_context,
    })
