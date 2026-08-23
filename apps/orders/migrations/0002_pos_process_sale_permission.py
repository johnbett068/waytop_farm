from django.db import migrations


def create_pos_process_sale_permission(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    content_type, _ = ContentType.objects.get_or_create(app_label="pos", model="orderentry")
    Permission.objects.get_or_create(
        content_type=content_type,
        codename="process_sale",
        defaults={"name": "Can process POS sales"},
    )


def remove_pos_process_sale_permission(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    content_type = ContentType.objects.filter(app_label="pos", model="orderentry").first()
    if content_type is None:
        return
    Permission.objects.filter(content_type=content_type, codename="process_sale").delete()
    if not Permission.objects.filter(content_type=content_type).exists():
        content_type.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_pos_process_sale_permission, remove_pos_process_sale_permission),
    ]
