import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import InventoryItem
from apps.orders.models import Order, OrderLine
from apps.orders.services import ContactInput, OrderLineInput, create_pending_order
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .models import Commitment, CommitmentEvent
from .services import (
    _base_quantity,
    _create_commitment_for_confirmation,
    list_fifo_commitments,
)


class CommitmentTestCase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku="WTP-COM-001",
            slug="commitment-seedling",
            name="Commitment Seedling",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        self.sale_unit = ProductSaleUnit.objects.create(
            product=self.product,
            name="Tray",
            base_quantity=Decimal("128.000"),
        )
        self.price = ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("250.00"),
            effective_start=timezone.now() - timedelta(days=1),
        )
        self.item = InventoryItem.objects.create(
            product=self.product,
            base_unit="seedling",
        )
        self.actor = get_user_model().objects.create_user(
            username="commitment-actor", password=None, is_staff=True
        )
        self.grant("payments.verify", "commitments.allocate", "commitments.view")

    def grant(self, *permissions):
        for permission_name in permissions:
            app_label, codename = permission_name.split(".", 1)
            self.actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            self.actor.__dict__.pop(cache_name, None)

    def revoke(self, permission_name):
        app_label, codename = permission_name.split(".", 1)
        self.actor.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label=app_label,
                codename=codename,
            )
        )
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            self.actor.__dict__.pop(cache_name, None)

    def create_order(
        self,
        *,
        product=None,
        sale_unit=None,
        quantity=2,
        supply_mode=OrderLine.SupplyMode.READY,
        required_date=None,
    ):
        product = product or self.product
        sale_unit = sale_unit or self.sale_unit
        if supply_mode == OrderLine.SupplyMode.PRE_ORDER and required_date is None:
            required_date = timezone.localdate() + timedelta(days=30)
        return create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            contact=ContactInput("Commitment Buyer", "+254724853914", "buyer@example.com"),
            lines=[
                OrderLineInput(
                    product_id=product.pk,
                    sale_unit_id=sale_unit.pk,
                    quantity=quantity,
                    supply_mode=supply_mode,
                )
            ],
            required_date=required_date,
            creation_idempotency_key=uuid.uuid4(),
        )

    def persist_commitment(
        self,
        order=None,
        *,
        confirmed_at=None,
        idempotency_key=None,
        correlation_id=None,
        actor=None,
        reason="Atomic confirmation commitment",
        source_type="ORDER_CONFIRMATION",
        source_reference=None,
    ):
        order = order or self.create_order()
        line = order.lines.get()
        confirmed_at = confirmed_at or timezone.now()
        idempotency_key = idempotency_key or uuid.uuid4()
        correlation_id = correlation_id or uuid.uuid4()
        source_reference = source_reference or order.order_number
        with transaction.atomic():
            return _create_commitment_for_confirmation(
                order_line_id=line.pk,
                actor=actor or self.actor,
                confirmed_at=confirmed_at,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
                reason=reason,
                source_type=source_type,
                source_reference=source_reference,
            )


