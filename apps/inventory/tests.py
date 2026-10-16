import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.test import TestCase
from django.urls import reverse

from apps.products.models import Product

from .models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    InventoryMovementLine,
    StockLot,
    StockPosition,
)
from .services import MovementLineInput, post_inventory_movement


class InventoryTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-INV-001",
            slug="inventory-seedling",
            name="Inventory Seedling",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=False,
        )
        self.item = InventoryItem.objects.create(
            product=self.product,
            base_unit="seedling",
        )
        self.location = InventoryLocation.objects.create(
            code="main-store",
            name="Main Store",
        )
        self.other_location = InventoryLocation.objects.create(
            code="dispatch",
            name="Dispatch Staging",
        )
        self.lot = StockLot.objects.create(
            item=self.item,
            lot_code="LOT-001",
            condition=StockLot.Condition.SALEABLE,
            provenance_reference="OPENING-EVIDENCE-001",
        )
        self.actor = get_user_model().objects.create_user(
            username="inventory-actor",
            password=None,
            is_staff=True,
        )

    def grant(self, *codenames):
        permissions = Permission.objects.filter(
            content_type__app_label="inventory",
            codename__in=codenames,
        )
        self.actor.user_permissions.add(*permissions)
        self.actor = get_user_model().objects.get(pk=self.actor.pk)

    def line(self, *, quantity="10.000", source=None, destination=None, item=None, lot=None):
        return MovementLineInput(
            item_id=(item or self.item).pk,
            lot_id=(lot or self.lot).pk,
            quantity=Decimal(quantity),
            source_location_id=source.pk if source else None,
            destination_location_id=destination.pk if destination else None,
        )

    def post(self, movement_type, lines, **overrides):
        values = {
            "movement_type": movement_type,
            "lines": lines,
            "actor": self.actor,
            "reason": "Authoritative test movement",
            "idempotency_key": uuid.uuid4(),
        }
        values.update(overrides)
        return post_inventory_movement(**values)

    def receive(self, quantity="10.000", **overrides):
        self.grant("receive")
        return self.post(
            InventoryMovement.Type.RECEIPT,
            [self.line(quantity=quantity, destination=self.location)],
            **overrides,
        )


class InventoryModelTests(InventoryTestCase):
    def test_item_is_one_to_one_with_product_and_snapshots_matching_base_unit(self):
        self.assertEqual(self.product.inventory_item, self.item)
        with self.assertRaises(ValidationError):
            InventoryItem.objects.create(product=self.product, base_unit="tray")
        with self.assertRaises(ValidationError):
            InventoryItem.objects.create(product=self.product, base_unit="seedling")

    def test_product_relationship_is_protected_and_no_customer_branch_or_order_fields_exist(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.product.delete()
        for model in (InventoryItem, InventoryLocation, StockLot, StockPosition):
            fields = {field.name for field in model._meta.get_fields()}
            self.assertTrue({"customer", "order", "branch", "sale_unit"}.isdisjoint(fields))

    def test_location_code_is_stable_internal_identity_without_branch(self):
        self.assertEqual(self.location.code, "MAIN-STORE")
        self.assertTrue(self.location.allows_saleable_stock)
        self.location.code = "RENUMBERED"
        with self.assertRaises(ValidationError):
            self.location.save()
        with self.assertRaises(ValidationError):
            InventoryLocation.objects.create(code="MAIN-STORE", name="Duplicate")

    def test_lot_code_is_unique_per_item_and_condition_change_is_not_direct_crud(self):
        with self.assertRaises(ValidationError):
            StockLot.objects.create(
                item=self.item,
                lot_code=self.lot.lot_code,
                condition=StockLot.Condition.HELD,
            )
        self.lot.condition = StockLot.Condition.HELD
        with self.assertRaises(ValidationError):
            self.lot.save()

    def test_stock_position_relationship_rejects_a_lot_from_another_item(self):
        other_product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-INV-002",
            slug="other-inventory-item",
            name="Other Item",
            base_inventory_unit="seedling",
        )
        other_item = InventoryItem.objects.create(product=other_product, base_unit="seedling")
        position = StockPosition(
            item=other_item,
            location=self.location,
            lot=self.lot,
            on_hand_base_quantity=0,
        )
        with self.assertRaises(ValidationError):
            position.save(_inventory_service_write=True)

    def test_direct_position_and_movement_writes_are_blocked(self):
        with self.assertRaises(ValidationError):
            StockPosition.objects.create(
                item=self.item,
                location=self.location,
                lot=self.lot,
                on_hand_base_quantity=1,
            )
        with self.assertRaises(ValidationError):
            InventoryMovement.objects.create(
                movement_type=InventoryMovement.Type.RECEIPT,
                actor=self.actor,
                reason="Bypass",
                idempotency_key=uuid.uuid4(),
                request_fingerprint="0" * 64,
            )
        with self.assertRaises(ValidationError):
            StockPosition.objects.update(on_hand_base_quantity=10)
        with self.assertRaises(ValidationError):
            InventoryMovement.objects.bulk_create([])
        with self.assertRaises(ValidationError):
            InventoryMovementLine.objects.update(quantity=10)

    def test_database_rejects_negative_position_even_when_model_guard_is_bypassed(self):
        self.receive()
        position = StockPosition.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet(model=StockPosition, using="default").filter(
                pk=position.pk
            ).update(on_hand_base_quantity=-1)

    def test_product_and_item_base_units_are_immutable_after_movement(self):
        self.receive()
        self.product.base_inventory_unit = "tray"
        with self.assertRaises(ValidationError):
            self.product.save()
        self.item.base_unit = "tray"
        with self.assertRaises(ValidationError):
            self.item.save()

    def test_empty_database_does_not_fabricate_positions_movements_or_quantities(self):
        self.assertEqual(StockPosition.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.count(), 0)
        self.assertEqual(InventoryMovementLine.objects.count(), 0)


