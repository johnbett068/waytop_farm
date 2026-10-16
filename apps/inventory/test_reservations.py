import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.commitments.models import Commitment
from apps.commitments.services import _create_commitment_for_confirmation
from apps.orders.models import Order, OrderLine
from apps.orders.services import ContactInput, OrderLineInput, create_pending_order
from apps.payments.models import Payment
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .availability import ReservationCoverage, get_ready_availability
from .models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    Reservation,
    ReservationEvent,
    SourceAllocation,
    SourceAllocationOperation,
    StockLot,
    StockPosition,
)
from .reservations import (
    AllocationSourceInput,
    reallocate_ready_reservation,
    reserve_and_allocate_ready_commitment,
)
from .services import MovementLineInput, post_inventory_movement


class ReservationAllocationTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-RES-001",
            slug="reservation-seedling",
            name="Reservation Seedling",
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
        self.location_a = InventoryLocation.objects.create(code="RES-A", name="Reservation A")
        self.location_b = InventoryLocation.objects.create(code="RES-B", name="Reservation B")
        self.lot_a = StockLot.objects.create(
            item=self.item,
            lot_code="RES-LOT-A",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate() + timedelta(days=10),
        )
        self.lot_b = StockLot.objects.create(
            item=self.item,
            lot_code="RES-LOT-B",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate() + timedelta(days=20),
        )
        self.actor = get_user_model().objects.create_user(
            username="reservation-actor", password=None, is_staff=True
        )
        for app_label, codename in (
            ("inventory", "receive"),
            ("payments", "verify"),
            ("commitments", "allocate"),
            ("commitments", "view"),
        ):
            self.actor.user_permissions.add(
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
            lines=[
                MovementLineInput(
                    item_id=self.item.pk,
                    lot_id=lot.pk,
                    quantity=Decimal(quantity),
                    destination_location_id=location.pk,
                )
            ],
            actor=self.actor,
            reason="Reservation test receipt",
            source_type="TEST_RECEIPT",
            source_reference=str(uuid.uuid4()),
            idempotency_key=uuid.uuid4(),
        )
        return StockPosition.objects.get(item=self.item, lot=lot, location=location)

    def create_commitment(
        self,
        *,
        quantity=1,
        supply_mode=OrderLine.SupplyMode.READY,
        confirmed_at=None,
        order_status=Order.Status.CONFIRMED,
    ):
        required_date = (
            timezone.localdate() + timedelta(days=30)
            if supply_mode == OrderLine.SupplyMode.PRE_ORDER
            else None
        )
        order = create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            contact=ContactInput("Reservation Buyer", "+254724853914", "buyer@example.com"),
            lines=[
                OrderLineInput(
                    product_id=self.product.pk,
                    sale_unit_id=self.sale_unit.pk,
                    quantity=quantity,
                    supply_mode=supply_mode,
                )
            ],
            required_date=required_date,
            creation_idempotency_key=uuid.uuid4(),
        )
        with transaction.atomic():
            commitment = _create_commitment_for_confirmation(
                order_line_id=order.lines.get().pk,
                actor=self.actor,
                confirmed_at=confirmed_at or timezone.now(),
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="Commitment persistence fixture",
                source_type="TEST_CONFIRMATION",
                source_reference=order.order_number,
            )
            if order_status != Order.Status.PENDING:
                models.QuerySet(model=Order, using="default").filter(pk=order.pk).update(
                    status=order_status
                )
        commitment.order.refresh_from_db()
        return commitment

    def reserve(
        self,
        commitment,
        *,
        idempotency_key=None,
        correlation_id=None,
        approved_sources=None,
        reason="Owner-approved complete allocation",
    ):
        with transaction.atomic():
            return reserve_and_allocate_ready_commitment(
                commitment_id=commitment.id,
                actor=self.actor,
                correlation_id=correlation_id or uuid.uuid4(),
                idempotency_key=idempotency_key or uuid.uuid4(),
                reason=reason,
                source_type="ORDER_CONFIRMATION",
                source_reference=commitment.order.order_number,
                approved_sources=approved_sources,
            )


