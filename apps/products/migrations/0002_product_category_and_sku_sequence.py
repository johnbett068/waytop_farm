import re
import uuid

from django.db import migrations, models
from django.db.models import Q


RATIFIED_PRODUCT_ID = uuid.UUID("8de0cae8-7a0f-4729-b1c8-9f4fc2c2ecb2")
RATIFIED_PRODUCT_SKU = "TOMATO SEEDLING"
SKU_PATTERN = re.compile(r"^WTP-(VEG|FRT|TRE)-(\d+)$")
CATEGORIES = ("VEG", "FRT", "TRE")


def category_and_suffix_for_existing_product(product_id, sku):
    match = SKU_PATTERN.fullmatch(sku)
    if match is not None:
        category, suffix = match.groups()
        return category, int(suffix)
    if product_id == RATIFIED_PRODUCT_ID and sku == RATIFIED_PRODUCT_SKU:
        return "VEG", None
    return None


def backfill_categories_and_sequences(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductSkuSequence = apps.get_model("products", "ProductSkuSequence")

    assignments = []
    highest = {category: 0 for category in CATEGORIES}
    blockers = []
    for product in Product.objects.all().only("id", "sku"):
        resolution = category_and_suffix_for_existing_product(product.pk, product.sku)
        if resolution is not None:
            category, suffix = resolution
            assignments.append((product.pk, category))
            if suffix is not None:
                highest[category] = max(highest[category], suffix)
        else:
            blockers.append(f"{product.pk}: {product.sku}")

    if blockers:
        raise RuntimeError(
            "Product category migration blocked by unrecognized SKU format(s): "
            + ", ".join(blockers)
        )

    for product_id, category in assignments:
        Product.objects.filter(pk=product_id).update(category=category)
    for category in CATEGORIES:
        ProductSkuSequence.objects.update_or_create(
            category=category,
            defaults={"last_value": highest[category]},
        )


class Migration(migrations.Migration):
    dependencies = [("products", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="category",
            field=models.CharField(
                choices=[("VEG", "Vegetable"), ("FRT", "Fruit"), ("TRE", "Tree")],
                max_length=3,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="ProductSkuSequence",
            fields=[
                (
                    "category",
                    models.CharField(
                        choices=[("VEG", "Vegetable"), ("FRT", "Fruit"), ("TRE", "Tree")],
                        max_length=3,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("last_value", models.PositiveBigIntegerField(default=0)),
            ],
        ),
        migrations.RunPython(backfill_categories_and_sequences, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="category",
            field=models.CharField(
                choices=[("VEG", "Vegetable"), ("FRT", "Fruit"), ("TRE", "Tree")],
                max_length=3,
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.CheckConstraint(
                condition=Q(category__in=("VEG", "FRT", "TRE")),
                name="product_category_supported",
            ),
        ),
        migrations.AddConstraint(
            model_name="productskusequence",
            constraint=models.CheckConstraint(
                condition=Q(last_value__gte=0),
                name="product_sku_sequence_non_negative",
            ),
        ),
    ]