class InventoryMovementServiceTests(InventoryTestCase):
    def test_receipt_posts_immutable_history_and_creates_position(self):
        movement = self.receive("10.125", source_type="MANUAL_RECEIPT", source_reference="MR-001")
        line = movement.lines.get()
        position = StockPosition.objects.get(
            item=self.item, location=self.location, lot=self.lot
        )
        self.assertEqual(line.quantity, Decimal("10.125"))
        self.assertEqual(position.on_hand_base_quantity, Decimal("10.125"))
        self.assertEqual(position.version, 1)
        with self.assertRaises(ValidationError):
            movement.delete()
        with self.assertRaises(ValidationError):
            line.delete()
        movement.reason = "Rewritten"
        with self.assertRaises(ValidationError):
            movement.save(_inventory_service_write=True)

    def test_issue_decreases_position_without_creating_negative_inventory(self):
        self.receive("10.000")
        self.grant("release")
        self.post(
            InventoryMovement.Type.ISSUE,
            [self.line(quantity="4.250", source=self.location)],
        )
        position = StockPosition.objects.get()
        self.assertEqual(position.on_hand_base_quantity, Decimal("5.750"))
        self.assertEqual(position.version, 2)
        before = InventoryMovement.objects.count()
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.ISSUE,
                [self.line(quantity="6.000", source=self.location)],
            )
        self.assertEqual(InventoryMovement.objects.count(), before)
        position.refresh_from_db()
        self.assertEqual(position.on_hand_base_quantity, Decimal("5.750"))

    def test_transfer_updates_source_and_destination_atomically(self):
        self.receive("12.000")
        self.grant("transfer")
        movement = self.post(
            InventoryMovement.Type.TRANSFER,
            [
                self.line(
                    quantity="5.000",
                    source=self.location,
                    destination=self.other_location,
                )
            ],
        )
        self.assertEqual(movement.lines.count(), 1)
        quantities = {
            position.location.code: position.on_hand_base_quantity
            for position in StockPosition.objects.all()
        }
        self.assertEqual(
            quantities,
            {"MAIN-STORE": Decimal("7.000"), "DISPATCH": Decimal("5.000")},
        )

    def test_transfer_cannot_use_same_movement_receipts_as_source_stock(self):
        self.grant("transfer")
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.TRANSFER,
                [
                    self.line(quantity="5.000", source=self.location, destination=self.other_location),
                    self.line(quantity="5.000", source=self.other_location, destination=self.location),
                ],
            )
        self.assertEqual(InventoryMovement.objects.count(), 0)
        self.assertEqual(StockPosition.objects.count(), 0)

    def test_multi_line_failure_rolls_back_every_line_and_balance(self):
        self.receive("10.000")
        self.grant("release")
        count = InventoryMovement.objects.count()
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.ISSUE,
                [
                    self.line(quantity="6.000", source=self.location),
                    self.line(quantity="5.000", source=self.location),
                ],
            )
        self.assertEqual(InventoryMovement.objects.count(), count)
        self.assertEqual(
            StockPosition.objects.get().on_hand_base_quantity,
            Decimal("10.000"),
        )

    def test_quantities_are_positive_finite_exact_and_limited_to_three_decimals(self):
        self.grant("receive")
        for quantity in ("0", "-1", "NaN", "1.0001", "1E+30"):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.post(
                    InventoryMovement.Type.RECEIPT,
                    [self.line(quantity=quantity, destination=self.location)],
                )
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_movement_line_shape_item_lot_and_active_records_are_validated(self):
        self.grant("receive")
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [self.line(source=self.location, destination=self.other_location)],
            )
        other_product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-INV-003",
            slug="movement-other",
            name="Movement Other",
            base_inventory_unit="seedling",
        )
        other_item = InventoryItem.objects.create(product=other_product, base_unit="seedling")
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [self.line(item=other_item, destination=self.location)],
            )
        self.location.is_active = False
        self.location.save()
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [self.line(destination=self.location)],
            )

    def test_idempotent_retry_returns_same_result_and_changed_input_is_rejected(self):
        self.grant("receive")
        key = uuid.uuid4()
        values = {
            "movement_type": InventoryMovement.Type.RECEIPT,
            "lines": [self.line(destination=self.location)],
            "actor": self.actor,
            "reason": "Idempotent receipt",
            "idempotency_key": key,
        }
        first = post_inventory_movement(**values)
        second = post_inventory_movement(**values)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(InventoryMovement.objects.count(), 1)
        with self.assertRaises(ValidationError):
            post_inventory_movement(**{**values, "reason": "Different"})

        other_actor = get_user_model().objects.create_user(
            username="other-inventory-actor", password=None, is_staff=True
        )
        permission = Permission.objects.get(
            content_type__app_label="inventory", codename="receive"
        )
        other_actor.user_permissions.add(permission)
        with self.assertRaises(ValidationError):
            post_inventory_movement(**{**values, "actor": other_actor})

    def test_malformed_identifiers_are_domain_validation_errors(self):
        self.grant("receive")
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [
                    MovementLineInput(
                        "not-a-uuid", self.lot.pk, Decimal("1.000"), None, self.location.pk
                    )
                ],
            )
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [self.line(destination=self.location)],
                idempotency_key="not-a-uuid",
            )

    def test_source_reference_is_unique_and_both_parts_are_required(self):
        self.grant("receive")
        self.post(
            InventoryMovement.Type.RECEIPT,
            [self.line(destination=self.location)],
            source_type="RECEIPT",
            source_reference="SOURCE-001",
        )
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [self.line(destination=self.other_location)],
                source_type="RECEIPT",
                source_reference="SOURCE-001",
            )
        with self.assertRaises(ValidationError):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [self.line(destination=self.other_location)],
                source_type="RECEIPT",
            )

    def test_permissions_require_active_staff_with_exact_capability(self):
        with self.assertRaises(PermissionDenied):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [self.line(destination=self.location)],
            )
        self.grant("receive")
        self.actor.is_staff = False
        self.actor.save()
        with self.assertRaises(PermissionDenied):
            self.post(
                InventoryMovement.Type.RECEIPT,
                [self.line(destination=self.location)],
            )

    def test_adjustment_and_reversal_posting_remain_unavailable(self):
        self.grant("adjust", "approve_adjustment")
        for movement_type in (
            InventoryMovement.Type.ADJUSTMENT_IN,
            InventoryMovement.Type.ADJUSTMENT_OUT,
            InventoryMovement.Type.REVERSAL,
        ):
            with self.subTest(movement_type=movement_type), self.assertRaises(ValidationError):
                self.post(
                    movement_type,
                    [self.line(destination=self.location)],
                )
        self.assertEqual(InventoryMovement.objects.count(), 0)


