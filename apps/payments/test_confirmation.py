import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.test import TestCase
from django.utils import timezone

from apps.commitments.models import Commitment
from apps.commitments.services import _create_commitment_for_confirmation
from apps.inventory.models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    Reservation,
    SourceAllocation,
    StockLot,
    StockPosition,
)
from apps.inventory.services import MovementLineInput, post_inventory_movement
from apps.orders.models import Order, OrderLine, OrderStatusEvent
from apps.orders.services import ContactInput, OrderLineInput, create_pending_order
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .models import Payment, PaymentEvidence, PaymentStatusEvent, PaymentVerificationAttempt
from .services import submit_payment_evidence, verify_payment_and_confirm_order


class AtomicConfirmationTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku="WTP-F-001",
            slug="phase-f-product",
            name="Phase F Product",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        self.sale_unit = ProductSaleUnit.objects.create(
            product=self.product,
            name="Pair",
            base_quantity=Decimal("2.000"),
        )
        ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("100.00"),
            effective_start=timezone.now() - timedelta(days=1),
        )
        self.item = InventoryItem.objects.create(product=self.product, base_unit="seedling")
        self.location = InventoryLocation.objects.create(code="F-MAIN", name="Phase F Main")
        self.lot = StockLot.objects.create(
            item=self.item,
            lot_code="F-LOT-1",
            condition=StockLot.Condition.SALEABLE,
        )
        self.actor = get_user_model().objects.create_user(
            username="phase-f-verifier", password=None, is_staff=True
        )
        self.grant(self.actor, "payments.verify", "commitments.allocate", "inventory.receive")
        self.receive("20.000")

    def grant(self, actor, *permission_names):
        for permission_name in permission_names:
            app_label, codename = permission_name.split(".", 1)
            actor.user_permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            actor.__dict__.pop(cache_name, None)

    def revoke(self, actor, permission_name):
        app_label, codename = permission_name.split(".", 1)
        actor.user_permissions.remove(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            actor.__dict__.pop(cache_name, None)

    def receive(self, quantity):
        return post_inventory_movement(
            movement_type=InventoryMovement.Type.RECEIPT,
            lines=[
                MovementLineInput(
                    item_id=self.item.pk,
                    lot_id=self.lot.pk,
                    quantity=Decimal(quantity),
                    destination_location_id=self.location.pk,
                )
            ],
            actor=self.actor,
            reason="Phase F test stock",
            idempotency_key=uuid.uuid4(),
        )

    def create_order(self, modes=(OrderLine.SupplyMode.READY,), quantity=2):
        required_date = (
            timezone.localdate() + timedelta(days=14)
            if OrderLine.SupplyMode.PRE_ORDER in modes
            else None
        )
        return create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            lines=[
                OrderLineInput(
                    product_id=self.product.pk,
                    sale_unit_id=self.sale_unit.pk,
                    quantity=quantity,
                    supply_mode=mode,
                )
                for mode in modes
            ],
            creation_idempotency_key=uuid.uuid4(),
            contact=ContactInput("Phase F Buyer", "+254724853914", "buyer@example.com"),
            required_date=required_date,
        )

    def evidence(self, order, reference="FREF001"):
        return submit_payment_evidence(
            payment=order.payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim=reference,
            submitted_message="Customer-submitted M-Pesa evidence",
        )

    def command(self, order, evidence, *, key=None, correlation=None, reference="FREF001", actor=None):
        return verify_payment_and_confirm_order(
            order_id=order.pk,
            payment_id=order.payment.pk,
            evidence_id=evidence.pk,
            provider_reference=reference,
            actor=actor or self.actor,
            correlation_id=correlation or uuid.uuid4(),
            idempotency_key=key or uuid.uuid4(),
            reason="Staff reviewed submitted evidence against Order and Payment facts",
        )

    def test_success_confirms_payment_and_order_and_establishes_complete_ready_supply(self):
        order = self.create_order()
        evidence = self.evidence(order)
        before = StockPosition.objects.get(item=self.item).on_hand_base_quantity
        result = self.command(order, evidence)

        result.refresh_from_db()
        result.payment.refresh_from_db()
        line = result.lines.get()
        commitment = line.commitment
        reservation = commitment.reservation
        self.assertEqual(result.status, Order.Status.CONFIRMED)
        self.assertNotEqual(result.status, Order.Status.PROCESSING)
        self.assertEqual(result.payment.state, Payment.State.CONFIRMED)
        self.assertEqual(result.payment.provider_reference, "FREF001")
        self.assertEqual(commitment.committed_quantity, line.quantity)
        self.assertEqual(reservation.initial_base_quantity, commitment.committed_base_quantity)
        self.assertEqual(
            sum((a.initial_base_quantity for a in reservation.allocations.all()), Decimal("0.000")),
            commitment.committed_base_quantity,
        )
        self.assertEqual(line.confirmed_quantity, line.quantity)
        self.assertEqual(line.outstanding_quantity, line.quantity)
        self.assertEqual(StockPosition.objects.get(item=self.item).on_hand_base_quantity, before)
        self.assertEqual(InventoryMovement.objects.filter(movement_type="ISSUE").count(), 0)

    def test_confirmation_requires_both_permissions_and_active_staff(self):
        order = self.create_order()
        evidence = self.evidence(order)
        self.revoke(self.actor, "commitments.allocate")
        with self.assertRaises(PermissionDenied):
            self.command(order, evidence)
        self.grant(self.actor, "commitments.allocate")
        self.revoke(self.actor, "payments.verify")
        with self.assertRaises(PermissionDenied):
            self.command(order, evidence)
        self.grant(self.actor, "payments.verify")
        self.actor.is_active = False
        self.actor.save(update_fields=("is_active",))
        with self.assertRaises(PermissionDenied):
            self.command(order, evidence)
        self.assertFalse(PaymentVerificationAttempt.objects.exists())

    def test_superuser_preserves_normal_django_permission_semantics(self):
        order = self.create_order()
        evidence = self.evidence(order)
        superuser = get_user_model().objects.create_superuser(username="phase-f-root", password=None)
        result = self.command(order, evidence, actor=superuser)
        self.assertEqual(result.status, Order.Status.CONFIRMED)

    def test_preorder_and_mixed_orders_are_rejected_before_acceptance_history(self):
        for modes in (
            (OrderLine.SupplyMode.PRE_ORDER,),
            (OrderLine.SupplyMode.READY, OrderLine.SupplyMode.PRE_ORDER),
        ):
            order = self.create_order(modes=modes)
            evidence = self.evidence(order, reference=str(uuid.uuid4()))
            with self.assertRaises(ValidationError):
                self.command(order, evidence, reference=str(uuid.uuid4()))
        self.assertFalse(PaymentVerificationAttempt.objects.exists())

    def test_invalid_evidence_and_wrong_payment_amount_are_rejected(self):
        order = self.create_order()
        other = self.create_order()
        wrong_evidence = self.evidence(other, reference="OTHERREF")
        with self.assertRaises(ValidationError):
            self.command(order, wrong_evidence)
        models.QuerySet(model=Payment, using="default").filter(pk=order.payment.pk).update(
            amount=Decimal("99.00")
        )
        with self.assertRaises(ValidationError):
            self.command(order, self.evidence(order))
        self.assertFalse(
            PaymentVerificationAttempt.objects.filter(payment_id=order.payment.pk).exists()
        )

    def test_insufficient_stock_preserves_acceptance_but_rolls_back_all_confirmation_effects(self):
        order = self.create_order(quantity=11)
        evidence = self.evidence(order)
        key, correlation = uuid.uuid4(), uuid.uuid4()
        with self.assertRaises(ValidationError):
            self.command(order, evidence, key=key, correlation=correlation)
        order.refresh_from_db()
        order.payment.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment.state, Payment.State.PENDING)
        self.assertEqual(PaymentVerificationAttempt.objects.get(idempotency_key=key).outcome, "APPROVED")
        self.assertFalse(Commitment.objects.filter(order=order).exists())
        self.assertFalse(Reservation.objects.filter(commitment__order=order).exists())
        self.assertFalse(SourceAllocation.objects.filter(reservation__commitment__order=order).exists())

    def test_late_transaction_failure_rolls_back_children_and_same_key_retry_recovers(self):
        order = self.create_order()
        evidence = self.evidence(order)
        key, correlation = uuid.uuid4(), uuid.uuid4()
        with patch("apps.payments.confirmation.Payment.save", side_effect=ValidationError("late failure")):
            with self.assertRaises(ValidationError):
                self.command(order, evidence, key=key, correlation=correlation)
        self.assertEqual(PaymentVerificationAttempt.objects.filter(idempotency_key=key).count(), 1)
        self.assertFalse(Commitment.objects.filter(order=order).exists())
        self.assertFalse(Reservation.objects.filter(commitment__order=order).exists())
        self.assertFalse(SourceAllocation.objects.filter(reservation__commitment__order=order).exists())

        result = self.command(order, evidence, key=key, correlation=correlation)
        self.assertEqual(result.status, Order.Status.CONFIRMED)
        self.assertEqual(PaymentVerificationAttempt.objects.filter(idempotency_key=key).count(), 1)

    def test_each_confirmation_stage_is_inside_the_same_rollback_boundary(self):
        failure_patches = (
            "apps.payments.confirmation.reserve_and_allocate_ready_commitment",
            "apps.inventory.reservations._create_allocation_lines",
            "apps.payments.confirmation.Payment.save",
            "apps.payments.confirmation.Order.save",
        )
        for index, target in enumerate(failure_patches, start=1):
            with self.subTest(target=target):
                order = self.create_order()
                evidence = self.evidence(order, reference=f"ROLLBACK{index}")
                key = uuid.uuid4()
                with patch(target, side_effect=ValidationError(f"stage {index} failure")):
                    with self.assertRaises(ValidationError):
                        self.command(order, evidence, key=key, reference=f"ROLLBACK{index}")
                order.refresh_from_db()
                order.payment.refresh_from_db()
                self.assertEqual(order.status, Order.Status.PENDING)
                self.assertEqual(order.payment.state, Payment.State.PENDING)
                self.assertTrue(PaymentVerificationAttempt.objects.filter(idempotency_key=key).exists())
                self.assertFalse(Commitment.objects.filter(order=order).exists())
                self.assertFalse(Reservation.objects.filter(commitment__order=order).exists())
                self.assertFalse(SourceAllocation.objects.filter(reservation__commitment__order=order).exists())

    def test_stale_order_or_payment_state_is_rejected_before_new_acceptance(self):
        stale_order = self.create_order()
        stale_order_evidence = self.evidence(stale_order, reference="STALEORDER")
        models.QuerySet(model=Order, using="default").filter(pk=stale_order.pk).update(
            status=Order.Status.CONFIRMED
        )
        with self.assertRaises(ValidationError):
            self.command(stale_order, stale_order_evidence, reference="STALEORDER")

        stale_payment_order = self.create_order()
        stale_payment_evidence = self.evidence(stale_payment_order, reference="STALEPAYMENT")
        models.QuerySet(model=Payment, using="default").filter(
            pk=stale_payment_order.payment.pk
        ).update(
            state=Payment.State.CONFIRMED,
            provider_reference="STALEPAYMENT",
            verified_by=self.actor,
            verified_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            self.command(stale_payment_order, stale_payment_evidence, reference="STALEPAYMENT")
        self.assertFalse(
            PaymentVerificationAttempt.objects.filter(
                payment_id__in=(stale_order.payment.pk, stale_payment_order.payment.pk)
            ).exists()
        )

    def test_complete_operation_is_idempotent_and_changed_reuse_is_rejected(self):
        order = self.create_order()
        evidence = self.evidence(order)
        key, correlation = uuid.uuid4(), uuid.uuid4()
        first = self.command(order, evidence, key=key, correlation=correlation)
        counts = (
            Commitment.objects.count(), Reservation.objects.count(), SourceAllocation.objects.count(),
            PaymentVerificationAttempt.objects.count(), OrderStatusEvent.objects.count(),
            PaymentStatusEvent.objects.count(),
        )
        second = self.command(order, evidence, key=key, correlation=correlation)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(counts, (
            Commitment.objects.count(), Reservation.objects.count(), SourceAllocation.objects.count(),
            PaymentVerificationAttempt.objects.count(), OrderStatusEvent.objects.count(),
            PaymentStatusEvent.objects.count(),
        ))
        with self.assertRaises(ValidationError):
            self.command(order, evidence, key=key, correlation=uuid.uuid4())

    def test_confirmed_provider_reference_cannot_be_reused(self):
        first = self.create_order()
        self.command(first, self.evidence(first), reference="UNIQUE-MPESA")
        second = self.create_order()
        with self.assertRaises(ValidationError):
            self.command(second, self.evidence(second), reference=" unique-mpesa ")
        second.refresh_from_db()
        self.assertEqual(second.status, Order.Status.PENDING)

    def test_fifo_blocks_later_order_when_earlier_confirmed_commitment_is_unreserved(self):
        earlier = self.create_order()
        earlier_line = earlier.lines.get()
        with transaction.atomic():
            _create_commitment_for_confirmation(
                order_line_id=earlier_line.pk,
                actor=self.actor,
                confirmed_at=timezone.now() - timedelta(minutes=1),
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="FIFO test predecessor",
                source_type="ORDER_CONFIRMATION",
                source_reference=earlier.order_number,
            )
        models.QuerySet(model=Order, using="default").filter(pk=earlier.pk).update(
            status=Order.Status.CONFIRMED
        )

        later = self.create_order()
        with self.assertRaisesMessage(ValidationError, "earlier eligible READY Commitment"):
            self.command(later, self.evidence(later), reference="LATERREF")
        self.assertFalse(Commitment.objects.filter(order=later).exists())

    def test_audit_history_shares_actor_and_correlation_without_exposing_sources_on_result(self):
        order = self.create_order()
        evidence = self.evidence(order)
        correlation = uuid.uuid4()
        result = self.command(order, evidence, correlation=correlation)
        attempt = PaymentVerificationAttempt.objects.get(payment=order.payment, outcome="APPROVED")
        payment_event = PaymentStatusEvent.objects.get(payment=order.payment, new_state="CONFIRMED")
        order_event = OrderStatusEvent.objects.get(order=order, new_status="CONFIRMED")
        self.assertEqual({attempt.correlation_id, payment_event.correlation_id, order_event.correlation_id}, {correlation})
        self.assertEqual({attempt.actor_id, payment_event.actor_id, order_event.actor_id}, {self.actor.pk})
        self.assertFalse(hasattr(result, "stock_position"))
        self.assertFalse(hasattr(result, "lot"))
        self.assertFalse(hasattr(result, "location"))
