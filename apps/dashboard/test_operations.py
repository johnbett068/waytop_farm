import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.commitments.models import Commitment, CommitmentSupplyEvent
from apps.commitments.supply import supply_ready_commitment
from apps.fulfillment.models import FulfillmentCompletion
from apps.fulfillment.services import complete_order_fulfillment
from apps.inventory.models import (
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    Reservation,
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
from apps.payments.models import (
    Payment,
    PaymentEvidence,
    PaymentVerificationAttempt,
)
from apps.payments.services import (
    record_rejected_verification_attempt,
    submit_payment_evidence,
    verify_payment_and_confirm_order,
)
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .queries import RECENT_ACTIVITY_LIMIT, build_operations_dashboard


class OperationsDashboardProjectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            category=Product.Category.VEGETABLE,
            sku="WTP-OPS-001",
            slug="operations-product",
            name="Operations Product",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        cls.sale_unit = ProductSaleUnit.objects.create(
            product=cls.product,
            name="Operations bundle",
            base_quantity=Decimal("5.000"),
        )
        ProductPrice.objects.create(
            sale_unit=cls.sale_unit,
            amount=Decimal("100.00"),
            effective_start=timezone.now() - timedelta(days=1),
        )
        cls.item = InventoryItem.objects.create(
            product=cls.product,
            base_unit="seedling",
        )
        cls.location = InventoryLocation.objects.create(
            code="OPS-PRIVATE-LOCATION",
            name="Private operations location",
        )
        cls.lot = StockLot.objects.create(
            item=cls.item,
            lot_code="OPS-PRIVATE-LOT",
            condition=StockLot.Condition.SALEABLE,
        )
        cls.actor = get_user_model().objects.create_user(
            username="private-operations-actor",
            password=None,
            is_staff=True,
        )
        cls._grant(
            cls.actor,
            "orders.view",
            "orders.cancel",
            "orders.process",
            "payments.verify",
            "commitments.view",
            "commitments.allocate",
            "inventory.view",
            "inventory.receive",
            "inventory.release",
            "fulfillment.complete",
        )
        post_inventory_movement(
            movement_type=InventoryMovement.Type.RECEIPT,
            lines=(
                MovementLineInput(
                    item_id=cls.item.pk,
                    lot_id=cls.lot.pk,
                    quantity=Decimal("100.000"),
                    destination_location_id=cls.location.pk,
                ),
            ),
            actor=cls.actor,
            reason="Authoritative test receipt",
            source_type="TEST_RECEIPT",
            source_reference="PRIVATE-RECEIPT-SOURCE",
            idempotency_key=uuid.uuid4(),
        )

        cls.pending = cls._pending_order("Pending Operations Buyer")
        cls.rejected = cls._pending_order("Rejected Operations Buyer")
        rejected_evidence = submit_payment_evidence(
            payment=cls.rejected.payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim="PRIVATE-REJECTED-REFERENCE",
            submitted_message="PRIVATE RAW PAYMENT EVIDENCE",
        )
        record_rejected_verification_attempt(
            payment=cls.rejected.payment,
            evidence=rejected_evidence,
            actor=cls.actor,
            reason="Authoritative rejection",
            idempotency_key=uuid.uuid4(),
        )

        cls.confirmed = cls._confirmed_order("Confirmed Operations Buyer")
        cls.processing = cls._confirmed_order("Processing Operations Buyer")
        start_order_processing(
            order_id=cls.processing.pk,
            actor=cls.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Start processing projection fixture",
        )

        cls.fulfilled = cls._confirmed_order("Fulfilled Operations Buyer")
        start_order_processing(
            order_id=cls.fulfilled.pk,
            actor=cls.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Start fulfilled projection fixture",
        )
        supply_ready_commitment(
            commitment_id=cls.fulfilled.commitments.get().id,
            commercial_quantity=1,
            actor=cls.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Supply fulfilled projection fixture",
            source_type="FULFILLMENT_HANDOFF",
            source_reference=cls.fulfilled.order_number,
        )
        complete_order_fulfillment(
            order_id=cls.fulfilled.pk,
            actor=cls.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            note="Projection fixture completed",
            reference="PRIVATE-FULFILLMENT-REFERENCE",
        )

        cls.cancelled = cls._confirmed_order("Cancelled Operations Buyer")
        cancel_ready_order(
            order_id=cls.cancelled.pk,
            actor=cls.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Cancel projection fixture",
        )

    @classmethod
    def _grant(cls, actor, *permission_names):
        for permission_name in permission_names:
            app_label, codename = permission_name.split(".", 1)
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        cls._clear_permission_cache(actor)

    @staticmethod
    def _clear_permission_cache(actor):
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            actor.__dict__.pop(cache_name, None)

    @classmethod
    def _pending_order(cls, buyer_name):
        return create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            lines=(
                OrderLineInput(
                    product_id=cls.product.pk,
                    sale_unit_id=cls.sale_unit.pk,
                    quantity=1,
                    supply_mode=OrderLine.SupplyMode.READY,
                ),
            ),
            creation_idempotency_key=uuid.uuid4(),
            contact=ContactInput(
                buyer_name,
                "+254724853914",
                "private-buyer@example.com",
            ),
        )

    @classmethod
    def _confirmed_order(cls, buyer_name):
        order = cls._pending_order(buyer_name)
        evidence = submit_payment_evidence(
            payment=order.payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim=f"OPS{uuid.uuid4().hex[:10]}",
            submitted_message="PRIVATE CONFIRMATION EVIDENCE",
        )
        return verify_payment_and_confirm_order(
            order_id=order.pk,
            payment_id=order.payment.pk,
            evidence_id=evidence.pk,
            provider_reference=evidence.reference_claim,
            actor=cls.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
            reason="Verify operations projection fixture",
        )

    @staticmethod
    def _section(snapshot, key):
        return next(section for section in snapshot["sections"] if section["key"] == key)

    @classmethod
    def _metrics(cls, snapshot, key):
        return {
            metric["label"]: metric["value"]
            for metric in cls._section(snapshot, key)["metrics"]
        }

    def test_metrics_use_authoritative_current_states(self):
        snapshot = build_operations_dashboard(actor=self.actor)
        self.assertEqual(
            self._metrics(snapshot, "orders"),
            {
                "Pending": 2,
                "Confirmed": 1,
                "Processing": 1,
                "Fulfilled": 1,
                "Cancelled": 1,
            },
        )
        self.assertEqual(
            self._metrics(snapshot, "payments"),
            {
                "Pending": 2,
                "Confirmed": 4,
                "Approved verifications": 4,
                "Rejected verifications": 1,
            },
        )
        self.assertEqual(
            self._metrics(snapshot, "commitments"),
            {
                "Active commitments": 2,
                "Satisfied commitments": 1,
                "Cancelled commitments": 1,
                "Active reservations": 2,
                "Consumed reservations": 1,
                "Released reservations": 1,
            },
        )
        self.assertEqual(
            self._metrics(snapshot, "inventory"),
            {
                "Inventory items": 1,
                "Positions with stock": 1,
                "Movements": 2,
                "Issues": 1,
            },
        )
        self.assertEqual(
            self._metrics(snapshot, "fulfillment"),
            {"Completed fulfillments": 1},
        )

    def test_recent_activity_is_bounded_chronological_and_authoritative(self):
        activity = build_operations_dashboard(actor=self.actor)["activity"]
        self.assertLessEqual(len(activity), RECENT_ACTIVITY_LIMIT)
        self.assertEqual(
            [item.timestamp for item in activity],
            sorted((item.timestamp for item in activity), reverse=True),
        )
        sources = {item.source for item in activity}
        self.assertTrue(
            {
                "OrderStatusEvent",
                "PaymentStatusEvent",
                "CommitmentEvent",
                "ReservationEvent",
                "SourceAllocationOperation",
                "InventoryMovement",
                "FulfillmentCompletion",
            }.intersection(sources)
        )

    def test_sections_are_permission_filtered_and_private_facts_are_absent(self):
        viewer = get_user_model().objects.create_user(
            username="inventory-dashboard-viewer",
            password=None,
            is_staff=True,
        )
        self._grant(viewer, "inventory.view")
        snapshot = build_operations_dashboard(actor=viewer)
        self.assertEqual(
            [section["key"] for section in snapshot["sections"]],
            ["inventory"],
        )
        self.client.force_login(viewer)
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory")
        self.assertNotContains(response, self.confirmed.order_number)
        for private_value in (
            "PRIVATE RAW PAYMENT EVIDENCE",
            "PRIVATE CONFIRMATION EVIDENCE",
            "PRIVATE-REJECTED-REFERENCE",
            "PRIVATE-RECEIPT-SOURCE",
            "OPS-PRIVATE-LOCATION",
            "OPS-PRIVATE-LOT",
            "private-operations-actor",
            "private-buyer@example.com",
            "Confirmed Operations Buyer",
        ):
            self.assertNotContains(response, private_value)

    def test_projection_is_read_only_and_has_a_bounded_query_count(self):
        tracked_models = (
            Order,
            OrderStatusEvent,
            Payment,
            PaymentVerificationAttempt,
            Commitment,
            CommitmentSupplyEvent,
            Reservation,
            InventoryMovement,
            StockPosition,
            FulfillmentCompletion,
        )
        before = {model: model.objects.count() for model in tracked_models}
        self.actor.get_all_permissions()
        with CaptureQueriesContext(connection) as queries:
            build_operations_dashboard(actor=self.actor)
        self.assertLessEqual(len(queries), 20)
        self.assertEqual(
            {model: model.objects.count() for model in tracked_models},
            before,
        )
