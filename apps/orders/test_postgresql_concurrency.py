import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, tag
from django.utils import timezone

from apps.commitments.models import Commitment
from apps.commitments.supply import supply_ready_commitment
from apps.fulfillment.models import FulfillmentCompletion
from apps.fulfillment.services import complete_order_fulfillment
from apps.inventory.models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    Reservation,
    StockLot,
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
from apps.payments.models import PaymentEvidence
from apps.payments.services import submit_payment_evidence, verify_payment_and_confirm_order
from apps.products.models import Product, ProductPrice, ProductSaleUnit


@skipUnless(
    connection.vendor == "postgresql",
    "PostgreSQL row-lock integration tests require a configured PostgreSQL test database.",
)
@tag("postgresql_concurrency")
class PostgreSQLReadyLifecycleConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-PG-LOCK",
            slug="postgres-lock-product",
            name="PostgreSQL Lock Product",
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
        self.location = InventoryLocation.objects.create(code="PG-LOCK", name="Postgres Lock")
        self.lot = StockLot.objects.create(
            item=self.item,
            lot_code="PG-LOCK-LOT",
            condition=StockLot.Condition.SALEABLE,
        )
        self.actor = get_user_model().objects.create_user(
            username="postgres-lock-actor", password=None, is_staff=True
        )
        for permission_name in (
            "inventory.receive", "inventory.release", "payments.verify",
            "commitments.allocate", "orders.cancel", "orders.process", "fulfillment.complete",
        ):
            app_label, codename = permission_name.split(".", 1)
            self.actor.user_permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )

    def receive(self, quantity):
        post_inventory_movement(
            movement_type=InventoryMovement.Type.RECEIPT,
            lines=(
                MovementLineInput(
                    item_id=self.item.pk,
                    lot_id=self.lot.pk,
                    quantity=Decimal(quantity),
                    destination_location_id=self.location.pk,
                ),
            ),
            actor=self.actor,
            reason="PostgreSQL concurrency stock",
            source_type="TEST_RECEIPT",
            source_reference=str(uuid.uuid4()),
            idempotency_key=uuid.uuid4(),
        )

    def pending_request(self, quantity=1):
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
            contact=ContactInput("Concurrency Buyer", "+254724853914"),
        )
        evidence = submit_payment_evidence(
            payment=order.payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim=f"PG{uuid.uuid4().hex[:10]}",
        )
        return order, evidence

    def confirm(self, order, evidence, *, idempotency_key=None):
        return verify_payment_and_confirm_order(
            order_id=order.pk,
            payment_id=order.payment.pk,
            evidence_id=evidence.pk,
            provider_reference=evidence.reference_claim,
            actor=get_user_model().objects.get(pk=self.actor.pk),
            correlation_id=uuid.uuid4(),
            idempotency_key=idempotency_key or uuid.uuid4(),
            reason="PostgreSQL competing confirmation",
        )

    @staticmethod
    def run_competing(*workers):
        barrier = Barrier(len(workers))

        def invoke(worker):
            close_old_connections()
            barrier.wait()
            try:
                worker()
                return "SUCCESS"
            except ValidationError:
                return "REJECTED"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(workers)) as executor:
            return tuple(executor.map(invoke, workers))

    def test_two_confirmations_cannot_reserve_the_same_supply(self):
        self.receive("5.000")
        first_order, first_evidence = self.pending_request()
        second_order, second_evidence = self.pending_request()
        outcomes = self.run_competing(
            lambda: self.confirm(first_order, first_evidence),
            lambda: self.confirm(second_order, second_evidence),
        )
        self.assertEqual(sorted(outcomes), ["REJECTED", "SUCCESS"])
        self.assertEqual(Commitment.objects.count(), 1)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_same_order_creation_key_serializes_concurrent_first_use(self):
        key = uuid.uuid4()

        def create():
            create_pending_order(
                channel=Order.Channel.ECOMMERCE,
                fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
                lines=(
                    OrderLineInput(
                        product_id=self.product.pk,
                        sale_unit_id=self.sale_unit.pk,
                        quantity=1,
                        supply_mode=OrderLine.SupplyMode.READY,
                    ),
                ),
                creation_idempotency_key=key,
                contact=ContactInput("Concurrent Retry", "+254724853914"),
            )

        outcomes = self.run_competing(create, create)
        self.assertEqual(outcomes, ("SUCCESS", "SUCCESS"))
        self.assertEqual(Order.objects.filter(creation_idempotency_key=key).count(), 1)

    def test_changed_order_creation_reuse_has_one_winner_not_integrity_error(self):
        key = uuid.uuid4()

        def create(quantity):
            create_pending_order(
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
                creation_idempotency_key=key,
                contact=ContactInput("Concurrent Collision", "+254724853914"),
            )

        outcomes = self.run_competing(lambda: create(1), lambda: create(2))
        self.assertEqual(sorted(outcomes), ["REJECTED", "SUCCESS"])
        self.assertEqual(Order.objects.filter(creation_idempotency_key=key).count(), 1)

    def test_confirmation_key_serializes_different_payment_roots(self):
        self.receive("10.000")
        first_order, first_evidence = self.pending_request()
        second_order, second_evidence = self.pending_request()
        key = uuid.uuid4()
        outcomes = self.run_competing(
            lambda: self.confirm(first_order, first_evidence, idempotency_key=key),
            lambda: self.confirm(second_order, second_evidence, idempotency_key=key),
        )
        self.assertEqual(sorted(outcomes), ["REJECTED", "SUCCESS"])
        self.assertEqual(Commitment.objects.count(), 1)

    def test_supply_and_cancellation_serialize_without_quantity_corruption(self):
        self.receive("10.000")
        order, evidence = self.pending_request(quantity=2)
        order = self.confirm(order, evidence)
        commitment = order.commitments.get()
        cancellation_key, correlation = uuid.uuid4(), uuid.uuid4()

        outcomes = self.run_competing(
            lambda: supply_ready_commitment(
                commitment_id=commitment.id,
                commercial_quantity=1,
                actor=get_user_model().objects.get(pk=self.actor.pk),
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="Concurrent handoff",
                source_type="FULFILLMENT_HANDOFF",
                source_reference=order.order_number,
            ),
            lambda: cancel_ready_order(
                order_id=order.pk,
                actor=get_user_model().objects.get(pk=self.actor.pk),
                correlation_id=correlation,
                idempotency_key=cancellation_key,
                reason="Concurrent cancellation",
            ),
        )
        self.assertIn("SUCCESS", outcomes)
        order.refresh_from_db()
        commitment.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(
            commitment.committed_quantity,
            commitment.supplied_quantity + commitment.cancelled_quantity,
        )
        self.assertEqual(commitment.outstanding_quantity, 0)
        self.assertEqual(commitment.reservation.remaining_base_quantity, Decimal("0.000"))

    def test_two_processing_requests_with_same_key_are_one_transition(self):
        self.receive("10.000")
        order, evidence = self.pending_request(quantity=2)
        order = self.confirm(order, evidence)
        key, correlation = uuid.uuid4(), uuid.uuid4()

        def worker():
            start_order_processing(
                order_id=order.pk,
                actor=get_user_model().objects.get(pk=self.actor.pk),
                correlation_id=correlation,
                idempotency_key=key,
                reason="Concurrent processing",
            )

        outcomes = self.run_competing(worker, worker)
        self.assertEqual(outcomes, ("SUCCESS", "SUCCESS"))
        self.assertEqual(OrderStatusEvent.objects.filter(idempotency_key=key).count(), 1)

    def test_two_processing_requests_with_different_keys_have_one_winner(self):
        self.receive("10.000")
        order, evidence = self.pending_request(quantity=2)
        order = self.confirm(order, evidence)

        def worker(key):
            start_order_processing(
                order_id=order.pk,
                actor=get_user_model().objects.get(pk=self.actor.pk),
                correlation_id=uuid.uuid4(),
                idempotency_key=key,
                reason="Concurrent processing",
            )

        outcomes = self.run_competing(
            lambda: worker(uuid.uuid4()), lambda: worker(uuid.uuid4())
        )
        self.assertEqual(sorted(outcomes), ["REJECTED", "SUCCESS"])
        self.assertEqual(
            OrderStatusEvent.objects.filter(
                order=order, new_status=Order.Status.PROCESSING
            ).count(),
            1,
        )

    def test_processing_and_cancellation_serialize_without_corruption(self):
        self.receive("10.000")
        order, evidence = self.pending_request(quantity=2)
        order = self.confirm(order, evidence)
        outcomes = self.run_competing(
            lambda: start_order_processing(
                order_id=order.pk,
                actor=get_user_model().objects.get(pk=self.actor.pk),
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="Concurrent processing",
            ),
            lambda: cancel_ready_order(
                order_id=order.pk,
                actor=get_user_model().objects.get(pk=self.actor.pk),
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="Concurrent cancellation",
            ),
        )
        self.assertIn("SUCCESS", outcomes)
        order.refresh_from_db()
        commitment = order.commitments.get()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertLessEqual(
            OrderStatusEvent.objects.filter(
                order=order, new_status=Order.Status.PROCESSING
            ).count(),
            1,
        )
        self.assertEqual(
            commitment.committed_quantity,
            commitment.supplied_quantity + commitment.cancelled_quantity,
        )

    def test_two_completion_retries_with_same_key_are_one_completion(self):
        self.receive("10.000")
        order, evidence = self.pending_request(quantity=2)
        order = self.confirm(order, evidence)
        start_order_processing(
            order_id=order.pk,
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Start fulfillment",
        )
        supply_ready_commitment(
            commitment_id=order.commitments.get().id,
            commercial_quantity=2,
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Complete handoff",
            source_type="FULFILLMENT_HANDOFF",
            source_reference=order.order_number,
        )
        key, correlation = uuid.uuid4(), uuid.uuid4()

        def worker():
            complete_order_fulfillment(
                order_id=order.pk,
                actor=get_user_model().objects.get(pk=self.actor.pk),
                correlation_id=correlation,
                idempotency_key=key,
                note="Concurrent complete",
                reference="PG-COMPLETE",
            )

        outcomes = self.run_competing(worker, worker)
        self.assertEqual(outcomes, ("SUCCESS", "SUCCESS"))
        self.assertEqual(FulfillmentCompletion.objects.filter(idempotency_key=key).count(), 1)
        self.assertEqual(
            OrderStatusEvent.objects.filter(
                order=order, new_status=Order.Status.FULFILLED
            ).count(),
            1,
        )