class CommitmentPersistenceTests(CommitmentTestCase):
    def test_initial_commitment_event_must_match_creation_facts(self):
        commitment = self.persist_commitment()
        invalid = CommitmentEvent(
            commitment=commitment,
            previous_state=None,
            new_state=Commitment.State.ACTIVE,
            commercial_quantity=commitment.committed_quantity + 1,
            base_quantity=commitment.committed_base_quantity,
            actor=self.actor,
            reason="Invalid initial event",
            source_type="TEST",
            source_reference=commitment.order.order_number,
            correlation_id=commitment.creation_correlation_id,
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            invalid.save(_commitment_service_write=True)

    def test_creation_uses_order_line_snapshots_and_exact_base_conversion(self):
        commitment = self.persist_commitment()
        self.assertIsInstance(commitment.id, uuid.UUID)
        self.assertIsInstance(commitment.fifo_sequence, int)
        self.assertEqual(commitment.order_line.order_id, commitment.order_id)
        self.assertEqual(commitment.inventory_item, self.item)
        self.assertEqual(commitment.committed_quantity, 2)
        self.assertEqual(commitment.base_quantity_per_sale_unit, Decimal("128.000"))
        self.assertEqual(commitment.committed_base_quantity, Decimal("256.000"))
        self.assertEqual(commitment.supplied_base_quantity, Decimal("0"))
        self.assertEqual(commitment.cancelled_base_quantity, Decimal("0"))
        self.assertEqual(commitment.outstanding_base_quantity, Decimal("256.000"))
        self.assertEqual(commitment.state, Commitment.State.ACTIVE)
        self.assertIsNone(commitment.required_date)

    def test_one_commitment_per_line_and_protected_historical_references(self):
        commitment = self.persist_commitment()
        with self.assertRaises(ValidationError):
            self.persist_commitment(order=commitment.order)
        for record in (
            commitment.order_line,
            commitment.order,
            commitment.inventory_item,
            commitment.events.get().actor,
        ):
            with self.subTest(record=type(record).__name__), self.assertRaises(ProtectedError):
                models.QuerySet(model=type(record), using="default").filter(
                    pk=record.pk
                ).delete()

    def test_pending_creation_has_no_commitment_and_no_public_creation_service(self):
        order = self.create_order()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertFalse(Commitment.objects.filter(order=order).exists())
        with self.assertRaises(ValidationError):
            Commitment.objects.create(
                order=order,
                order_line=order.lines.get(),
                inventory_item=self.item,
                committed_quantity=2,
                base_quantity_per_sale_unit=Decimal("128.000"),
                committed_base_quantity=Decimal("256.000"),
                outstanding_quantity=2,
                outstanding_base_quantity=Decimal("256.000"),
                confirmed_at=timezone.now(),
                creation_correlation_id=uuid.uuid4(),
                creation_idempotency_key=uuid.uuid4(),
            )
        import apps.commitments.services as services

        self.assertFalse(hasattr(services, "create_commitment"))
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_preorder_copies_required_date_but_ready_never_does(self):
        required_date = timezone.localdate() + timedelta(days=40)
        preorder = self.create_order(
            supply_mode=OrderLine.SupplyMode.PRE_ORDER,
            required_date=required_date,
        )
        commitment = self.persist_commitment(order=preorder)
        self.assertEqual(commitment.required_date, required_date)
        self.assertIsNone(self.persist_commitment().required_date)


class CommitmentQuantityConstraintTests(CommitmentTestCase):
    def test_database_enforces_commercial_and_base_quantity_equations(self):
        commitment = self.persist_commitment()
        unsafe = models.QuerySet(model=Commitment, using="default").filter(
            fifo_sequence=commitment.fifo_sequence
        )
        for values in (
            {"supplied_quantity": -1, "outstanding_quantity": 3},
            {"cancelled_quantity": -1, "outstanding_quantity": 3},
            {"outstanding_quantity": -1, "supplied_quantity": 3},
            {"supplied_quantity": 3, "outstanding_quantity": 0},
            {"cancelled_quantity": 3, "outstanding_quantity": 0},
            {"supplied_base_quantity": Decimal("257.000"), "outstanding_base_quantity": 0},
            {"cancelled_base_quantity": Decimal("257.000"), "outstanding_base_quantity": 0},
        ):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                unsafe.update(**values)

    def test_database_rejects_negative_base_quantities_and_inexact_conversion(self):
        commitment = self.persist_commitment()
        unsafe = models.QuerySet(model=Commitment, using="default").filter(
            fifo_sequence=commitment.fifo_sequence
        )
        for values in (
            {"supplied_base_quantity": Decimal("-1.000")},
            {"cancelled_base_quantity": Decimal("-1.000")},
            {"outstanding_base_quantity": Decimal("-1.000")},
            {"committed_base_quantity": Decimal("255.000"), "outstanding_base_quantity": Decimal("255.000")},
        ):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                unsafe.update(**values)

    def test_invalid_precision_and_non_finite_quantities_are_rejected(self):
        for quantity in ("0", "-1", "NaN", "1.0001", "1E+30"):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                _base_quantity(quantity)

    def test_state_and_quantity_consistency_is_database_enforced(self):
        commitment = self.persist_commitment()
        unsafe = models.QuerySet(model=Commitment, using="default").filter(
            fifo_sequence=commitment.fifo_sequence
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            unsafe.update(state=Commitment.State.SATISFIED)


class CommitmentFIFOTests(CommitmentTestCase):
    def test_fifo_orders_by_confirmation_time_then_database_sequence(self):
        at = timezone.now()
        later = self.persist_commitment(
            order=self.create_order(), confirmed_at=at + timedelta(seconds=1)
        )
        tied_first = self.persist_commitment(order=self.create_order(), confirmed_at=at)
        tied_second = self.persist_commitment(order=self.create_order(), confirmed_at=at)
        actual = list(
            list_fifo_commitments(
                inventory_item_id=self.item.pk,
                supply_mode=OrderLine.SupplyMode.READY,
                actor=self.actor,
            )
        )
        self.assertEqual(actual, [tied_first, tied_second, later])
        self.assertLess(tied_first.fifo_sequence, tied_second.fifo_sequence)

    def test_fifo_pool_partitions_by_inventory_item_and_supply_mode(self):
        ready = self.persist_commitment()
        preorder = self.persist_commitment(
            order=self.create_order(supply_mode=OrderLine.SupplyMode.PRE_ORDER)
        )
        other_product = Product.objects.create(
            sku="WTP-COM-002",
            slug="other-commitment-item",
            name="Other Commitment Item",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        other_unit = ProductSaleUnit.objects.create(
            product=other_product, name="Seedling", base_quantity=Decimal("1.000")
        )
        ProductPrice.objects.create(
            sale_unit=other_unit,
            amount=Decimal("10.00"),
            effective_start=timezone.now() - timedelta(days=1),
        )
        other_item = InventoryItem.objects.create(product=other_product, base_unit="seedling")
        other = self.persist_commitment(
            order=self.create_order(product=other_product, sale_unit=other_unit)
        )
        ready_pool = list(
            list_fifo_commitments(
                inventory_item_id=self.item.pk,
                supply_mode=OrderLine.SupplyMode.READY,
                actor=self.actor,
            )
        )
        self.assertEqual(ready_pool, [ready])
        self.assertNotIn(preorder, ready_pool)
        self.assertNotIn(other, ready_pool)
        self.assertNotEqual(other.inventory_item, self.item)
        self.assertEqual(other.inventory_item, other_item)

    def test_required_date_does_not_change_fifo_priority(self):
        at = timezone.now()
        earlier_confirmation = self.persist_commitment(
            order=self.create_order(
                supply_mode=OrderLine.SupplyMode.PRE_ORDER,
                required_date=timezone.localdate() + timedelta(days=60),
            ),
            confirmed_at=at,
        )
        later_confirmation = self.persist_commitment(
            order=self.create_order(
                supply_mode=OrderLine.SupplyMode.PRE_ORDER,
                required_date=timezone.localdate() + timedelta(days=10),
            ),
            confirmed_at=at + timedelta(seconds=1),
        )
        self.assertEqual(
            list(
                list_fifo_commitments(
                    inventory_item_id=self.item.pk,
                    supply_mode=OrderLine.SupplyMode.PRE_ORDER,
                    actor=self.actor,
                )
            ),
            [earlier_confirmation, later_confirmation],
        )

    def test_fifo_identity_is_immutable_and_has_no_override_field_or_permission(self):
        commitment = self.persist_commitment()
        commitment.fifo_sequence += 100
        with self.assertRaises(ValidationError):
            commitment.save(_commitment_service_write=True)
        with self.assertRaises(ValidationError):
            Commitment.objects.update(fifo_sequence=999)
        fields = {field.name for field in Commitment._meta.get_fields()}
        self.assertTrue({"priority", "fifo_override", "manual_priority"}.isdisjoint(fields))
        self.assertFalse(
            Permission.objects.filter(
                content_type__app_label="commitments",
                codename__icontains="override",
            ).exists()
        )


class CommitmentHistoryAndIdempotencyTests(CommitmentTestCase):
    def test_creation_appends_complete_immutable_audit_event(self):
        correlation_id = uuid.uuid4()
        idempotency_key = uuid.uuid4()
        commitment = self.persist_commitment(
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            reason="Owner-approved atomic confirmation",
            source_type="PAYMENT_VERIFICATION",
            source_reference="PAY-REF-001",
        )
        event = commitment.events.get()
        self.assertIsNone(event.previous_state)
        self.assertEqual(event.new_state, Commitment.State.ACTIVE)
        self.assertEqual(event.commercial_quantity, commitment.committed_quantity)
        self.assertEqual(event.base_quantity, commitment.committed_base_quantity)
        self.assertEqual(event.actor, self.actor)
        self.assertEqual(event.reason, "Owner-approved atomic confirmation")
        self.assertEqual(event.source_type, "PAYMENT_VERIFICATION")
        self.assertEqual(event.source_reference, "PAY-REF-001")
        self.assertEqual(event.correlation_id, correlation_id)
        self.assertEqual(event.idempotency_key, idempotency_key)
        self.assertIsNotNone(event.created_at)
        with self.assertRaises(ValidationError):
            event.delete()
        with self.assertRaises(ValidationError):
            CommitmentEvent.objects.update(reason="rewritten")

    def test_identical_retry_returns_one_commitment_and_one_event(self):
        order = self.create_order()
        at = timezone.now()
        key = uuid.uuid4()
        correlation = uuid.uuid4()
        first = self.persist_commitment(
            order=order,
            confirmed_at=at,
            idempotency_key=key,
            correlation_id=correlation,
        )
        second = self.persist_commitment(
            order=order,
            confirmed_at=at,
            idempotency_key=key,
            correlation_id=correlation,
        )
        self.assertEqual(first.fifo_sequence, second.fifo_sequence)
        self.assertEqual(Commitment.objects.count(), 1)
        self.assertEqual(CommitmentEvent.objects.count(), 1)

    def test_changed_retry_is_rejected_without_duplicate_history(self):
        order = self.create_order()
        at = timezone.now()
        key = uuid.uuid4()
        correlation = uuid.uuid4()
        self.persist_commitment(
            order=order,
            confirmed_at=at,
            idempotency_key=key,
            correlation_id=correlation,
        )
        with self.assertRaises(ValidationError):
            self.persist_commitment(
                order=order,
                confirmed_at=at,
                idempotency_key=key,
                correlation_id=correlation,
                reason="Changed reason",
            )
        self.assertEqual(Commitment.objects.count(), 1)
        self.assertEqual(CommitmentEvent.objects.count(), 1)

    def test_catalog_changes_do_not_rewrite_commitment_snapshots(self):
        commitment = self.persist_commitment()
        self.product.name = "Renamed Product"
        self.product.save()
        self.sale_unit.name = "Renamed Tray"
        self.sale_unit.base_quantity = Decimal("64.000")
        self.sale_unit.save()
        self.price.effective_end = timezone.now()
        self.price.save()
        ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("999.00"),
            effective_start=self.price.effective_end,
        )
        commitment.refresh_from_db()
        self.assertEqual(commitment.order_line.product_name, "Commitment Seedling")
        self.assertEqual(commitment.order_line.sale_unit_name, "Tray")
        self.assertEqual(commitment.base_quantity_per_sale_unit, Decimal("128.000"))
        self.assertEqual(commitment.committed_base_quantity, Decimal("256.000"))
        self.assertEqual(commitment.order_line.unit_price, Decimal("250.00"))

    def test_product_and_inventory_base_meaning_are_immutable_after_commitment(self):
        self.persist_commitment()
        self.product.base_inventory_unit = "tray"
        with self.assertRaises(ValidationError):
            self.product.save()
        self.item.base_unit = "tray"
        with self.assertRaises(ValidationError):
            self.item.save()


class CommitmentPermissionAndAdminTests(CommitmentTestCase):
    def test_confirmation_persistence_requires_both_ratified_permissions(self):
        order = self.create_order()
        self.revoke("payments.verify")
        with self.assertRaises(PermissionDenied):
            self.persist_commitment(order=order)
        self.grant("payments.verify")
        self.revoke("commitments.allocate")
        with self.assertRaises(PermissionDenied):
            self.persist_commitment(order=order)
        self.assertFalse(Commitment.objects.filter(order=order).exists())

    def test_fifo_projection_requires_view_permission_not_a_role_name(self):
        self.persist_commitment()
        self.revoke("commitments.view")
        self.actor.username = "owner"
        self.actor.save()
        with self.assertRaises(PermissionDenied):
            list_fifo_commitments(
                inventory_item_id=self.item.pk,
                supply_mode=OrderLine.SupplyMode.READY,
                actor=self.actor,
            )

    def test_native_permissions_exist_and_admin_is_view_only(self):
        actual = set(
            Permission.objects.filter(content_type__app_label="commitments").values_list(
                "codename", flat=True
            )
        )
        self.assertTrue({"view", "allocate"} <= actual)
        self.client.force_login(self.actor)
        list_url = reverse("admin:commitments_commitment_changelist")
        self.assertEqual(self.client.get(list_url).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin:commitments_commitment_add")).status_code,
            403,
        )


class CommitmentRegressionBoundaryTests(CommitmentTestCase):
    def test_commitment_models_contain_no_deferred_domain_fields(self):
        # Later phases may add authorized reverse relations without adding
        # deferred-domain columns to the Commitment persistence boundary.
        fields = {field.name for field in Commitment._meta.fields}
        self.assertTrue(
            {
                "reservation",
                "allocation",
                "location",
                "lot",
                "branch",
                "production",
                "fulfillment",
                "payment",
                "availability",
            }.isdisjoint(fields)
        )

    def test_no_demo_commitments_or_fabricated_availability_exist(self):
        self.assertEqual(Commitment.objects.count(), 0)
        self.assertEqual(CommitmentEvent.objects.count(), 0)
        self.assertFalse(hasattr(Commitment, "available_quantity"))


class CommitmentOuterTransactionBoundaryTests(TransactionTestCase):
    def test_internal_creation_requires_an_existing_outer_transaction(self):
        with self.assertRaises(ValidationError):
            _create_commitment_for_confirmation(
                order_line_id=uuid.uuid4(),
                actor=None,
                confirmed_at=timezone.now(),
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
                reason="Confirmation",
                source_type="ORDER_CONFIRMATION",
                source_reference="TEST",
            )
