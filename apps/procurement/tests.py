import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.inventory.adjustments import approve_inventory_adjustment, request_inventory_adjustment
from apps.inventory.models import (
    InventoryAdjustmentRequest, InventoryItem, InventoryLocation, InventoryMovement,
    InventorySupply, Reservation, SourceAllocation, StockPosition,
)
from apps.inventory.supply_services import create_inventory_supply, update_inventory_supply
from apps.commitments.models import Commitment
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.products.models import Product

from .models import SupplierGoodsReceipt, SupplierPurchaseOrder
from .services import (
    PurchaseLineInput, ReceiptLineInput, create_purchase_order, post_goods_receipt,
    save_supplier, transition_purchase_order,
)


class SupplierInventoryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(
            username="supplier-manager", password="test", is_staff=True
        )
        cls.approver = get_user_model().objects.create_user(
            username="stock-approver", password="test", is_staff=True
        )
        cls.outsider = get_user_model().objects.create_user(
            username="supplier-outsider", password="test", is_staff=True
        )
        cls._grant(cls.manager, "procurement.view", "procurement.manage_suppliers",
                   "procurement.manage_purchases", "inventory.view", "inventory.manage_supplies",
                   "inventory.receive", "inventory.adjust")
        cls._grant(cls.approver, "inventory.view", "inventory.approve_adjustment")

    @staticmethod
    def _grant(actor, *names):
        for name in names:
            app, codename = name.split(".")
            actor.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))

    def setUp(self):
        self.supplier = save_supplier(
            code="SUP-001", name="Nursery Inputs Ltd", actor=self.manager,
            reason="Approved supplier", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        self.supply = create_inventory_supply(
            code="TRAY-128", name="128-cell Nursery Tray",
            category=InventorySupply.Category.NURSERY_TRAYS, base_unit="tray",
            allows_fractional_quantity=False, actor=self.manager, reason="Operational stock definition",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        self.location = InventoryLocation.objects.create(code="MAIN", name="Main Store")

    def _po(self, quantity=Decimal("10.000")):
        po = create_purchase_order(
            number=f"PO-{uuid.uuid4().hex[:8]}", supplier_id=self.supplier.pk,
            order_date=date(2026, 8, 31), expected_date=None, reference="", notes="",
            lines=(PurchaseLineInput(
                supply_id=self.supply.pk, ordered_quantity=quantity,
                purchase_unit="tray", base_quantity_per_purchase_unit=Decimal("1.000"),
                unit_cost=Decimal("150.00"),
            ),), actor=self.manager, reason="Purchase nursery trays",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        return transition_purchase_order(
            purchase_order_id=po.pk, to_status=SupplierPurchaseOrder.Status.ORDERED,
            actor=self.manager, reason="Order sent", correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
        )

    def _receipt(self, po, accepted, key=None, number=None):
        return post_goods_receipt(
            number=number or f"GRN-{uuid.uuid4().hex[:8]}", purchase_order_id=po.pk,
            delivery_note_reference=f"DN-{uuid.uuid4().hex[:8]}", receipt_date=date(2026, 8, 31),
            lines=(ReceiptLineInput(
                purchase_order_line_id=po.lines.get().pk,
                accepted_base_quantity=accepted, rejected_base_quantity=Decimal("0.000"),
                rejection_reason="", lot_code="LOT-TRAY-01", destination_location_id=self.location.pk,
            ),), actor=self.manager, reason="Accepted supplier delivery",
            correlation_id=uuid.uuid4(), idempotency_key=key or uuid.uuid4(),
        )


class SupplierInventoryFoundationTests(SupplierInventoryTestCase):
    def test_supply_is_not_product_or_customer_commerce_identity(self):
        item = self.supply.inventory_item
        self.assertEqual(item.kind, InventoryItem.Kind.SUPPLY)
        self.assertIsNone(item.product_id)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_supply_creation_is_idempotent_and_changed_reuse_rejects(self):
        key = uuid.uuid4()
        values = dict(
            code="MEDIA-01", name="Growing Media", category=InventorySupply.Category.GROWING_MEDIA,
            base_unit="kg", allows_fractional_quantity=True, actor=self.manager,
            reason="Define media", correlation_id=uuid.uuid4(), idempotency_key=key,
        )
        first = create_inventory_supply(**values)
        self.assertEqual(create_inventory_supply(**values).pk, first.pk)
        with self.assertRaises(ValidationError):
            create_inventory_supply(**{**values, "name": "Changed"})

    def test_exact_permissions_are_required(self):
        with self.assertRaises(PermissionDenied):
            create_inventory_supply(
                code="NOPE", name="Denied", category=InventorySupply.Category.OTHER,
                base_unit="piece", allows_fractional_quantity=False, actor=self.outsider,
                reason="Denied", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
            )

    def test_duplicate_supply_sku_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_inventory_supply(
                code=self.supply.code, name="Duplicate Tray",
                category=InventorySupply.Category.NURSERY_TRAYS, base_unit="tray",
                allows_fractional_quantity=False, actor=self.manager,
                reason="Attempt duplicate", correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
            )

    def test_supply_can_be_maintained_deactivated_and_reactivated_with_audit(self):
        first = update_inventory_supply(
            supply_id=self.supply.pk, name="128-cell Propagation Tray",
            category=InventorySupply.Category.NURSERY_TRAYS, is_active=False,
            actor=self.manager, reason="Temporarily stop purchasing",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        self.assertFalse(first.is_active)
        self.assertEqual(first.history.count(), 2)
        second = update_inventory_supply(
            supply_id=self.supply.pk, name=first.name,
            category=first.category, is_active=True,
            actor=self.manager, reason="Supply approved again",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        self.assertTrue(second.is_active)
        self.assertEqual(second.history.count(), 3)

    def test_product_and_supply_inventory_items_work_and_database_xor_is_enforced(self):
        product = Product.objects.create(
            sku="SEEDLING-001", slug="seedling-001", name="Tomato Seedling",
            base_inventory_unit="seedling", is_active=True, is_published=False,
        )
        product_item = InventoryItem.objects.create(
            kind=InventoryItem.Kind.PRODUCT, product=product, supply=None,
            base_unit="seedling",
        )
        self.assertEqual(product_item.product, product)
        self.assertEqual(self.supply.inventory_item.supply, self.supply)

        second_product = Product.objects.create(
            sku="SEEDLING-002", slug="seedling-002", name="Cabbage Seedling",
            base_inventory_unit="seedling", is_active=True, is_published=False,
        )
        orphan_supply = InventorySupply(
            code="SUP-XOR", name="XOR fixture", category=InventorySupply.Category.OTHER,
            base_unit="piece", allows_fractional_quantity=False,
        )
        InventorySupply.objects.bulk_create([orphan_supply])
        invalid_both = InventoryItem(
            kind=InventoryItem.Kind.PRODUCT, product=second_product, supply=orphan_supply,
            base_unit="seedling",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            InventoryItem.objects.bulk_create([invalid_both])
        invalid_neither = InventoryItem(
            kind=InventoryItem.Kind.SUPPLY, product=None, supply=None, base_unit="piece",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            InventoryItem.objects.bulk_create([invalid_neither])


class PurchaseAndReceiptTests(SupplierInventoryTestCase):
    def test_purchase_total_and_deterministic_unit_conversion_are_snapshotted(self):
        po = create_purchase_order(
            number="PO-CALC-001", supplier_id=self.supplier.pk,
            order_date=date(2026, 8, 31), expected_date=None, reference="QUOTE-42", notes="",
            lines=(PurchaseLineInput(
                supply_id=self.supply.pk, ordered_quantity=Decimal("20.000"),
                purchase_unit="pack", base_quantity_per_purchase_unit=Decimal("5.000"),
                unit_cost=Decimal("350.00"),
            ),), actor=self.manager, reason="Verify commercial calculation",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        line = po.lines.get()
        self.assertEqual(line.ordered_base_quantity, Decimal("100.000"))
        self.assertEqual(line.line_total, Decimal("7000.00"))
        self.assertEqual(StockPosition.objects.count(), 0)

    def test_invalid_purchase_quantity_and_conversion_are_rejected(self):
        common = dict(
            supplier_id=self.supplier.pk, order_date=date(2026, 8, 31),
            expected_date=None, reference="", notes="", actor=self.manager,
            reason="Invalid purchase", correlation_id=uuid.uuid4(),
        )
        for quantity, conversion in (
            (Decimal("0.000"), Decimal("1.000")),
            (Decimal("1.000"), Decimal("0.000")),
            (Decimal("1.000"), Decimal("1.0001")),
        ):
            with self.subTest(quantity=quantity, conversion=conversion), self.assertRaises(ValidationError):
                create_purchase_order(
                    number=f"PO-BAD-{uuid.uuid4().hex[:6]}",
                    lines=(PurchaseLineInput(
                        supply_id=self.supply.pk, ordered_quantity=quantity,
                        purchase_unit="tray", base_quantity_per_purchase_unit=conversion,
                        unit_cost=Decimal("1.00"),
                    ),), idempotency_key=uuid.uuid4(), **common,
                )

    def test_purchase_has_no_stock_effect_and_partial_receipts_use_ledger(self):
        po = self._po()
        self.assertEqual(StockPosition.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        first = self._receipt(po, Decimal("4.000"))
        po.refresh_from_db()
        self.assertEqual(po.status, SupplierPurchaseOrder.Status.PARTIALLY_RECEIVED)
        self.assertEqual(first.movement.movement_type, InventoryMovement.Type.RECEIPT)
        self.assertEqual(StockPosition.objects.get().on_hand_base_quantity, Decimal("4.000"))
        self._receipt(po, Decimal("6.000"))
        po.refresh_from_db()
        self.assertEqual(po.status, SupplierPurchaseOrder.Status.RECEIVED)
        self.assertEqual(StockPosition.objects.get().on_hand_base_quantity, Decimal("10.000"))

    def test_receipt_is_idempotent_and_over_receipt_rolls_back(self):
        po = self._po()
        key = uuid.uuid4()
        number = "GRN-IDEMPOTENT"
        # Correlation participates in the fingerprint, so exact retry reuses the returned object.
        correlation = uuid.uuid4()
        line = ReceiptLineInput(po.lines.get().pk, Decimal("5.000"), Decimal("0.000"), "", "LOT-IDEM", self.location.pk)
        values = dict(number=number, purchase_order_id=po.pk, delivery_note_reference="DN-IDEM",
                      receipt_date=date(2026, 8, 31), lines=(line,), actor=self.manager,
                      reason="Receive once", correlation_id=correlation, idempotency_key=key)
        first = post_goods_receipt(**values)
        self.assertEqual(post_goods_receipt(**values).pk, first.pk)
        self.assertEqual(SupplierGoodsReceipt.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self._receipt(po, Decimal("6.000"))
        self.assertEqual(StockPosition.objects.get().on_hand_base_quantity, Decimal("5.000"))

    def test_discrete_supply_rejects_fractional_receipt(self):
        po = self._po()
        with self.assertRaises(ValidationError):
            self._receipt(po, Decimal("0.500"))

    def test_receipt_is_auditable_and_creates_no_customer_commerce_effects(self):
        po = self._po()
        receipt = self._receipt(po, Decimal("3.000"))
        line = receipt.lines.select_related("purchase_order_line", "movement_line").get()
        self.assertEqual(receipt.received_by, self.manager)
        self.assertTrue(receipt.delivery_note_reference.startswith("DN-"))
        self.assertEqual(line.accepted_base_quantity, Decimal("3.000"))
        self.assertEqual(line.purchase_order_line.base_quantity_per_purchase_unit, Decimal("1.000"))
        self.assertEqual(line.movement_line.quantity, Decimal("3.000"))
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertEqual(SourceAllocation.objects.count(), 0)
        self.assertEqual(Commitment.objects.count(), 0)

    def test_receipt_requires_positive_accepted_physical_stock(self):
        po = self._po()
        with self.assertRaises(ValidationError):
            self._receipt(po, Decimal("0.000"))


class AdjustmentWorkflowTests(SupplierInventoryTestCase):
    def test_distinct_approver_posts_exact_adjustment_and_prevents_negative(self):
        po = self._po()
        self._receipt(po, Decimal("5.000"))
        position = StockPosition.objects.select_related("lot").get()
        request = request_inventory_adjustment(
            item_id=position.item_id, lot_id=position.lot_id, location_id=position.location_id,
            direction=InventoryAdjustmentRequest.Direction.OUT, base_quantity=Decimal("2.000"),
            actor=self.manager, reason="Count variance", correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaises(PermissionDenied):
            approve_inventory_adjustment(
                adjustment_id=request.pk, actor=self.manager, reason="Self approval",
                correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
            )
        approved = approve_inventory_adjustment(
            adjustment_id=request.pk, actor=self.approver, reason="Independent count review",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        self.assertEqual(approved.state, InventoryAdjustmentRequest.State.APPROVED)
        position.refresh_from_db()
        self.assertEqual(position.on_hand_base_quantity, Decimal("3.000"))
        excessive = request_inventory_adjustment(
            item_id=position.item_id, lot_id=position.lot_id, location_id=position.location_id,
            direction=InventoryAdjustmentRequest.Direction.OUT, base_quantity=Decimal("4.000"),
            actor=self.manager, reason="Bad variance", correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            approve_inventory_adjustment(
                adjustment_id=excessive.pk, actor=self.approver, reason="Would go negative",
                correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
            )
        position.refresh_from_db()
        self.assertEqual(position.on_hand_base_quantity, Decimal("3.000"))


class SupplierInventoryStaffUITests(SupplierInventoryTestCase):
    def test_permission_protected_pages_render(self):
        self.client.force_login(self.manager)
        for route in (
            "dashboard:procurement_supplier_list", "dashboard:procurement_purchase_list",
            "dashboard:inventory_supply_list", "dashboard:inventory_stock",
            "dashboard:inventory_history", "dashboard:inventory_adjustments",
        ):
            with self.subTest(route=route): self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("dashboard:inventory_stock")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:procurement_supplier_list")).status_code, 403)

    def test_inventory_shortcuts_cover_every_inventory_and_procurement_screen(self):
        self.client.force_login(self.manager)
        purchase_order = self._po()
        paths = (
            reverse("dashboard:inventory"),
            reverse("dashboard:inventory_items"),
            reverse("dashboard:inventory_lots"),
            reverse("dashboard:inventory_movements"),
            reverse("dashboard:inventory_receiving"),
            reverse("dashboard:inventory_transfers"),
            reverse("dashboard:inventory_counts"),
            reverse("dashboard:inventory_supply_list"),
            reverse("dashboard:inventory_supply_create"),
            reverse("dashboard:inventory_supply_detail", args=(self.supply.code,)),
            reverse("dashboard:inventory_supply_edit", args=(self.supply.code,)),
            reverse("dashboard:inventory_receipt_create"),
            reverse("dashboard:inventory_stock"),
            reverse("dashboard:inventory_history"),
            reverse("dashboard:inventory_adjustments"),
            reverse("dashboard:procurement_supplier_list"),
            reverse("dashboard:procurement_supplier_create"),
            reverse("dashboard:procurement_supplier_edit", args=(self.supplier.pk,)),
            reverse("dashboard:procurement_purchase_list"),
            reverse("dashboard:procurement_purchase_create"),
            reverse("dashboard:procurement_purchase_detail", args=(purchase_order.number,)),
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="inventory-shortcuts"')
                self.assertContains(response, 'class="inventory-shortcuts__home"')

        response = self.client.get(reverse("dashboard:inventory"))
        expected_links = (
            ("dashboard:inventory", "Overview"),
            ("dashboard:inventory_stock", "On-Hand Stock"),
            ("dashboard:inventory_receipt_create", "Receive Stock"),
            ("dashboard:inventory_supply_list", "Supply Definitions"),
            ("dashboard:procurement_purchase_list", "Purchase Orders"),
            ("dashboard:procurement_supplier_list", "Suppliers"),
            ("dashboard:inventory_history", "Ledger History"),
        )
        for route, label in expected_links:
            with self.subTest(route=route):
                self.assertContains(response, f'href="{reverse(route)}"')
                self.assertContains(response, label)
        self.assertContains(response, 'aria-label="Inventory and procurement shortcuts"')
        self.assertContains(response, 'aria-current="page"')

        dashboard_response = self.client.get(reverse("dashboard:dashboard"))
        self.assertNotContains(dashboard_response, 'class="inventory-shortcuts"')

    def test_create_forms_persist_authoritative_records(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("dashboard:inventory_supply_create"), {
            "code": "PACK-01", "name": "Packaging", "category": "PACKAGING",
            "base_unit": "piece", "allows_fractional_quantity": "",
            "reason": "Create packaging", "correlation_id": uuid.uuid4(),
            "idempotency_key": uuid.uuid4(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(InventorySupply.objects.filter(code="PACK-01").exists())

    def test_purchase_form_explains_order_receipt_boundary_and_total(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("dashboard:procurement_purchase_create"))
        self.assertContains(response, "Creating a purchase order does not add stock")
        self.assertContains(response, "WayTop purchase order number")
        self.assertContains(response, "Supplier document / reference number")
        self.assertContains(response, "Supply being ordered")
        self.assertContains(response, "Total ordered cost")
        self.assertContains(response, "staff-procurement.css")
        self.assertContains(response, 'class="purchase-order-form__grid"', count=2)
        self.assertContains(response, 'class="purchase-order-form__help"')
        for field_name in (
            "reason", "number", "supplier", "order_date", "expected_date", "reference", "notes",
            "supply", "ordered_quantity", "purchase_unit",
            "base_quantity_per_purchase_unit", "unit_cost", "correlation_id", "idempotency_key",
        ):
            with self.subTest(field_name=field_name):
                self.assertContains(response, f'name="{field_name}"')
                self.assertContains(response, f'id="id_{field_name}"')

    def test_supply_and_supplier_forms_use_block_layout_without_contract_changes(self):
        self.client.force_login(self.manager)
        cases = (
            (
                "dashboard:inventory_supply_create", "dashboard/inventory/form_live.html",
                ("reason", "code", "name", "category", "base_unit",
                 "allows_fractional_quantity", "is_active", "correlation_id", "idempotency_key"),
            ),
            (
                "dashboard:procurement_supplier_create", "dashboard/procurement/form_live.html",
                ("reason", "code", "name", "contact_person", "phone", "email", "address",
                 "notes", "is_active", "correlation_id", "idempotency_key"),
            ),
        )
        for route, template, field_names in cases:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)
                self.assertContains(response, "staff-procurement.css")
                self.assertContains(response, 'class="purchase-order-form__grid"')
                self.assertContains(response, 'class="purchase-order-form__label"')
                if route == "dashboard:inventory_supply_create":
                    self.assertContains(response, 'class="purchase-order-form__help"')
                for field_name in field_names:
                    self.assertContains(response, f'name="{field_name}"')
                    self.assertContains(response, f'id="id_{field_name}"')

    def test_supply_definition_form_has_staff_friendly_sections_order_and_errors(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("dashboard:inventory_supply_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operational supply")
        self.assertContains(response, "not a customer-saleable Product")
        self.assertContains(response, "Supply information")
        self.assertContains(response, "Inventory settings")
        self.assertContains(response, "Record reason")
        self.assertContains(response, "Supply name")
        self.assertContains(response, "Active supply")
        self.assertContains(response, "Save Supply")
        self.assertContains(response, "Tomato Seeds — Rio Grande")
        self.assertContains(response, "SUP-SEED-TOM-001")
        self.assertContains(response, "Use the name staff recognize")
        self.assertContains(response, "Inactive supplies remain in history")

        content = response.content.decode()
        ordered_markers = (
            "Supply information", 'id="id_name"', 'id="id_code"', 'id="id_category"',
            'id="id_base_unit"', "Inventory settings", 'id="id_allows_fractional_quantity"',
            'id="id_is_active"', "Record reason", 'id="id_reason"', "Save Supply", "Cancel",
        )
        positions = [content.index(marker) for marker in ordered_markers]
        self.assertEqual(positions, sorted(positions))

        invalid = self.client.post(reverse("dashboard:inventory_supply_create"), {
            "name": "", "code": "", "category": "", "base_unit": "", "reason": "",
            "allows_fractional_quantity": "", "is_active": "on",
            "correlation_id": uuid.uuid4(), "idempotency_key": uuid.uuid4(),
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, 'aria-invalid="true"')
        self.assertContains(invalid, "This field is required.")

    def test_receipt_form_has_grouped_layout_and_preserves_field_contract(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("dashboard:inventory_receipt_create"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/inventory/receipt_form_live.html")
        self.assertContains(response, "staff-procurement.css")
        self.assertContains(response, 'class="purchase-order-form__grid"', count=3)
        self.assertContains(response, "Receipt identity")
        self.assertContains(response, "Supply and quantities")
        self.assertContains(response, "Lot and destination")
        for field_name in (
            "reason", "number", "purchase_order_line", "delivery_note_reference", "receipt_date",
            "accepted_base_quantity", "rejected_base_quantity", "rejection_reason", "lot_code",
            "destination_location", "correlation_id", "idempotency_key",
        ):
            with self.subTest(field_name=field_name):
                self.assertContains(response, f'name="{field_name}"')
                self.assertContains(response, f'id="id_{field_name}"')

    def test_adjustment_forms_use_explicit_block_field_layout(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("dashboard:inventory_adjustments"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "staff-procurement.css")
        self.assertContains(response, 'class="purchase-order-form__label"')
        self.assertContains(response, reverse("dashboard:inventory_adjustment_request"))
        self.assertContains(response, reverse("dashboard:inventory_adjustment_approve"))

    def test_supply_edit_can_deactivate_definition(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("dashboard:inventory_supply_edit", args=(self.supply.code,)),
            {
                "code": self.supply.code, "name": "Tray definition paused",
                "category": self.supply.category, "base_unit": self.supply.base_unit,
                "allows_fractional_quantity": "", "is_active": "",
                "reason": "Supplier discontinued line", "correlation_id": uuid.uuid4(),
                "idempotency_key": uuid.uuid4(),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.supply.refresh_from_db()
        self.assertFalse(self.supply.is_active)
