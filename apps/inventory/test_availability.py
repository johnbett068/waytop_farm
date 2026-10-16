import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from apps.commitments.models import Commitment, CommitmentEvent
from apps.commitments.services import _create_commitment_for_confirmation
from apps.orders.models import Order, OrderLine
from apps.orders.services import ContactInput, OrderLineInput, create_pending_order
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .availability import (
    AvailabilityUnavailable,
    ReadyAvailability,
    ReservationCoverage,
    get_ready_availability,
)
from .models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    StockLot,
    StockPosition,
)
from .services import MovementLineInput, post_inventory_movement


class ReadyAvailabilityTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-AVL-001",
            slug="availability-seedling",
            name="Availability Seedling",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        self.sale_unit = ProductSaleUnit.objects.create(
            product=self.product,
            name="Bundle of 5",
            base_quantity=Decimal("5.000"),
        )
        self.price = ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("100.00"),
            effective_start=timezone.now() - timedelta(days=1),
        )
        self.item = InventoryItem.objects.create(
            product=self.product,
            base_unit="seedling",
        )
        self.location = InventoryLocation.objects.create(code="AVL-A", name="Availability A")
        self.other_location = InventoryLocation.objects.create(
            code="AVL-B", name="Availability B"
        )
        self.lot = StockLot.objects.create(
            item=self.item,
            lot_code="AVL-LOT-A",
            condition=StockLot.Condition.SALEABLE,
            provenance_reference="AVL-RECEIPT-A",
        )
        self.actor = get_user_model().objects.create_user(
            username="availability-actor", password=None, is_staff=True
        )
        for app_label, codename in (
            ("inventory", "receive"),
            ("payments", "verify"),
            ("commitments", "allocate"),
        ):
            self.actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )

    def receive(self, quantity, *, lot=None, location=None):
        lot = lot or self.lot
        location = location or self.location
        return post_inventory_movement(
            movement_type=InventoryMovement.Type.RECEIPT,
            lines=[
                MovementLineInput(
                    item_id=self.item.pk,
                    lot_id=lot.pk,
                    quantity=Decimal(quantity),
                    destination_location_id=location.pk,
                )
            ],
            actor=self.actor,
            reason="Availability test receipt",
            source_type="TEST_RECEIPT",
            source_reference=str(uuid.uuid4()),
            idempotency_key=uuid.uuid4(),
        )

    def availability(self, **overrides):
        values = {"product": self.product, "sale_unit": self.sale_unit}
        values.update(overrides)
        return get_ready_availability(**values)

    def create_commitment_fixture(self):
        order = create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            contact=ContactInput("Availability Buyer", "+254724853914", "buyer@example.com"),
            lines=[
                OrderLineInput(
                    product_id=self.product.pk,
                    sale_unit_id=self.sale_unit.pk,
                    quantity=1,
                    supply_mode=OrderLine.SupplyMode.READY,
                )
            ],
            creation_idempotency_key=uuid.uuid4(),
        )
        with transaction.atomic():
            return _create_commitment_for_confirmation(
                order_line_id=order.lines.get().pk,
                actor=self.actor,
                confirmed_at=timezone.now(),
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="Persistence-only Commitment fixture",
                source_type="TEST_CONFIRMATION_FIXTURE",
                source_reference=order.order_number,
            )


