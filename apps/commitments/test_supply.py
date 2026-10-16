import inspect
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.test import TestCase
from django.utils import timezone

from apps.inventory.availability import get_ready_availability
from apps.inventory.models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    Reservation,
    ReservationEvent,
    SourceAllocation,
    SourceAllocationConsumption,
    SourceAllocationOperation,
    StockLot,
    StockPosition,
)
from apps.inventory.reservations import (
    AllocationSourceInput,
    reserve_and_allocate_ready_commitment,
)
from apps.inventory.services import MovementLineInput, post_inventory_movement
from apps.orders.models import Order, OrderLine
from apps.orders.services import ContactInput, OrderLineInput, create_pending_order
from apps.payments.models import Payment
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .models import Commitment, CommitmentSupplyEvent
from .services import _create_commitment_for_confirmation
from .supply import supply_ready_commitment


class SupplyTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-SUP-001",
            slug="supply-seedling",
            name="Supply Seedling",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        self.sale_unit = ProductSaleUnit.objects.create(
            product=self.product,
            name="Bundle of 5",
            base_quantity=Decimal("5.000"),
        )
        ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("100.00"),
            effective_start=timezone.now() - timedelta(days=1),
        )
        self.item = InventoryItem.objects.create(product=self.product, base_unit="seedling")
        self.location_a = InventoryLocation.objects.create(code="SUP-A", name="Supply A")
        self.location_b = InventoryLocation.objects.create(code="SUP-B", name="Supply B")
        self.lot_a = StockLot.objects.create(
            item=self.item,
            lot_code="SUP-LOT-A",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate() + timedelta(days=10),
        )
        self.lot_b = StockLot.objects.create(
            item=self.item,
            lot_code="SUP-LOT-B",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate() + timedelta(days=20),
        )
        self.actor = get_user_model().objects.create_user(
            username="supply-actor", password=None, is_staff=True
        )
        self.grant(
            self.actor,
            "inventory.receive",
            "inventory.release",
            "payments.verify",
            "commitments.allocate",
            "commitments.view",
        )

    def grant(self, actor, *permissions):
        for permission_name in permissions:
            app_label, codename = permission_name.split(".", 1)
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )

    def receive(self, quantity, *, lot=None, location=None):
        lot = lot or self.lot_a
        location = location or self.location_a
        post_inventory_movement(
            movement_type=InventoryMovement.Type.RECEIPT,
            lines=(
                MovementLineInput(
                    item_id=self.item.pk,
                    lot_id=lot.pk,
                    quantity=Decimal(quantity),
                    destination_location_id=location.pk,
                ),
            ),
            actor=self.actor,
            reason="Supply test receipt",
            source_type="TEST_RECEIPT",
            source_reference=str(uuid.uuid4()),
            idempotency_key=uuid.uuid4(),
        )
        return StockPosition.objects.get(item=self.item, lot=lot, location=location)

    def create_commitment(self, *, quantity=2, supply_mode=OrderLine.SupplyMode.READY):
        order = create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            contact=ContactInput("Supply Buyer", "+254724853915", "supply@example.com"),
            lines=(
                OrderLineInput(
                    product_id=self.product.pk,
                    sale_unit_id=self.sale_unit.pk,
                    quantity=quantity,
                    supply_mode=supply_mode,
                ),
            ),
            required_date=(
                timezone.localdate() + timedelta(days=30)
                if supply_mode == OrderLine.SupplyMode.PRE_ORDER
                else None
            ),
            creation_idempotency_key=uuid.uuid4(),
        )
        with transaction.atomic():
            commitment = _create_commitment_for_confirmation(
                order_line_id=order.lines.get().pk,
                actor=self.actor,
                confirmed_at=timezone.now(),
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="Supply commitment fixture",
                source_type="TEST_CONFIRMATION",
                source_reference=order.order_number,
            )
            models.QuerySet(model=Order, using="default").filter(pk=order.pk).update(
                status=Order.Status.PROCESSING
            )
            models.QuerySet(model=OrderLine, using="default").filter(order=order).update(
                confirmed_quantity=quantity,
                outstanding_quantity=quantity,
            )
        commitment.order.refresh_from_db()
        return commitment

    def reserve(self, commitment, *, approved_sources=None):
        with transaction.atomic():
            return reserve_and_allocate_ready_commitment(
                commitment_id=commitment.id,
                actor=self.actor,
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="Supply fixture allocation",
                source_type="TEST_CONFIRMATION",
                source_reference=commitment.order.order_number,
                approved_sources=approved_sources,
            )

    def supply(
        self,
        commitment,
        quantity=1,
        *,
        actor=None,
        correlation_id=None,
        idempotency_key=None,
        reason="Physical handoff",
    ):
        return supply_ready_commitment(
            commitment_id=commitment.id,
            commercial_quantity=quantity,
            actor=actor or self.actor,
            correlation_id=correlation_id or uuid.uuid4(),
            idempotency_key=idempotency_key or uuid.uuid4(),
            reason=reason,
            source_type="FULFILLMENT_HANDOFF",
            source_reference=str(uuid.uuid4()),
        )