class ReservationPersistenceTests(ReservationAllocationTestCase):
    def test_initial_reservation_history_must_match_creation_identity(self):
        self.receive("10.000")
        commitment = self.create_commitment(quantity=1)
        reservation, _ = self.reserve(commitment)
        invalid_event = ReservationEvent(
            reservation=reservation,
            action=ReservationEvent.Action.CREATED,
            previous_state=None,
            new_state=Reservation.State.ACTIVE,
            base_quantity=reservation.initial_base_quantity,
            actor=self.actor,
            reason="Invalid duplicate creation",
            source_type="TEST",
            source_reference=commitment.order.order_number,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            invalid_event.save(_reservation_service_write=True)

        invalid_operation = SourceAllocationOperation(
            reservation=reservation,
            kind=SourceAllocationOperation.Kind.INITIAL,
            actor=self.actor,
            reason="Invalid duplicate allocation",
            source_type="TEST",
            source_reference=commitment.order.order_number,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            request_fingerprint="0" * 64,
        )
        with self.assertRaises(ValidationError):
            invalid_operation.save(_reservation_service_write=True)

    def test_ready_commitment_creates_one_exact_reservation_and_complete_allocation(self):
        self.receive("10.000")
        commitment = self.create_commitment(quantity=2)
        reservation, allocations = self.reserve(commitment)
        self.assertEqual(commitment.reservation, reservation)
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(reservation.inventory_item, self.item)
        self.assertEqual(reservation.initial_base_quantity, Decimal("10.000"))
        self.assertEqual(reservation.remaining_base_quantity, Decimal("10.000"))
        self.assertEqual(reservation.state, Reservation.State.ACTIVE)
        self.assertEqual(sum(a.initial_base_quantity for a in allocations), Decimal("10.000"))
        self.assertEqual(reservation.events.get().action, ReservationEvent.Action.CREATED)

    def test_preorder_commitment_and_pending_order_are_rejected(self):
        self.receive("20.000")
        preorder = self.create_commitment(supply_mode=OrderLine.SupplyMode.PRE_ORDER)
        with self.assertRaises(ValidationError):
            self.reserve(preorder)
        pending = self.create_commitment(order_status=Order.Status.PENDING)
        with self.assertRaises(ValidationError):
            self.reserve(pending)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_insufficient_stock_rolls_back_reservation_allocation_and_audit(self):
        self.receive("4.999")
        commitment = self.create_commitment()
        with self.assertRaises(ValidationError):
            self.reserve(commitment)
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertEqual(SourceAllocation.objects.count(), 0)
        self.assertEqual(SourceAllocationOperation.objects.count(), 0)
        self.assertEqual(ReservationEvent.objects.count(), 0)

    def test_reservation_does_not_reduce_on_hand_but_reduces_ready_availability(self):
        position = self.receive("10.000")
        before = get_ready_availability(product=self.product, sale_unit=self.sale_unit)
        commitment = self.create_commitment()
        movement_count = InventoryMovement.objects.count()
        version = position.version
        self.reserve(commitment)
        after = get_ready_availability(product=self.product, sale_unit=self.sale_unit)
        position.refresh_from_db()
        self.assertEqual(position.on_hand_base_quantity, Decimal("10.000"))
        self.assertEqual(position.version, version)
        self.assertEqual(InventoryMovement.objects.count(), movement_count)
        self.assertEqual(before.available_sale_units, 2)
        self.assertEqual(after.available_sale_units, 1)
        self.assertEqual(after.reservation_coverage, ReservationCoverage.COMPLETE)

    def test_reservation_identity_quantity_and_commitment_are_not_mutable(self):
        self.receive("10.000")
        first = self.create_commitment()
        reservation, _ = self.reserve(first)
        second = self.create_commitment(confirmed_at=timezone.now() + timedelta(seconds=1))
        reservation.commitment = second
        reservation.initial_base_quantity = Decimal("4.000")
        with self.assertRaises(ValidationError):
            reservation.save(_reservation_service_write=True)
        with self.assertRaises(ValidationError):
            Reservation.objects.update(remaining_base_quantity=Decimal("1.000"))

    def test_database_enforces_reservation_quantity_equation_and_non_negative_values(self):
        self.receive("10.000")
        reservation, _ = self.reserve(self.create_commitment())
        unsafe = models.QuerySet(model=Reservation, using="default").filter(pk=reservation.pk)
        for values in (
            {"remaining_base_quantity": Decimal("4.000")},
            {
                "consumed_base_quantity": Decimal("-1.000"),
                "remaining_base_quantity": Decimal("6.000"),
            },
        ):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                unsafe.update(**values)

    def test_identical_retry_creates_no_duplicate_reservation_allocation_or_history(self):
        self.receive("10.000")
        commitment = self.create_commitment()
        key = uuid.uuid4()
        correlation = uuid.uuid4()
        first_reservation, first_lines = self.reserve(
            commitment,
            idempotency_key=key,
            correlation_id=correlation,
        )
        second_reservation, second_lines = self.reserve(
            commitment,
            idempotency_key=key,
            correlation_id=correlation,
        )
        self.assertEqual(first_reservation.pk, second_reservation.pk)
        self.assertEqual([line.pk for line in first_lines], [line.pk for line in second_lines])
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(SourceAllocation.objects.count(), len(first_lines))
        self.assertEqual(ReservationEvent.objects.count(), 1)
        self.assertEqual(SourceAllocationOperation.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.reserve(
                commitment,
                idempotency_key=key,
                correlation_id=correlation,
                reason="Changed request",
            )


class SourceAllocationTests(ReservationAllocationTestCase):
    def test_allocation_uses_position_item_location_lot_and_exact_base_quantity(self):
        position = self.receive("5.000")
        reservation, allocations = self.reserve(self.create_commitment())
        allocation = allocations[0]
        self.assertEqual(allocation.reservation, reservation)
        self.assertEqual(allocation.stock_position, position)
        self.assertEqual(allocation.stock_position.item, self.item)
        self.assertEqual(allocation.stock_position.location, self.location_a)
        self.assertEqual(allocation.stock_position.lot, self.lot_a)
        self.assertEqual(allocation.initial_base_quantity, Decimal("5.000"))
        self.assertEqual(allocation.remaining_base_quantity, Decimal("5.000"))

    def test_complete_allocation_can_split_across_locations_and_lots(self):
        first = self.receive("3.000", lot=self.lot_a, location=self.location_a)
        second = self.receive("4.000", lot=self.lot_b, location=self.location_b)
        reservation, allocations = self.reserve(
            self.create_commitment(quantity=1),
            approved_sources=(
                AllocationSourceInput(first.pk, Decimal("2.000")),
                AllocationSourceInput(second.pk, Decimal("3.000")),
            ),
        )
        self.assertEqual(len(allocations), 2)
        self.assertEqual(
            {allocation.stock_position_id for allocation in allocations},
            {first.pk, second.pk},
        )
        self.assertEqual(
            sum(a.remaining_base_quantity for a in allocations),
            reservation.remaining_base_quantity,
        )

    def test_partial_excess_duplicate_and_ineligible_approved_splits_are_rejected(self):
        eligible = self.receive("10.000")
        held_lot = StockLot.objects.create(
            item=self.item, lot_code="RES-HELD", condition=StockLot.Condition.HELD
        )
        ineligible = self.receive("10.000", lot=held_lot)
        cases = (
            (AllocationSourceInput(eligible.pk, Decimal("4.000")),),
            (AllocationSourceInput(eligible.pk, Decimal("6.000")),),
            (
                AllocationSourceInput(eligible.pk, Decimal("2.000")),
                AllocationSourceInput(eligible.pk, Decimal("3.000")),
            ),
            (AllocationSourceInput(ineligible.pk, Decimal("5.000")),),
        )
        commitment = self.create_commitment()
        for split in cases:
            with self.subTest(split=split), self.assertRaises(ValidationError):
                self.reserve(commitment, approved_sources=split)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_same_position_stock_cannot_be_allocated_twice(self):
        self.receive("5.000")
        first = self.create_commitment(confirmed_at=timezone.now())
        second = self.create_commitment(confirmed_at=timezone.now() + timedelta(seconds=1))
        self.reserve(first)
        with self.assertRaises(ValidationError):
            self.reserve(second)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_deterministic_source_order_uses_expiry_then_lot_creation_location_and_id(self):
        null_expiry = StockLot.objects.create(
            item=self.item,
            lot_code="RES-NULL",
            condition=StockLot.Condition.SALEABLE,
        )
        earliest = StockLot.objects.create(
            item=self.item,
            lot_code="RES-EARLIEST",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate() + timedelta(days=1),
        )
        later = StockLot.objects.create(
            item=self.item,
            lot_code="RES-LATER",
            condition=StockLot.Condition.SALEABLE,
            expiry_date=timezone.localdate() + timedelta(days=2),
        )
        null_position = self.receive("5.000", lot=null_expiry, location=self.location_a)
        earliest_position = self.receive("5.000", lot=earliest, location=self.location_b)
        later_position = self.receive("5.000", lot=later, location=self.location_a)
        _, allocations = self.reserve(self.create_commitment(quantity=2))
        self.assertEqual(
            [allocation.stock_position_id for allocation in allocations],
            [earliest_position.pk, later_position.pk],
        )
        self.assertNotIn(null_position.pk, [a.stock_position_id for a in allocations])

    def test_fifo_prevents_later_commitment_bypass(self):
        self.receive("10.000")
        at = timezone.now()
        earlier = self.create_commitment(confirmed_at=at)
        later = self.create_commitment(confirmed_at=at + timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            self.reserve(later)
        self.reserve(earlier)
        self.reserve(later)
        self.assertEqual(Reservation.objects.count(), 2)

    def test_fifo_tie_uses_existing_database_sequence_and_has_no_override(self):
        self.receive("10.000")
        at = timezone.now()
        first = self.create_commitment(confirmed_at=at)
        second = self.create_commitment(confirmed_at=at)
        self.assertLess(first.fifo_sequence, second.fifo_sequence)
        with self.assertRaises(ValidationError):
            self.reserve(second)
        self.reserve(first)
        fields = {field.name for field in SourceAllocation._meta.get_fields()}
        self.assertTrue({"priority", "fifo_override", "manual_priority"}.isdisjoint(fields))

    def test_reallocation_releases_old_lines_appends_new_lines_and_is_idempotent(self):
        first = self.receive("5.000", lot=self.lot_a, location=self.location_a)
        second = self.receive("5.000", lot=self.lot_b, location=self.location_b)
        reservation, old_lines = self.reserve(
            self.create_commitment(),
            approved_sources=(AllocationSourceInput(first.pk, Decimal("5.000")),),
        )
        key = uuid.uuid4()
        correlation = uuid.uuid4()
        with transaction.atomic():
            new_lines = reallocate_ready_reservation(
                reservation_id=reservation.pk,
                actor=self.actor,
                correlation_id=correlation,
                idempotency_key=key,
                reason="Owner-approved source change",
                source_type="REALLOCATION",
                source_reference=reservation.commitment.order.order_number,
                approved_sources=(AllocationSourceInput(second.pk, Decimal("5.000")),),
            )
        old_lines[0].refresh_from_db()
        self.assertEqual(old_lines[0].remaining_base_quantity, Decimal("0.000"))
        self.assertEqual(old_lines[0].released_base_quantity, Decimal("5.000"))
        self.assertIsNotNone(old_lines[0].released_by_operation_id)
        self.assertEqual(new_lines[0].stock_position_id, second.pk)
        self.assertEqual(SourceAllocation.objects.count(), 2)
        self.assertEqual(SourceAllocationOperation.objects.count(), 2)
        with transaction.atomic():
            retried = reallocate_ready_reservation(
                reservation_id=reservation.pk,
                actor=self.actor,
                correlation_id=correlation,
                idempotency_key=key,
                reason="Owner-approved source change",
                source_type="REALLOCATION",
                source_reference=reservation.commitment.order.order_number,
                approved_sources=(AllocationSourceInput(second.pk, Decimal("5.000")),),
            )
        self.assertEqual([line.pk for line in retried], [line.pk for line in new_lines])
        self.assertEqual(SourceAllocation.objects.count(), 2)


class ReservationBoundaryAndAdminTests(ReservationAllocationTestCase):
    def test_allocate_permission_is_required_without_role_name_assumptions(self):
        self.receive("5.000")
        commitment = self.create_commitment()
        permission = Permission.objects.get(
            content_type__app_label="commitments", codename="allocate"
        )
        self.actor.user_permissions.remove(permission)
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            self.actor.__dict__.pop(cache_name, None)
        self.actor.username = "owner"
        self.actor.save()
        with self.assertRaises(PermissionDenied):
            self.reserve(commitment)

    def test_admin_is_commitment_view_controlled_and_read_only(self):
        self.receive("5.000")
        reservation, _ = self.reserve(self.create_commitment())
        self.client.force_login(self.actor)
        list_url = reverse("admin:inventory_reservation_changelist")
        self.assertEqual(self.client.get(list_url).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin:inventory_reservation_add")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("admin:inventory_reservation_change", args=(reservation.pk,))
            ).status_code,
            200,
        )

    def test_no_order_payment_inventory_or_customer_visible_mutation_is_introduced(self):
        position = self.receive("5.000")
        commitment = self.create_commitment()
        order_status = commitment.order.status
        payment_state = commitment.order.payment.state
        movement_count = InventoryMovement.objects.count()
        self.reserve(commitment)
        commitment.order.refresh_from_db()
        commitment.order.payment.refresh_from_db()
        position.refresh_from_db()
        self.assertEqual(commitment.order.status, order_status)
        self.assertEqual(commitment.order.payment.state, payment_state)
        self.assertEqual(position.on_hand_base_quantity, Decimal("5.000"))
        self.assertEqual(InventoryMovement.objects.count(), movement_count)
        fields = {field.name for field in Reservation._meta.get_fields()}
        self.assertTrue({"branch", "customer", "expiry", "production"}.isdisjoint(fields))
        import apps.inventory.reservations as reservation_services

        self.assertFalse(hasattr(reservation_services, "cancel_order"))
        self.assertFalse(hasattr(reservation_services, "confirm_order"))
        self.assertFalse(hasattr(reservation_services, "verify_payment"))
        self.assertEqual(Payment.objects.filter(state=Payment.State.CONFIRMED).count(), 0)

    def test_no_demo_reservations_allocations_or_stock_exist(self):
        self.assertEqual(Reservation.objects.count(), 0)
        self.assertEqual(SourceAllocation.objects.count(), 0)
        self.assertEqual(StockPosition.objects.count(), 0)


class ReservationOuterTransactionTests(TransactionTestCase):
    def test_initial_and_reallocation_services_require_outer_transaction(self):
        with self.assertRaises(ValidationError):
            reserve_and_allocate_ready_commitment(
                commitment_id=uuid.uuid4(),
                actor=None,
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="test",
                source_type="test",
                source_reference="test",
            )
        with self.assertRaises(ValidationError):
            reallocate_ready_reservation(
                reservation_id=uuid.uuid4(),
                actor=None,
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="test",
                source_type="test",
                source_reference="test",
            )