class ReadyAvailabilityCalculationTests(ReadyAvailabilityTestCase):
    def test_empty_inventory_returns_zero_and_exposes_reservation_boundary(self):
        result = self.availability()
        self.assertEqual(result.available_sale_units, 0)
        self.assertEqual(result.reservation_coverage, ReservationCoverage.COMPLETE)
        self.assertIsNotNone(result.calculated_at)

    def test_one_eligible_position_uses_exact_floor_conversion(self):
        self.receive("23.000")
        result = self.availability()
        self.assertEqual(result.available_sale_units, 4)
        self.assertIsInstance(result.available_sale_units, int)

    def test_exact_division_and_stock_smaller_than_one_sale_unit(self):
        self.receive("10.000")
        self.assertEqual(self.availability().available_sale_units, 2)
        other_lot = StockLot.objects.create(
            item=self.item,
            lot_code="AVL-SMALL",
            condition=StockLot.Condition.SALEABLE,
        )
        small_product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-AVL-SMALL",
            slug="availability-small",
            name="Availability Small",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        small_unit = ProductSaleUnit.objects.create(
            product=small_product, name="Bundle", base_quantity=Decimal("5.000")
        )
        small_item = InventoryItem.objects.create(product=small_product, base_unit="seedling")
        small_lot = StockLot.objects.create(
            item=small_item, lot_code="SMALL", condition=StockLot.Condition.SALEABLE
        )
        post_inventory_movement(
            movement_type=InventoryMovement.Type.RECEIPT,
            lines=[
                MovementLineInput(
                    item_id=small_item.pk,
                    lot_id=small_lot.pk,
                    quantity=Decimal("4.999"),
                    destination_location_id=self.location.pk,
                )
            ],
            actor=self.actor,
            reason="Small stock",
            idempotency_key=uuid.uuid4(),
        )
        self.assertEqual(
            get_ready_availability(product=small_product, sale_unit=small_unit).available_sale_units,
            0,
        )
        self.assertEqual(other_lot.positions.count(), 0)

    def test_multiple_locations_aggregate_without_exposing_sources(self):
        self.receive("3.000", location=self.location)
        self.receive("3.000", location=self.other_location)
        result = self.availability()
        self.assertEqual(result.available_sale_units, 1)
        self.assertEqual(
            set(result.__dataclass_fields__),
            {"available_sale_units", "calculated_at", "reservation_coverage"},
        )
        self.assertTrue(
            {
                "location",
                "lot",
                "inventory_item",
                "movement",
                "commitment",
                "fifo_sequence",
                "actor",
                "branch",
            }.isdisjoint(result.__dataclass_fields__)
        )

    def test_multiple_eligible_lots_aggregate(self):
        other_lot = StockLot.objects.create(
            item=self.item,
            lot_code="AVL-LOT-B",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate() + timedelta(days=1),
        )
        self.receive("2.500")
        self.receive("2.500", lot=other_lot)
        self.assertEqual(self.availability().available_sale_units, 1)

    def test_decimal_precision_never_uses_float_or_rounds_up(self):
        decimal_unit = ProductSaleUnit.objects.create(
            product=self.product,
            name="Decimal bundle",
            base_quantity=Decimal("0.300"),
        )
        self.receive("0.899")
        result = self.availability(sale_unit=decimal_unit)
        self.assertEqual(result.available_sale_units, 2)

    def test_multiple_sale_units_and_products_remain_separate(self):
        single = ProductSaleUnit.objects.create(
            product=self.product, name="Single", base_quantity=Decimal("1.000")
        )
        self.receive("10.000")
        self.assertEqual(self.availability().available_sale_units, 2)
        self.assertEqual(self.availability(sale_unit=single).available_sale_units, 10)

        other_product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-AVL-002",
            slug="availability-other",
            name="Availability Other",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        other_unit = ProductSaleUnit.objects.create(
            product=other_product, name="Single", base_quantity=Decimal("1.000")
        )
        InventoryItem.objects.create(product=other_product, base_unit="seedling")
        self.assertEqual(
            get_ready_availability(
                product=other_product, sale_unit=other_unit
            ).available_sale_units,
            0,
        )


class ReadyAvailabilityEligibilityTests(ReadyAvailabilityTestCase):
    def test_ineligible_item_location_and_lot_stock_is_excluded(self):
        restricted_lots = [
            StockLot.objects.create(
                item=self.item,
                lot_code=f"AVL-{condition}",
                condition=condition,
            )
            for condition in (
                StockLot.Condition.HELD,
                StockLot.Condition.QUARANTINED,
                StockLot.Condition.DAMAGED,
                StockLot.Condition.EXPIRED,
            )
        ]
        expired_lot = StockLot.objects.create(
            item=self.item,
            lot_code="AVL-PAST-DATE",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate() - timedelta(days=1),
        )
        inactive_lot = StockLot.objects.create(
            item=self.item,
            lot_code="AVL-INACTIVE",
            condition=StockLot.Condition.SALEABLE,
        )
        blocked_location = InventoryLocation.objects.create(
            code="AVL-BLOCKED", name="Blocked", allows_saleable_stock=False
        )
        inactive_location = InventoryLocation.objects.create(
            code="AVL-INACTIVE", name="Inactive"
        )
        ineligible_sources = [
            *((lot, self.location) for lot in restricted_lots),
            (expired_lot, self.location),
            (inactive_lot, self.location),
            (self.lot, blocked_location),
            (self.lot, inactive_location),
        ]
        for lot, location in ineligible_sources:
            self.receive("10.000", lot=lot, location=location)
        inactive_lot.is_active = False
        inactive_lot.save()
        inactive_location.is_active = False
        inactive_location.save()
        self.assertEqual(self.availability().available_sale_units, 0)

        self.item.is_active = False
        self.item.save()
        self.assertEqual(self.availability().available_sale_units, 0)

    def test_today_expiry_is_eligible_but_past_expiry_is_not(self):
        today_lot = StockLot.objects.create(
            item=self.item,
            lot_code="AVL-TODAY",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate(),
        )
        self.receive("5.000", lot=today_lot)
        self.assertEqual(self.availability().available_sale_units, 1)

    def test_inactive_or_unpublished_catalog_records_are_unavailable(self):
        self.receive("10.000")
        self.product.is_published = False
        self.product.save()
        with self.assertRaises(AvailabilityUnavailable) as caught:
            self.availability()
        self.assertEqual(caught.exception.code, "CATALOG_PRODUCT_UNAVAILABLE")
        self.product.is_published = True
        self.product.save()
        self.sale_unit.is_active = False
        self.sale_unit.save()
        with self.assertRaises(AvailabilityUnavailable) as caught:
            self.availability()
        self.assertEqual(caught.exception.code, "CATALOG_SALE_UNIT_UNAVAILABLE")

    def test_missing_inventory_provider_is_error_not_fabricated_zero(self):
        product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-AVL-NO-INV",
            slug="availability-no-inventory",
            name="No Inventory Provider",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        unit = ProductSaleUnit.objects.create(
            product=product, name="Single", base_quantity=Decimal("1.000")
        )
        with self.assertRaises(AvailabilityUnavailable) as caught:
            get_ready_availability(product=product, sale_unit=unit)
        self.assertEqual(caught.exception.code, "INVENTORY_PROVIDER_UNAVAILABLE")