class InventoryConstraintTests(InventoryTestCase):
    def test_database_rejects_non_positive_movement_line_quantity(self):
        movement = self.receive()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet(model=InventoryMovementLine, using="default").bulk_create(
                [
                    InventoryMovementLine(
                        movement=movement,
                        line_number=2,
                        item=self.item,
                        lot=self.lot,
                        quantity=0,
                        destination_location=self.location,
                    )
                ]
            )

    def test_position_identity_is_unique(self):
        self.receive()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet(model=StockPosition, using="default").bulk_create(
                [
                    StockPosition(
                        item=self.item,
                        location=self.location,
                        lot=self.lot,
                        on_hand_base_quantity=0,
                    )
                ]
            )


class InventoryAdminAndPermissionTests(InventoryTestCase):
    def test_native_inventory_permissions_exist(self):
        expected = {"view", "receive", "release", "adjust", "approve_adjustment", "transfer"}
        actual = set(
            Permission.objects.filter(content_type__app_label="inventory").values_list(
                "codename", flat=True
            )
        )
        self.assertTrue(expected <= actual)

    def test_admin_is_view_only_and_requires_inventory_view(self):
        self.client.force_login(self.actor)
        url = reverse("admin:inventory_inventoryitem_changelist")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.grant("view")
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin:inventory_inventoryitem_add")).status_code,
            403,
        )