class SupplyQuantityAndLifecycleTests(SupplyTestCase):
    def test_partial_supply_creates_exact_append_only_event_and_updates_all_ledgers(self):
        position = self.receive("10.000")
        commitment = self.create_commitment(quantity=2)
        reservation, allocations = self.reserve(commitment)
        event = self.supply(commitment, 1)

        commitment.refresh_from_db()
        reservation.refresh_from_db()
        allocations[0].refresh_from_db()
        position.refresh_from_db()
        self.assertEqual(event.commercial_quantity, 1)
        self.assertEqual(event.base_quantity, Decimal("5.000"))
        self.assertEqual(event.inventory_movement.movement_type, InventoryMovement.Type.ISSUE)
        self.assertEqual(commitment.supplied_quantity, 1)
        self.assertEqual(commitment.supplied_base_quantity, Decimal("5.000"))
        self.assertEqual(commitment.outstanding_quantity, 1)
        self.assertEqual(commitment.outstanding_base_quantity, Decimal("5.000"))
        self.assertEqual(commitment.state, Commitment.State.ACTIVE)
        self.assertEqual(reservation.consumed_base_quantity, Decimal("5.000"))
        self.assertEqual(reservation.remaining_base_quantity, Decimal("5.000"))
        self.assertEqual(reservation.state, Reservation.State.ACTIVE)
        self.assertEqual(allocations[0].consumed_base_quantity, Decimal("5.000"))
        self.assertEqual(allocations[0].remaining_base_quantity, Decimal("5.000"))
        self.assertEqual(position.on_hand_base_quantity, Decimal("5.000"))
        self.assertEqual(
            commitment.committed_quantity,
            commitment.supplied_quantity
            + commitment.cancelled_quantity
            + commitment.outstanding_quantity,
        )
        self.assertEqual(
            reservation.initial_base_quantity,
            reservation.consumed_base_quantity
            + reservation.released_base_quantity
            + reservation.remaining_base_quantity,
        )
        with self.assertRaises(ValidationError):
            event.delete()
        event.reason = "rewrite"
        with self.assertRaises(ValidationError):
            event.save(_commitment_service_write=True)

    def test_full_supply_consumes_reservation_and_satisfies_commitment(self):
        self.receive("10.000")
        commitment = self.create_commitment(quantity=2)
        reservation, _ = self.reserve(commitment)
        event = self.supply(commitment, 2)
        commitment.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(event.previous_state, Commitment.State.ACTIVE)
        self.assertEqual(event.new_state, Commitment.State.SATISFIED)
        self.assertEqual(commitment.state, Commitment.State.SATISFIED)
        self.assertEqual(commitment.outstanding_quantity, 0)
        self.assertEqual(reservation.state, Reservation.State.CONSUMED)
        self.assertEqual(reservation.remaining_base_quantity, Decimal("0.000"))
        self.assertEqual(reservation.consumed_base_quantity, Decimal("10.000"))
        reservation_event = ReservationEvent.objects.get(
            reservation=reservation, action=ReservationEvent.Action.CONSUMED
        )
        self.assertEqual(reservation_event.new_state, Reservation.State.CONSUMED)

    def test_zero_negative_and_excess_commercial_supply_are_rejected(self):
        self.receive("10.000")
        commitment = self.create_commitment(quantity=2)
        self.reserve(commitment)
        for quantity in (0, -1, 3, Decimal("0.5"), True):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.supply(commitment, quantity)
        self.assertEqual(CommitmentSupplyEvent.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="ISSUE").count(), 0)

    def test_caller_cannot_supply_base_quantity_or_choose_allocation_split(self):
        parameters = inspect.signature(supply_ready_commitment).parameters
        self.assertNotIn("base_quantity", parameters)
        self.assertNotIn("allocations", parameters)
        self.assertNotIn("approved_sources", parameters)

    def test_released_reservation_cannot_be_consumed(self):
        self.receive("5.000")
        commitment = self.create_commitment(quantity=1)
        reservation, allocations = self.reserve(commitment)
        models.QuerySet(model=SourceAllocation, using="default").filter(
            pk=allocations[0].pk
        ).update(
            released_base_quantity=Decimal("5.000"),
            remaining_base_quantity=Decimal("0.000"),
        )
        models.QuerySet(model=Reservation, using="default").filter(pk=reservation.pk).update(
            state=Reservation.State.RELEASED,
            released_base_quantity=Decimal("5.000"),
            remaining_base_quantity=Decimal("0.000"),
        )
        with self.assertRaises(ValidationError):
            self.supply(commitment)
        self.assertEqual(CommitmentSupplyEvent.objects.count(), 0)


