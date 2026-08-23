import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.test import TestCase
from django.utils import timezone

from apps.commitments.models import Commitment, CommitmentEvent, CommitmentSupplyEvent
from apps.commitments.supply import supply_ready_commitment
from apps.fulfillment.services import complete_order_fulfillment
from apps.inventory.models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    InventoryMovementLine,
    Reservation,
    ReservationEvent,
    SourceAllocation,
    SourceAllocationOperation,
    StockLot,
    StockPosition,
)
from apps.inventory.services import MovementLineInput, post_inventory_movement
from apps.orders.models import (
    Order,
    OrderAddressSnapshot,
    OrderContactSnapshot,
    OrderLine,
    OrderStatusEvent,
)
from apps.orders.services import (
    ContactInput,
    OrderLineInput,
    cancel_ready_order,
    create_pending_order,
    start_order_processing,
)
from apps.payments.models import (
    Payment,
    PaymentEvidence,
    PaymentStatusEvent,
    PaymentVerificationAttempt,
)
from apps.payments.services import submit_payment_evidence, verify_payment_and_confirm_order
from apps.products.models import Product, ProductPrice, ProductSaleUnit


class StartOrderProcessingTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku="WTP-PROCESS", slug="processing-product", name="Processing Product",
            base_inventory_unit="seedling", is_active=True, is_published=True,
        )
        self.sale_unit = ProductSaleUnit.objects.create(
            product=self.product, name="Bundle of 5", base_quantity=Decimal("5.000")
        )
        ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("100.00"),
            effective_start=timezone.now() - timedelta(days=1),
        )
        self.item = InventoryItem.objects.create(product=self.product, base_unit="seedling")
        self.location = InventoryLocation.objects.create(code="PROCESS", name="Processing")
        self.lot = StockLot.objects.create(
            item=self.item, lot_code="PROCESS-LOT", condition=StockLot.Condition.SALEABLE
        )
        self.actor = get_user_model().objects.create_user(
            username="processing-actor", password=None, is_staff=True
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
            lines=(MovementLineInput(
                item_id=self.item.pk,
                lot_id=self.lot.pk,
                quantity=Decimal("100.000"),
                destination_location_id=self.location.pk,
            ),),
            actor=self.actor,
            reason="Processing test stock",
            source_type="TEST_RECEIPT",
            source_reference="PROCESSING-STOCK",
            idempotency_key=uuid.uuid4(),
        )

    @staticmethod
    def clear_permissions(actor):
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            actor.__dict__.pop(cache_name, None)

    def grant(self, actor, *names):
        for name in names:
            app_label, codename = name.split(".", 1)
            actor.user_permissions.add(Permission.objects.get(
                content_type__app_label=app_label, codename=codename
            ))
        self.clear_permissions(actor)

    def pending(self, *, mode=OrderLine.SupplyMode.READY):
        return create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            required_date=(timezone.localdate() + timedelta(days=2)) if mode == OrderLine.SupplyMode.PRE_ORDER else None,
            lines=(OrderLineInput(
                product_id=self.product.pk,
                sale_unit_id=self.sale_unit.pk,
                quantity=2,
                supply_mode=mode,
            ),),
            creation_idempotency_key=uuid.uuid4(),
            contact=ContactInput("Processing Buyer", "+254724853914", "process@example.com"),
        )

    def confirmed(self):
        order = self.pending()
        evidence = submit_payment_evidence(
            payment=order.payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim=f"PROC{uuid.uuid4().hex[:10]}",
        )
        return verify_payment_and_confirm_order(
            order_id=order.pk,
            payment_id=order.payment.pk,
            evidence_id=evidence.pk,
            provider_reference=evidence.reference_claim,
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Verified for processing tests",
        )

    def start(self, order, *, actor=None, key=None, correlation=None, reason="Start picking"):
        return start_order_processing(
            order_id=order.pk,
            actor=actor or self.actor,
            correlation_id=correlation or uuid.uuid4(),
            idempotency_key=key or uuid.uuid4(),
            reason=reason,
        )

    @staticmethod
    def rows(model):
        return list(model.objects.order_by("pk").values())

    def test_success_records_exact_event_and_mutates_no_payment_or_supply_fact(self):
        order = self.confirmed()
        key, correlation = uuid.uuid4(), uuid.uuid4()
        protected_models = (
            Payment, PaymentEvidence, PaymentVerificationAttempt, PaymentStatusEvent,
            OrderContactSnapshot, OrderAddressSnapshot, OrderLine,
            Commitment, CommitmentEvent, CommitmentSupplyEvent,
            Reservation, ReservationEvent, SourceAllocation, SourceAllocationOperation,
            StockPosition, InventoryMovement, InventoryMovementLine,
        )
        before = {model: self.rows(model) for model in protected_models}

        result = self.start(order, key=key, correlation=correlation, reason="  Start picking  ")

        self.assertEqual(result.status, Order.Status.PROCESSING)
        self.assertEqual(before, {model: self.rows(model) for model in protected_models})
        event = OrderStatusEvent.objects.get(idempotency_key=key)
        self.assertEqual(event.order_id, order.pk)
        self.assertEqual(event.previous_status, Order.Status.CONFIRMED)
        self.assertEqual(event.new_status, Order.Status.PROCESSING)
        self.assertEqual(event.actor_id, self.actor.pk)
        self.assertEqual(event.reason, "Start picking")
        self.assertEqual(event.correlation_id, correlation)

    def test_permission_active_staff_and_normal_superuser_semantics(self):
        order = self.confirmed()
        unauthorized = get_user_model().objects.create_user(
            username="no-process", password=None, is_staff=True
        )
        with self.assertRaises(PermissionDenied):
            self.start(order, actor=unauthorized)
        inactive = get_user_model().objects.create_user(
            username="inactive-process", password=None, is_staff=True, is_active=False
        )
        self.grant(inactive, "orders.process")
        with self.assertRaises(PermissionDenied):
            self.start(order, actor=inactive)
        superuser = get_user_model().objects.create_superuser(
            username="processing-root", password=None
        )
        self.start(order, actor=superuser)

    def test_pending_cancelled_and_fulfilled_orders_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.start(self.pending())

        cancelled = self.confirmed()
        cancel_ready_order(
            order_id=cancelled.pk, actor=self.actor, correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(), reason="Cancel before work",
        )
        with self.assertRaises(ValidationError):
            self.start(cancelled)

        fulfilled = self.confirmed()
        self.start(fulfilled)
        supply_ready_commitment(
            commitment_id=fulfilled.commitments.get().id,
            commercial_quantity=2,
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Complete handoff",
            source_type="FULFILLMENT_HANDOFF",
            source_reference=fulfilled.order_number,
        )
        complete_order_fulfillment(
            order_id=fulfilled.pk, actor=self.actor, correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(), note="Collected", reference="PROC-COLLECT",
        )
        with self.assertRaises(ValidationError):
            self.start(fulfilled)

    def test_unconfirmed_payment_and_preorder_are_rejected(self):
        order = self.confirmed()
        models.QuerySet(model=Payment, using="default").filter(pk=order.payment.pk).update(
            state=Payment.State.PENDING,
            provider_reference=None,
            verified_by=None,
            verified_at=None,
        )
        with self.assertRaises(ValidationError):
            self.start(order)

        preorder = self.pending(mode=OrderLine.SupplyMode.PRE_ORDER)
        self.forge_confirmed(preorder)
        with self.assertRaises(ValidationError):
            self.start(preorder)

    def forge_confirmed(self, order):
        models.QuerySet(model=Order, using="default").filter(pk=order.pk).update(
            status=Order.Status.CONFIRMED
        )
        models.QuerySet(model=Payment, using="default").filter(order_id=order.pk).update(
            state=Payment.State.CONFIRMED,
            provider_reference=f"FORGED{uuid.uuid4().hex[:10]}",
            verified_by=self.actor,
            verified_at=timezone.now(),
        )
        models.QuerySet(model=OrderLine, using="default").filter(order_id=order.pk).update(
            confirmed_quantity=models.F("quantity"), outstanding_quantity=models.F("quantity")
        )
        order.refresh_from_db()

    def test_missing_commitment_is_rejected(self):
        order = self.pending()
        self.forge_confirmed(order)
        with self.assertRaises(ValidationError):
            self.start(order)

    def test_invalid_commitment_reservation_and_allocation_are_each_rejected(self):
        order = self.confirmed()
        line = order.lines.get()
        models.QuerySet(model=OrderLine, using="default").filter(pk=line.pk).update(
            base_quantity=Decimal("6.000")
        )
        with self.assertRaises(ValidationError):
            self.start(order)

        order = self.confirmed()
        reservation = order.commitments.get().reservation
        models.QuerySet(model=Reservation, using="default").filter(pk=reservation.pk).update(
            initial_base_quantity=models.F("initial_base_quantity") + Decimal("1.000"),
            remaining_base_quantity=models.F("remaining_base_quantity") + Decimal("1.000"),
        )
        with self.assertRaises(ValidationError):
            self.start(order)

        order = self.confirmed()
        allocation = order.commitments.get().reservation.allocations.get()
        models.QuerySet(model=SourceAllocation, using="default").filter(pk=allocation.pk).update(
            released_base_quantity=models.F("released_base_quantity") + Decimal("1.000"),
            remaining_base_quantity=models.F("remaining_base_quantity") - Decimal("1.000"),
        )
        with self.assertRaises(ValidationError):
            self.start(order)

    def test_partial_supply_does_not_prevent_processing(self):
        order = self.confirmed()
        supply_ready_commitment(
            commitment_id=order.commitments.get().id,
            commercial_quantity=1,
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Early handoff",
            source_type="FULFILLMENT_HANDOFF",
            source_reference=order.order_number,
        )
        self.start(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)

    def test_idempotency_exact_retry_changed_input_and_different_key(self):
        order = self.confirmed()
        key, correlation = uuid.uuid4(), uuid.uuid4()
        first = self.start(order, key=key, correlation=correlation, reason="Start picking")
        second = self.start(order, key=key, correlation=correlation, reason="Start picking")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(OrderStatusEvent.objects.filter(idempotency_key=key).count(), 1)
        with self.assertRaises(ValidationError):
            self.start(order, key=key, correlation=correlation, reason="Changed reason")
        with self.assertRaises(ValidationError):
            self.start(order, key=uuid.uuid4(), correlation=correlation, reason="Start picking")
        self.assertEqual(
            OrderStatusEvent.objects.filter(
                order=order, new_status=Order.Status.PROCESSING
            ).count(),
            1,
        )

    def test_failure_to_append_event_rolls_back_order_transition(self):
        order = self.confirmed()
        with patch("apps.orders.lifecycle.OrderStatusEvent.save", side_effect=ValidationError("boom")):
            with self.assertRaises(ValidationError):
                self.start(order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertFalse(order.status_events.filter(new_status=Order.Status.PROCESSING).exists())

    def test_processing_event_is_append_only(self):
        order = self.confirmed()
        key = uuid.uuid4()
        self.start(order, key=key)
        event = OrderStatusEvent.objects.get(idempotency_key=key)
        event.reason = "Rewrite"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()