class ReadyAvailabilityBoundaryTests(ReadyAvailabilityTestCase):
    def test_reservation_provider_cannot_produce_clamped_negative_availability(self):
        class ExcessReservationProvider:
            coverage = ReservationCoverage.COMPLETE

            def active_ready_reserved_base_quantity(self, **kwargs):
                return Decimal("5.001")

        self.receive("5.000")
        with self.assertRaises(AvailabilityUnavailable) as caught:
            self.availability(reservation_provider=ExcessReservationProvider())
        self.assertEqual(caught.exception.code, "RESERVATION_INVARIANT_VIOLATION")

    def test_preorder_availability_is_explicitly_unavailable(self):
        self.receive("10.000")
        with self.assertRaises(AvailabilityUnavailable) as caught:
            self.availability(supply_mode=OrderLine.SupplyMode.PRE_ORDER)
        self.assertEqual(caught.exception.code, "PRE_ORDER_CAPACITY_UNAVAILABLE")

    def test_existing_commitment_is_not_treated_as_reservation(self):
        self.receive("10.000")
        before = self.availability()
        self.create_commitment_fixture()
        after = self.availability()
        self.assertEqual(before.available_sale_units, 2)
        self.assertEqual(after.available_sale_units, 2)
        self.assertEqual(after.reservation_coverage, ReservationCoverage.COMPLETE)

    def test_query_mutates_neither_inventory_nor_commitments(self):
        self.receive("10.000")
        commitment = self.create_commitment_fixture()
        position_before = tuple(
            StockPosition.objects.values_list(
                "pk", "on_hand_base_quantity", "version", "updated_at"
            )
        )
        commitment_before = tuple(
            Commitment.objects.values_list(
                "fifo_sequence",
                "state",
                "supplied_base_quantity",
                "cancelled_base_quantity",
                "outstanding_base_quantity",
            )
        )
        movement_count = InventoryMovement.objects.count()
        event_count = CommitmentEvent.objects.count()
        result = self.availability()
        self.assertIsInstance(result, ReadyAvailability)
        self.assertEqual(
            tuple(
                StockPosition.objects.values_list(
                    "pk", "on_hand_base_quantity", "version", "updated_at"
                )
            ),
            position_before,
        )
        self.assertEqual(
            tuple(
                Commitment.objects.values_list(
                    "fifo_sequence",
                    "state",
                    "supplied_base_quantity",
                    "cancelled_base_quantity",
                    "outstanding_base_quantity",
                )
            ),
            commitment_before,
        )
        self.assertEqual(InventoryMovement.objects.count(), movement_count)
        self.assertEqual(CommitmentEvent.objects.count(), event_count)
        commitment.refresh_from_db()

    def test_result_and_models_introduce_no_branch_or_customer_location(self):
        self.assertTrue(
            {"branch", "customer", "location", "lot"}.isdisjoint(
                ReadyAvailability.__dataclass_fields__
            )
        )
        self.assertEqual(StockPosition.objects.count(), 0)
        self.assertEqual(Commitment.objects.count(), 0)