class MultiSourceSupplyTests(SupplyTestCase):
    def test_consumes_allocations_in_creation_order_and_crosses_sources(self):
        first_position = self.receive("4.000", lot=self.lot_a, location=self.location_a)
        second_position = self.receive("6.000", lot=self.lot_b, location=self.location_b)
        commitment = self.create_commitment(quantity=2)
        _, allocations = self.reserve(
            commitment,
            approved_sources=(
                AllocationSourceInput(first_position.pk, Decimal("4.000")),
                AllocationSourceInput(second_position.pk, Decimal("6.000")),
            ),
        )
        event = self.supply(commitment, 1)
        consumption = list(event.allocation_consumptions.order_by("line_number"))
        self.assertEqual(
            [(line.allocation_id, line.base_quantity) for line in consumption],
            [
                (allocations[0].pk, Decimal("4.000")),
                (allocations[1].pk, Decimal("1.000")),
            ],
        )
        allocations[0].refresh_from_db()
        allocations[1].refresh_from_db()
        self.assertEqual(allocations[0].remaining_base_quantity, Decimal("0.000"))
        self.assertEqual(allocations[1].remaining_base_quantity, Decimal("5.000"))
        self.assertEqual(SourceAllocation.objects.count(), 2)
        self.assertEqual(
            SourceAllocationOperation.objects.filter(
                kind=SourceAllocationOperation.Kind.CONSUMPTION
            ).count(),
            1,
        )

    def test_allocation_uuid_breaks_equal_creation_time_tie(self):
        first_position = self.receive("5.000", lot=self.lot_a, location=self.location_a)
        second_position = self.receive("5.000", lot=self.lot_b, location=self.location_b)
        commitment = self.create_commitment(quantity=2)
        _, allocations = self.reserve(
            commitment,
            approved_sources=(
                AllocationSourceInput(first_position.pk, Decimal("5.000")),
                AllocationSourceInput(second_position.pk, Decimal("5.000")),
            ),
        )
        same_time = timezone.now()
        models.QuerySet(model=SourceAllocation, using="default").filter(
            pk__in=[allocation.pk for allocation in allocations]
        ).update(created_at=same_time)
        expected = min(allocations, key=lambda allocation: str(allocation.pk))
        event = self.supply(commitment, 1)
        consumption = event.allocation_consumptions.get()
        self.assertEqual(consumption.allocation_id, expected.pk)
        self.assertEqual(consumption.base_quantity, Decimal("5.000"))

    def test_ineligible_aggregate_allocation_rejects_before_any_mutation(self):
        first_position = self.receive("4.000", lot=self.lot_a, location=self.location_a)
        second_position = self.receive("6.000", lot=self.lot_b, location=self.location_b)
        commitment = self.create_commitment(quantity=2)
        reservation, _ = self.reserve(
            commitment,
            approved_sources=(
                AllocationSourceInput(first_position.pk, Decimal("4.000")),
                AllocationSourceInput(second_position.pk, Decimal("6.000")),
            ),
        )
        models.QuerySet(model=StockLot, using="default").filter(pk=self.lot_a.pk).update(
            condition=StockLot.Condition.HELD
        )
        with self.assertRaises(ValidationError):
            self.supply(commitment, 2)
        commitment.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(commitment.supplied_quantity, 0)
        self.assertEqual(reservation.consumed_base_quantity, Decimal("0.000"))
        self.assertEqual(CommitmentSupplyEvent.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="ISSUE").count(), 0)
        self.assertEqual(SourceAllocationConsumption.objects.count(), 0)

    def test_insufficient_physical_position_rejects_without_ledger_consumption(self):
        position = self.receive("10.000")
        commitment = self.create_commitment(quantity=2)
        reservation, allocations = self.reserve(commitment)
        post_inventory_movement(
            movement_type=InventoryMovement.Type.ISSUE,
            lines=(
                MovementLineInput(
                    item_id=self.item.pk,
                    lot_id=self.lot_a.pk,
                    quantity=Decimal("7.000"),
                    source_location_id=self.location_a.pk,
                ),
            ),
            actor=self.actor,
            reason="Test external issue",
            source_type="TEST_ISSUE",
            source_reference=str(uuid.uuid4()),
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            self.supply(commitment, 1)
        commitment.refresh_from_db()
        reservation.refresh_from_db()
        allocations[0].refresh_from_db()
        position.refresh_from_db()
        self.assertEqual(position.on_hand_base_quantity, Decimal("3.000"))
        self.assertEqual(commitment.supplied_quantity, 0)
        self.assertEqual(reservation.consumed_base_quantity, Decimal("0.000"))
        self.assertEqual(allocations[0].consumed_base_quantity, Decimal("0.000"))
        self.assertEqual(CommitmentSupplyEvent.objects.count(), 0)


class SupplyIdempotencyAndBoundaryTests(SupplyTestCase):
    def test_identical_retry_returns_one_complete_supply_effect_and_changed_retry_rejects(self):
        position = self.receive("10.000")
        commitment = self.create_commitment(quantity=2)
        reservation, allocations = self.reserve(commitment)
        key = uuid.uuid4()
        correlation = uuid.uuid4()
        reference = str(uuid.uuid4())
        kwargs = dict(
            commitment_id=commitment.id,
            commercial_quantity=1,
            actor=self.actor,
            correlation_id=correlation,
            idempotency_key=key,
            reason="Idempotent supply",
            source_type="FULFILLMENT_HANDOFF",
            source_reference=reference,
        )
        first = supply_ready_commitment(**kwargs)
        second = supply_ready_commitment(**kwargs)
        self.assertEqual(first.pk, second.pk)
        commitment.refresh_from_db()
        reservation.refresh_from_db()
        allocations[0].refresh_from_db()
        position.refresh_from_db()
        self.assertEqual(CommitmentSupplyEvent.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="ISSUE").count(), 1)
        self.assertEqual(SourceAllocationConsumption.objects.count(), 1)
        self.assertEqual(
            ReservationEvent.objects.filter(action=ReservationEvent.Action.CONSUMED).count(), 1
        )
        self.assertEqual(commitment.supplied_quantity, 1)
        self.assertEqual(reservation.consumed_base_quantity, Decimal("5.000"))
        self.assertEqual(allocations[0].consumed_base_quantity, Decimal("5.000"))
        self.assertEqual(position.on_hand_base_quantity, Decimal("5.000"))
        with self.assertRaises(ValidationError):
            supply_ready_commitment(**{**kwargs, "reason": "Changed retry"})

    def test_preorder_rejects_before_inventory_or_commitment_mutation(self):
        commitment = self.create_commitment(
            quantity=1, supply_mode=OrderLine.SupplyMode.PRE_ORDER
        )
        with self.assertRaises(ValidationError):
            self.supply(commitment)
        commitment.refresh_from_db()
        self.assertEqual(commitment.supplied_quantity, 0)
        self.assertEqual(CommitmentSupplyEvent.objects.count(), 0)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="ISSUE").count(), 0)

    def test_order_payment_and_availability_semantics_remain_unchanged(self):
        self.receive("15.000")
        commitment = self.create_commitment(quantity=2)
        reservation, _ = self.reserve(commitment)
        order_state = commitment.order.status
        payment_state = commitment.order.payment.state
        before = get_ready_availability(product=self.product, sale_unit=self.sale_unit)
        self.supply(commitment, 1)
        commitment.order.refresh_from_db()
        commitment.order.payment.refresh_from_db()
        reservation.refresh_from_db()
        after = get_ready_availability(product=self.product, sale_unit=self.sale_unit)
        self.assertEqual(commitment.order.status, order_state)
        self.assertEqual(commitment.order.payment.state, payment_state)
        self.assertEqual(payment_state, Payment.State.PENDING)
        self.assertEqual(after.available_sale_units, before.available_sale_units)

    def test_no_confirmation_production_or_customer_source_surface_is_added(self):
        import apps.commitments.supply as supply_module

        self.assertFalse(hasattr(supply_module, "confirm_order"))
        self.assertFalse(hasattr(supply_module, "verify_payment"))
        self.assertFalse(hasattr(supply_module, "production_capacity"))
        fields = set(inspect.signature(supply_ready_commitment).parameters)
        self.assertTrue({"location", "lot", "allocation"}.isdisjoint(fields))


