import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.procurement.services import save_supplier
from apps.products.models import Product, ProductSaleUnit

from .acquisitions import acquire_external_stock
from .availability import eligible_stock_positions, get_ready_availability
from .forms import StockAcquisitionForm
from .models import (
    ExternalStockAcquisition, InventoryItem, InventoryLocation, InventoryMovement,
    StockLot, StockPosition,
)


class ExternalStockAcquisitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="ACQ-SEED-001", slug="acquired-seedling", name="Acquired Seedling",
            base_inventory_unit="seedling", is_active=True, is_published=True,
        )
        cls.sale_unit = ProductSaleUnit.objects.create(
            product=cls.product, name="Single seedling", base_quantity=Decimal("1.000")
        )
        cls.item = InventoryItem.objects.create(
            product=cls.product, base_unit=cls.product.base_inventory_unit
        )
        cls.location = InventoryLocation.objects.create(code="ACQ-MAIN", name="Acquisition Store")
        cls.actor = get_user_model().objects.create_user(
            username="stock-acquirer", password="test", is_staff=True
        )
        cls.viewer = get_user_model().objects.create_user(
            username="stock-viewer", password="test", is_staff=True
        )
        for actor, permissions in (
            (cls.actor, (("inventory", "view"), ("inventory", "receive"), ("procurement", "manage_suppliers"))),
            (cls.viewer, (("inventory", "view"),)),
        ):
            actor.user_permissions.add(*[
                Permission.objects.get(content_type__app_label=app, codename=codename)
                for app, codename in permissions
            ])
        cls.supplier = save_supplier(
            code="ACQ-SOURCE", name="Occasional Seedling Source", actor=cls.actor,
            reason="Existing source", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )

    def values(self, **overrides):
        values = {
            "product_id": self.product.pk,
            "quantity": Decimal("12.345"),
            "unit_cost": Decimal("17.25"),
            "acquisition_date": date(2026, 9, 7),
            "supplier_id": self.supplier.pk,
            "location_id": self.location.pk,
            "supplier_batch_reference": "EXT-LOT-001",
            "condition": StockLot.Condition.SALEABLE,
            "reference": "INV-EXT-001",
            "note": "Occasional external seedling purchase",
            "actor": self.actor,
            "correlation_id": uuid.uuid4(),
            "idempotency_key": uuid.uuid4(),
        }
        values.update(overrides)
        return values

    def catalog_product(self, **overrides):
        values = dict(
            id=uuid.UUID("8de0cae8-7a0f-4729-b1c8-9f4fc2c2ecb2"),
            name="Tomato Seedling", sku="TOMATO SEEDLING", slug="tomato-seedling",
            category=Product.Category.VEGETABLE, base_inventory_unit="seedling",
        )
        values.update(overrides)
        return Product.objects.create(**values)

    def test_dropdown_includes_catalog_only_legacy_product_and_existing_item(self):
        product = self.catalog_product()
        self.client.force_login(self.actor)
        response = self.client.get(reverse("dashboard:inventory_receipt_create"))
        self.assertContains(response, '<select name="product"')
        self.assertContains(response, f'<option value="{product.pk}">')
        self.assertContains(response, "TOMATO SEEDLING")
        self.assertIn(self.product, response.context["form"].fields["product"].queryset)
        self.assertFalse(InventoryItem.objects.filter(product=product).exists())

    def test_new_catalog_products_in_all_categories_are_eligible(self):
        from apps.products.services import create_seedling_product

        self.actor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="products",
            codename__in=("add_product", "add_productsaleunit", "add_productprice"),
        ))
        actor = get_user_model().objects.get(pk=self.actor.pk)
        for category in Product.Category.values:
            product, _, _ = create_seedling_product(
                name=f"New {category}", category=category, description="",
                base_inventory_unit="seedling", is_active=True, is_published=False,
                sale_unit_name="Single", sale_unit_base_quantity=Decimal("1"),
                price_amount=None, price_effective_start=None, actor=actor,
            )
            self.assertIn(product, StockAcquisitionForm().fields["product"].queryset)
            self.assertFalse(InventoryItem.objects.filter(product=product).exists())

    def test_inactive_product_and_inactive_item_remain_ineligible(self):
        product = self.catalog_product(is_active=False)
        self.item.is_active = False
        self.item.save()
        queryset = StockAcquisitionForm().fields["product"].queryset
        self.assertNotIn(product, queryset)
        self.assertNotIn(self.product, queryset)
        for target in (product, self.product):
            with self.assertRaises(ValidationError):
                acquire_external_stock(**self.values(product_id=target.pk))
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_catalog_only_product_submission_creates_one_authoritative_item(self):
        product = self.catalog_product()
        self.client.force_login(self.actor)
        data = self.values(product_id=product.pk, supplier_id=None, quantity="5.000")
        data.pop("actor")
        data["product"] = data.pop("product_id")
        data["location"] = data.pop("location_id")
        data["supplier"] = ""
        data.pop("supplier_id")
        url = reverse("dashboard:inventory_receipt_create")
        for _ in range(2):
            self.assertRedirects(self.client.post(url, data), reverse("dashboard:inventory_stock"))
        item = InventoryItem.objects.get(product=product)
        self.assertEqual(item.base_unit, product.base_inventory_unit)
        self.assertEqual(InventoryItem.objects.filter(product=product).count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 1)
        self.assertEqual(ExternalStockAcquisition.objects.count(), 1)
        self.assertEqual(StockPosition.objects.get(item=item).on_hand_base_quantity, Decimal("5.000"))
        self.assertEqual(InventoryMovement.objects.get().movement_type, InventoryMovement.Type.RECEIPT)
        self.assertContains(self.client.get(reverse("dashboard:inventory_stock")), product.name)
        self.assertContains(self.client.get(reverse("dashboard:inventory_history")), product.name)
        product.refresh_from_db()
        self.assertEqual(product.sku, "TOMATO SEEDLING")

    def test_failed_receipt_rolls_back_new_inventory_item(self):
        product = self.catalog_product()
        self.location.is_active = False
        self.location.save()
        with self.assertRaises(InventoryLocation.DoesNotExist):
            acquire_external_stock(**self.values(product_id=product.pk))
        self.assertFalse(InventoryItem.objects.filter(product=product).exists())
        self.assertEqual(StockPosition.objects.count(), 0)

    def test_supplier_is_optional_and_legacy_status_does_not_restrict_acquisition(self):
        supplier = save_supplier(
            supplier_id=self.supplier.pk, code=self.supplier.code, name=self.supplier.name,
            is_active=False, actor=self.actor, reason="Legacy status fixture",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        product = self.catalog_product()
        self.client.force_login(self.actor)
        original_products = list(StockAcquisitionForm().fields["product"].queryset)
        for source in (None, supplier):
            data = self.values(product_id=product.pk, quantity="3.000")
            data.pop("actor")
            data["product"] = data.pop("product_id")
            data["location"] = data.pop("location_id")
            data.pop("supplier_id")
            data["supplier"] = source.pk if source else ""
            for _ in range(2):
                self.assertRedirects(self.client.post(reverse("dashboard:inventory_receipt_create"), data),
                                     reverse("dashboard:inventory_stock"))
            acquisition = ExternalStockAcquisition.objects.get(idempotency_key=data["idempotency_key"])
            self.assertEqual(acquisition.supplier, source)
            self.assertEqual(acquisition.movement.movement_type, InventoryMovement.Type.RECEIPT)
            self.assertEqual(acquisition.movement_line.quantity, Decimal("3.000"))
        self.assertEqual(list(StockAcquisitionForm().fields["product"].queryset), original_products)
        self.assertEqual(InventoryItem.objects.filter(product=product).count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 2)
        self.assertEqual(sum(StockPosition.objects.filter(item__product=product).values_list("on_hand_base_quantity", flat=True)), Decimal("6.000"))
        response = self.client.get(reverse("dashboard:inventory_history"))
        self.assertContains(response, supplier.name)
        self.assertContains(response, "Supplier: Not specified")

    def test_supplier_edit_preserves_acquisition_evidence(self):
        acquisition = acquire_external_stock(**self.values())
        evidence = (acquisition.supplier_id, acquisition.acquisition_date, acquisition.unit_cost,
                    acquisition.movement_line.quantity, acquisition.movement_id)
        self.client.force_login(self.actor)
        self.assertRedirects(self.client.post(
            reverse("dashboard:inventory_supplier_edit", args=(self.supplier.pk,)),
            {"name": "Renamed Nursery", "correlation_id": uuid.uuid4(), "idempotency_key": uuid.uuid4()},
        ), reverse("dashboard:inventory_supplier_list"))
        acquisition.refresh_from_db()
        self.assertEqual((acquisition.supplier_id, acquisition.acquisition_date, acquisition.unit_cost,
                          acquisition.movement_line.quantity, acquisition.movement_id), evidence)
        self.assertContains(self.client.get(reverse("dashboard:inventory_history")), "Renamed Nursery")

    def test_supplier_does_not_replace_required_traceability(self):
        for supplier in ("", self.supplier.pk):
            for missing in ("location", "condition"):
                data = dict(product=self.product.pk, quantity="1.000", unit_cost="2.00",
                            acquisition_date="2026-09-07", supplier=supplier, location=self.location.pk,
                            supplier_batch_reference="REQUIRED", condition=StockLot.Condition.SALEABLE,
                            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())
                data[missing] = ""
                form = StockAcquisitionForm(data)
                self.assertFalse(form.is_valid())
                self.assertIn(missing, form.errors)
        self.assertFalse(InventoryMovement.objects.exists())

    def test_acquisition_posts_authoritative_receipt_with_exact_cost_and_traceability(self):
        acquisition = acquire_external_stock(**self.values())

        self.assertEqual(acquisition.movement.movement_type, InventoryMovement.Type.RECEIPT)
        self.assertEqual(acquisition.movement.source_type, "EXTERNAL_STOCK_ACQUISITION")
        self.assertEqual(acquisition.movement_line.item, self.item)
        self.assertEqual(acquisition.movement_line.quantity, Decimal("12.345"))
        self.assertEqual(acquisition.movement_line.destination_location, self.location)
        self.assertEqual(acquisition.supplier_batch_reference, "EXT-LOT-001")
        self.assertEqual(acquisition.movement_line.lot.lot_code, f"WTP-LOT-{acquisition.idempotency_key.hex.upper()}")
        self.assertEqual(acquisition.supplier, self.supplier)
        self.assertEqual(acquisition.unit_cost, Decimal("17.25"))
        self.assertEqual(acquisition.total_acquisition_cost, Decimal("212.95"))
        self.assertEqual(acquisition.currency, "KES")
        self.assertEqual(
            StockPosition.objects.get(item=self.item, location=self.location).on_hand_base_quantity,
            Decimal("12.345"),
        )
        self.assertEqual(ExternalStockAcquisition.objects.count(), 1)

    def test_generated_lots_are_distinct_and_external_reference_is_optional(self):
        legacy = StockLot.objects.create(item=self.item, lot_code="HISTORICAL-LOT", condition="SALEABLE")
        first = acquire_external_stock(**self.values(supplier_id=None, supplier_batch_reference=""))
        second = acquire_external_stock(**self.values(supplier_id=None, supplier_batch_reference="TOM-SEP-26-A"))
        self.assertNotEqual(first.movement_line.lot_id, second.movement_line.lot_id)
        self.assertNotEqual(first.movement_line.lot.lot_code, second.movement_line.lot.lot_code)
        self.assertEqual(first.supplier_batch_reference, "")
        self.assertEqual(second.supplier_batch_reference, "TOM-SEP-26-A")
        self.assertNotEqual(second.movement_line.lot.lot_code, second.supplier_batch_reference)
        self.assertEqual(StockPosition.objects.get(lot=first.movement_line.lot).on_hand_base_quantity, Decimal("12.345"))
        legacy.refresh_from_db()
        self.assertEqual(legacy.lot_code, "HISTORICAL-LOT")
        self.client.force_login(self.actor)
        response = self.client.get(reverse("dashboard:inventory_history"))
        self.assertContains(response, first.movement_line.lot.lot_code)
        self.assertContains(response, "TOM-SEP-26-A")
        self.assertContains(self.client.get(reverse("dashboard:inventory_stock")), second.movement_line.lot.lot_code)

    def test_generated_identifier_cannot_be_renamed_and_collision_does_not_reuse_history(self):
        values = self.values()
        code = f"WTP-LOT-{values['idempotency_key'].hex.upper()}"
        legacy = StockLot.objects.create(item=self.item, lot_code=code, condition="SALEABLE")
        with self.assertRaises(ValidationError):
            acquire_external_stock(**values)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        legacy.refresh_from_db()
        self.assertEqual(legacy.lot_code, code)
        acquisition = acquire_external_stock(**self.values())
        lot = acquisition.movement_line.lot
        lot.lot_code = "RENAMED"
        with self.assertRaises(ValidationError):
            lot.save()
        with self.assertRaises(ValidationError):
            StockLot.objects.filter(pk=lot.pk).update(lot_code="RENAMED")
        with self.assertRaises(ValidationError):
            StockLot.objects.bulk_update([lot], ["lot_code"])

    def test_supplier_batch_is_part_of_idempotent_input_and_conditions_are_preserved(self):
        for condition in StockLot.Condition.values:
            values = self.values(condition=condition, supplier_batch_reference="")
            acquisition = acquire_external_stock(**values)
            self.assertEqual(acquisition.movement_line.lot.condition, condition)
            self.assertEqual(acquire_external_stock(**values).pk, acquisition.pk)
            with self.assertRaises(ValidationError):
                acquire_external_stock(**{**values, "supplier_batch_reference": "CHANGED"})
        self.assertEqual(StockLot.objects.count(), len(StockLot.Condition.values))

    def test_form_requires_no_manual_lot_or_supplier_reference(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse("dashboard:inventory_receipt_create"))
        self.assertNotIn("lot_code", response.context["form"].fields)
        self.assertFalse(response.context["form"].fields["supplier_batch_reference"].required)
        self.assertContains(response, "Automatically generated for traceability")
        data = self.values(supplier_id=None)
        for field in ("actor", "supplier_id", "supplier_batch_reference"):
            data.pop(field)
        data["product"] = data.pop("product_id")
        data["location"] = data.pop("location_id")
        self.assertRedirects(self.client.post(reverse("dashboard:inventory_receipt_create"), data),
                             reverse("dashboard:inventory_stock"))
        self.assertEqual(ExternalStockAcquisition.objects.get().supplier_batch_reference, "")

    def test_acquired_stock_is_visible_to_on_hand_history_and_shared_availability(self):
        acquire_external_stock(**self.values(quantity="7.000", supplier_id=None))
        self.client.force_login(self.actor)

        stock_response = self.client.get(reverse("dashboard:inventory_stock"))
        history_response = self.client.get(reverse("dashboard:inventory_history"))
        self.assertContains(stock_response, self.product.name)
        self.assertContains(stock_response, "7.000")
        self.assertContains(history_response, self.product.name)
        self.assertContains(history_response, "Occasional external seedling purchase")
        self.assertEqual(
            get_ready_availability(product=self.product, sale_unit=self.sale_unit).available_sale_units,
            7,
        )
        self.assertTrue(
            eligible_stock_positions(
                inventory_item=self.item, business_date=date(2026, 9, 7)
            ).filter(location=self.location).exists()
        )

    def test_selected_lot_condition_controls_existing_availability_rules(self):
        acquire_external_stock(**self.values(
            quantity="4.000", condition=StockLot.Condition.HELD, supplier_batch_reference="HELD-LOT"
        ))
        self.assertEqual(StockPosition.objects.get().on_hand_base_quantity, Decimal("4.000"))
        self.assertEqual(
            get_ready_availability(product=self.product, sale_unit=self.sale_unit).available_sale_units,
            0,
        )
        self.assertFalse(eligible_stock_positions(
            inventory_item=self.item, business_date=date(2026, 9, 7)
        ).exists())

    def test_retry_is_idempotent_and_changed_reuse_is_rejected(self):
        key, correlation = uuid.uuid4(), uuid.uuid4()
        values = self.values(idempotency_key=key, correlation_id=correlation)
        first = acquire_external_stock(**values)
        second = acquire_external_stock(**values)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ExternalStockAcquisition.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 1)
        self.assertEqual(StockPosition.objects.get().on_hand_base_quantity, Decimal("12.345"))
        with self.assertRaises(ValidationError):
            acquire_external_stock(**{**values, "quantity": Decimal("13.000")})

    def test_invalid_quantity_cost_and_precision_do_not_create_stock(self):
        for overrides in (
            {"quantity": "0"}, {"quantity": "-1"}, {"quantity": "1.0001"},
            {"unit_cost": "-0.01"}, {"unit_cost": "1.001"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                acquire_external_stock(**self.values(**overrides))
        self.assertEqual(ExternalStockAcquisition.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        self.assertEqual(StockPosition.objects.count(), 0)

    def test_receive_permission_is_required_and_failure_is_atomic(self):
        with self.assertRaises(PermissionDenied):
            acquire_external_stock(**self.values(actor=self.viewer))
        self.assertEqual(ExternalStockAcquisition.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        self.assertEqual(StockLot.objects.count(), 0)

    def test_form_submission_records_acquisition_without_purchase_order(self):
        self.client.force_login(self.actor)
        key = uuid.uuid4()
        data = {
            "product": self.product.pk,
            "quantity": "5.000",
            "unit_cost": "20.50",
            "acquisition_date": "2026-09-07",
            "supplier": self.supplier.pk,
            "location": self.location.pk,
            "supplier_batch_reference": "WEB-LOT-001",
            "condition": StockLot.Condition.SALEABLE,
            "reference": "WEB-REF-001",
            "note": "Web acquisition",
            "correlation_id": uuid.uuid4(),
            "idempotency_key": key,
        }
        first = self.client.post(reverse("dashboard:inventory_receipt_create"), data)
        second = self.client.post(reverse("dashboard:inventory_receipt_create"), data)
        self.assertRedirects(first, reverse("dashboard:inventory_stock"))
        self.assertRedirects(second, reverse("dashboard:inventory_stock"))
        self.assertEqual(ExternalStockAcquisition.objects.filter(idempotency_key=key).count(), 1)
        self.assertEqual(StockPosition.objects.get().on_hand_base_quantity, Decimal("5.000"))

    def test_unauthorized_form_submission_is_forbidden(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("dashboard:inventory_receipt_create"), {
            "product": self.product.pk, "quantity": "1.000", "unit_cost": "10.00",
            "acquisition_date": "2026-09-07", "supplier": "",
            "location": self.location.pk, "supplier_batch_reference": "DENIED-LOT", "reference": "",
            "condition": StockLot.Condition.SALEABLE, "note": "",
            "correlation_id": uuid.uuid4(), "idempotency_key": uuid.uuid4(),
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(InventoryMovement.objects.count(), 0)
