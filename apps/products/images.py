"""Product-permission commands and storage cleanup for catalog images."""
import logging
from contextlib import contextmanager
from pathlib import PurePosixPath

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Product, ProductImage
from .services import _require_permission, require_catalog_view, create_seedling_product


logger = logging.getLogger(__name__)


def _require_image_edit(actor):
    require_catalog_view(actor)
    _require_permission(actor, "products.change_product")


def _delete_owned_file(storage, name, product_id, image_id):
    path = PurePosixPath(name)
    if (path.parts[:2] != ("products", str(product_id)) or len(path.parts) != 3
            or not path.name.startswith(image_id.hex) or ProductImage.objects.filter(image=name).exists()):
        return
    try:
        storage.delete(name)
    except OSError:
        logger.exception("Could not remove stored file for ProductImage %s", image_id)


@receiver(post_delete, sender=ProductImage)
def remove_deleted_image_file(sender, instance, using, **kwargs):
    if instance.image:
        storage, name = instance.image.storage, instance.image.name
        product_id, image_id = instance.product_id, instance.pk
        transaction.on_commit(lambda: _delete_owned_file(storage, name, product_id, image_id), using=using)


@contextmanager
def _image_upload_transaction(record):
    """Keep database rollback and failed-upload file cleanup at one boundary."""
    if any(not getattr(block, "_from_testcase", False) for block in connection.atomic_blocks):
        raise ValidationError("Image upload must own its transaction to clean up failed uploads safely.")
    try:
        with transaction.atomic():
            yield
    except Exception:
        if record.image and record.image._committed:
            _delete_owned_file(record.image.storage, record.image.name, record.product_id, record.pk)
        raise


def upload_product_image(*, product_id, image, alt_text, sort_order, actor):
    _require_image_edit(actor)
    record = ProductImage(product_id=product_id, image=image, alt_text=alt_text, sort_order=sort_order)
    with _image_upload_transaction(record):
        Product.objects.select_for_update().get(pk=product_id)
        record.save()
    return record


def create_product_with_first_image(*, actor, image=None, alt_text="", **product_values):
    if image is None:
        return create_seedling_product(actor=actor, **product_values)
    _require_image_edit(actor)
    record = ProductImage(image=image, alt_text=alt_text, sort_order=0)
    with _image_upload_transaction(record):
        result = create_seedling_product(actor=actor, **product_values)
        record.product = result[0]
        record.save()
    return result


@transaction.atomic
def update_product_image(*, product_id, image_id, alt_text, sort_order, actor):
    _require_image_edit(actor)
    Product.objects.select_for_update().get(pk=product_id)
    record = ProductImage.objects.select_for_update().get(pk=image_id, product_id=product_id)
    record.alt_text, record.sort_order = alt_text, sort_order
    record.save()
    return record


@transaction.atomic
def delete_product_image(*, product_id, image_id, actor):
    _require_image_edit(actor)
    Product.objects.select_for_update().get(pk=product_id)
    record = ProductImage.objects.select_for_update().get(pk=image_id, product_id=product_id)
    record.delete()