class SupplyAuthorizationTests(SupplyTestCase):
    def setUp(self):
        super().setUp()
        self.receive("20.000")

    def _candidate(self):
        commitment = self.create_commitment(quantity=1)
        self.reserve(commitment)
        return commitment

    def test_anonymous_inactive_and_unauthorized_staff_are_rejected(self):
        inactive = get_user_model().objects.create_user(
            username="inactive-supplier", is_staff=True, is_active=False
        )
        self.grant(inactive, "inventory.release")
        unauthorized = get_user_model().objects.create_user(
            username="unauthorized-supplier", is_staff=True
        )
        for actor in (None, inactive, unauthorized):
            commitment = self._candidate()
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                supply_ready_commitment(
                    commitment_id=commitment.id,
                    commercial_quantity=1,
                    actor=actor,
                    correlation_id=uuid.uuid4(),
                    idempotency_key=uuid.uuid4(),
                    reason="Authorization test",
                    source_type="TEST",
                    source_reference=str(uuid.uuid4()),
                )

    def test_inventory_release_staff_and_django_superuser_succeed(self):
        authorized = get_user_model().objects.create_user(
            username="authorized-supplier", is_staff=True
        )
        self.grant(authorized, "inventory.release")
        superuser = get_user_model().objects.create_superuser(
            username="supply-superuser", password=None
        )
        first = self._candidate()
        second = self._candidate()
        self.assertIsNotNone(self.supply(first, actor=authorized).pk)
        self.assertIsNotNone(self.supply(second, actor=superuser).pk)
