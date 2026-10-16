import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.commitments.models import Commitment, CommitmentEvent
from apps.commitments.supply import supply_ready_commitment
from apps.fulfillment.models import FulfillmentCompletion
from apps.fulfillment.services import complete_order_fulfillment
from apps.inventory.availability import get_ready_availability
from apps.inventory.models import (
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
from apps.inventory.services import MovementLineInput, post_inventory_movement
from apps.orders.models import Order, OrderLine, OrderStatusEvent
from apps.orders.services import (
    ContactInput,
    OrderLineInput,
    cancel_ready_order,
    create_pending_order,
    start_order_processing,
)
from apps.payments.models import Payment, PaymentEvidence
from apps.payments.services import submit_payment_evidence, verify_payment_and_confirm_order
from apps.products.models import Product, ProductPrice, ProductSaleUnit


class ReadyLifecycleTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-G-001",
            slug="phase-g-product",
            name="Phase G Product",
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
        self.location = InventoryLocation.objects.create(code="G-MAIN", name="Phase G Main")
        self.lot = StockLot.objects.create(
            item=self.item,
            lot_code="G-LOT-1",
            condition=StockLot.Condition.SALEABLE,
        )
        self.actor = get_user_model().objects.create_user(
            username="phase-g-actor", password=None, is_staff=True
        )
        self.grant(
            self.actor,
            "inventory.receive",
            "inventory.release",
            "payments.verify",
            "commitments.allocate",
            "orders.cancel",
            "orders.process",
            "fulfillment.complete",
        )
        post_inventory_movement(
            movement_type=InventoryMovement.Type.RECEIPT,
            lines=(
                MovementLineInput(
                    item_id=self.item.pk,
                    lot_id=self.lot.pk,
                    quantity=Decimal("100.000"),
                    destination_location_id=self.location.pk,
                ),
            ),
            actor=self.actor,
            reason="Phase G stock",
            source_type="TEST_RECEIPT",
            source_reference="PHASE-G-STOCK",
            idempotency_key=uuid.uuid4(),
        )

    def grant(self, actor, *permission_names):
        for permission_name in permission_names:
            app_label, codename = permission_name.split(".", 1)
            actor.user_permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
        self.clear_permissions(actor)

    def revoke(self, actor, permission_name):
        app_label, codename = permission_name.split(".", 1)
        actor.user_permissions.remove(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
        self.clear_permissions(actor)

    @staticmethod
    def clear_permissions(actor):
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            actor.__dict__.pop(cache_name, None)

    def create_confirmed_order(self, quantity=3):
        order = create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            lines=(
                OrderLineInput(
                    product_id=self.product.pk,
                    sale_unit_id=self.sale_unit.pk,
                    quantity=quantity,
                    supply_mode=OrderLine.SupplyMode.READY,
                ),
            ),
            creation_idempotency_key=uuid.uuid4(),
            contact=ContactInput("Phase G Buyer", "+254724853914", "buyer@example.com"),
        )
        evidence = submit_payment_evidence(
            payment=order.payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim=f"G{uuid.uuid4().hex[:10]}",
        )
        return verify_payment_and_confirm_order(
            order_id=order.pk,
            payment_id=order.payment.pk,
            evidence_id=evidence.pk,
            provider_reference=evidence.reference_claim,
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Phase G staff verification",
        )

    def make_processing(self, order):
        start_order_processing(
            order_id=order.pk,
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Start test fulfillment work",
        )
        order.refresh_from_db()

    def supply(self, order, quantity):
        return supply_ready_commitment(
            commitment_id=order.commitments.get().id,
            commercial_quantity=quantity,
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Customer handoff",
            source_type="FULFILLMENT_HANDOFF",
            source_reference=order.order_number,
        )

    def cancel(self, order, *, key=None, correlation=None, reason="Customer cancellation"):
        return cancel_ready_order(
            order_id=order.pk,
            actor=self.actor,
            correlation_id=correlation or uuid.uuid4(),
            idempotency_key=key or uuid.uuid4(),
            reason=reason,
        )

    def complete(self, order, *, key=None, correlation=None, note="Collected"):
        return complete_order_fulfillment(
            order_id=order.pk,
            actor=self.actor,
            correlation_id=correlation or uuid.uuid4(),
            idempotency_key=key or uuid.uuid4(),
            note=note,
            reference="COLLECTION-001",
        )

    def test_confirmed_cancellation_releases_remaining_supply_without_changing_on_hand(self):
        order = self.create_confirmed_order()
        before_available = get_ready_availability(product=self.product, sale_unit=self.sale_unit)
        before_on_hand = StockPosition.objects.get(item=self.item).on_hand_base_quantity
        result = self.cancel(order)

        result.refresh_from_db()
        commitment = result.commitments.get()
        reservation = commitment.reservation
        allocation = reservation.allocations.get()
        self.assertEqual(result.status, Order.Status.CANCELLED)
        self.assertEqual(result.payment.state, Payment.State.CONFIRMED)
        self.assertEqual(commitment.state, Commitment.State.CANCELLED)
        self.assertEqual(commitment.cancelled_quantity, 3)
        self.assertEqual(commitment.supplied_quantity, 0)
        self.assertEqual(commitment.outstanding_quantity, 0)
        self.assertEqual(result.lines.get().outstanding_quantity, 0)
        self.assertEqual(reservation.state, Reservation.State.RELEASED)
        self.assertEqual(reservation.released_base_quantity, Decimal("15.000"))
        self.assertEqual(allocation.remaining_base_quantity, Decimal("0.000"))
        self.assertEqual(allocation.released_base_quantity, Decimal("15.000"))
        self.assertEqual(allocation.released_by_operation.kind, SourceAllocationOperation.Kind.RELEASE)
        self.assertEqual(StockPosition.objects.get(item=self.item).on_hand_base_quantity, before_on_hand)
        after_available = get_ready_availability(product=self.product, sale_unit=self.sale_unit)
        self.assertEqual(after_available.available_sale_units, before_available.available_sale_units + 3)

    def test_partial_supply_then_processing_cancellation_preserves_supply_and_cancels_remainder(self):
        order = self.create_confirmed_order(quantity=3)
        self.make_processing(order)
        self.supply(order, 1)
        order.lines.get().refresh_from_db()
        self.assertEqual(order.lines.get().outstanding_quantity, 2)
        on_hand_after_supply = StockPosition.objects.get(item=self.item).on_hand_base_quantity
        self.cancel(order)

        commitment = Commitment.objects.get(order=order)
        reservation = commitment.reservation
        self.assertEqual(commitment.supplied_quantity, 1)
        self.assertEqual(commitment.cancelled_quantity, 2)
        self.assertEqual(commitment.outstanding_quantity, 0)
        self.assertEqual(reservation.consumed_base_quantity, Decimal("5.000"))
        self.assertEqual(reservation.released_base_quantity, Decimal("10.000"))
        self.assertEqual(StockPosition.objects.get(item=self.item).on_hand_base_quantity, on_hand_after_supply)

    def test_cancellation_is_authorized_audited_idempotent_and_rejects_changed_reuse(self):
        order = self.create_confirmed_order()
        key, correlation = uuid.uuid4(), uuid.uuid4()
        self.revoke(self.actor, "orders.cancel")
        with self.assertRaises(PermissionDenied):
            self.cancel(order, key=key, correlation=correlation)
        self.grant(self.actor, "orders.cancel")
        first = self.cancel(order, key=key, correlation=correlation)
        counts = (
            CommitmentEvent.objects.count(), ReservationEvent.objects.count(),
            SourceAllocationOperation.objects.count(), OrderStatusEvent.objects.count(),
        )
        second = self.cancel(order, key=key, correlation=correlation)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(counts, (
            CommitmentEvent.objects.count(), ReservationEvent.objects.count(),
            SourceAllocationOperation.objects.count(), OrderStatusEvent.objects.count(),
        ))
        event = OrderStatusEvent.objects.get(idempotency_key=key)
        self.assertEqual(event.correlation_id, correlation)
        self.assertEqual(event.actor_id, self.actor.pk)
        with self.assertRaises(ValidationError):
            self.cancel(order, key=key, correlation=correlation, reason="Changed reason")

    def test_pending_cancel_is_prohibited_and_inactive_staff_is_rejected(self):
        pending = create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            lines=(OrderLineInput(self.product.pk, self.sale_unit.pk, 1, OrderLine.SupplyMode.READY),),
            creation_idempotency_key=uuid.uuid4(),
            contact=ContactInput("Pending Buyer", "+254724853914"),
        )
        with self.assertRaises(ValidationError):
            self.cancel(pending)
        confirmed = self.create_confirmed_order()
        self.actor.is_active = False
        self.actor.save(update_fields=("is_active",))
        with self.assertRaises(PermissionDenied):
            self.cancel(confirmed)

    def test_cancellation_late_failure_rolls_back_release_and_can_retry(self):
        order = self.create_confirmed_order()
        key, correlation = uuid.uuid4(), uuid.uuid4()
        with patch("apps.orders.lifecycle.Order.save", side_effect=ValidationError("late failure")):
            with self.assertRaises(ValidationError):
                self.cancel(order, key=key, correlation=correlation)
        order.refresh_from_db()
        commitment = Commitment.objects.get(order=order)
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(commitment.state, Commitment.State.ACTIVE)
        self.assertEqual(commitment.reservation.state, Reservation.State.ACTIVE)
        self.assertTrue(commitment.reservation.allocations.filter(remaining_base_quantity__gt=0).exists())
        self.cancel(order, key=key, correlation=correlation)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_full_supply_synchronizes_order_line_and_enables_minimal_completion(self):
        order = self.create_confirmed_order(quantity=2)
        self.make_processing(order)
        self.supply(order, 2)
        order.lines.get().refresh_from_db()
        self.assertEqual(order.lines.get().outstanding_quantity, 0)
        on_hand = StockPosition.objects.get(item=self.item).on_hand_base_quantity
        completion = self.complete(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.FULFILLED)
        self.assertEqual(completion.order_id, order.pk)
        self.assertEqual(completion.completed_by_id, self.actor.pk)
        self.assertEqual(StockPosition.objects.get(item=self.item).on_hand_base_quantity, on_hand)
        event = OrderStatusEvent.objects.get(order=order, new_status=Order.Status.FULFILLED)
        self.assertEqual(event.previous_status, Order.Status.PROCESSING)

    def test_completion_requires_permission_processing_and_zero_outstanding(self):
        confirmed = self.create_confirmed_order()
        with self.assertRaises(ValidationError):
            self.complete(confirmed)
        self.make_processing(confirmed)
        with self.assertRaises(ValidationError):
            self.complete(confirmed)
        self.supply(confirmed, 3)
        self.revoke(self.actor, "fulfillment.complete")
        with self.assertRaises(PermissionDenied):
            self.complete(confirmed)

    def test_completion_is_idempotent_changed_reuse_is_rejected_and_history_is_immutable(self):
        order = self.create_confirmed_order(quantity=1)
        self.make_processing(order)
        self.supply(order, 1)
        key, correlation = uuid.uuid4(), uuid.uuid4()
        first = self.complete(order, key=key, correlation=correlation)
        second = self.complete(order, key=key, correlation=correlation)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(FulfillmentCompletion.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.complete(order, key=key, correlation=correlation, note="Changed")
        with self.assertRaises(ValidationError):
            first.save(_fulfillment_service_write=True)
        with self.assertRaises(ValidationError):
            first.delete()

    def test_completion_late_failure_rolls_back_record_and_status(self):
        order = self.create_confirmed_order(quantity=1)
        self.make_processing(order)
        self.supply(order, 1)
        with patch("apps.fulfillment.services.Order.save", side_effect=ValidationError("late failure")):
            with self.assertRaises(ValidationError):
                self.complete(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)
        self.assertFalse(FulfillmentCompletion.objects.filter(order=order).exists())

    def test_minimal_completion_schema_has_no_inventory_or_delivery_logistics(self):
        fields = {field.name for field in FulfillmentCompletion._meta.get_fields()}
        self.assertTrue(
            {"inventory_item", "location", "lot", "reservation", "allocation", "branch", "driver", "route"}.isdisjoint(fields)
        )

    def test_order_and_payment_bulk_mutation_bypasses_are_closed(self):
        order = self.create_confirmed_order()
        with self.assertRaises(ValidationError):
            Order.objects.filter(pk=order.pk).update(status=Order.Status.CANCELLED)
        with self.assertRaises(ValidationError):
            OrderLine.objects.filter(order=order).update(outstanding_quantity=0)
        with self.assertRaises(ValidationError):
            Payment.objects.filter(pk=order.payment.pk).update(state=Payment.State.PENDING)
        with self.assertRaises(ValidationError):
            OrderStatusEvent.objects.filter(order=order).delete()

    def test_cancellation_and_completion_preserve_django_superuser_semantics(self):
        superuser = get_user_model().objects.create_superuser(
            username="phase-g-superuser", password=None
        )
        cancellable = self.create_confirmed_order(quantity=1)
        cancelled = cancel_ready_order(
            order_id=cancellable.pk,
            actor=superuser,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Superuser cancellation",
        )
        self.assertEqual(cancelled.status, Order.Status.CANCELLED)

        completable = self.create_confirmed_order(quantity=1)
        self.make_processing(completable)
        self.supply(completable, 1)
        completion = complete_order_fulfillment(
            order_id=completable.pk,
            actor=superuser,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            note="Superuser completion",
        )
        self.assertEqual(completion.completed_by_id, superuser.pk)
