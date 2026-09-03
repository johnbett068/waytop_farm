import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.inventory.models import InventoryMovement, Reservation, StockPosition
from apps.products.models import Product

from .models import (
    NurseryActivity,
    ProductionBatch,
    ProductionBatchEvent,
    ProductionLabour,
    ProductionPurchase,
)
from .services import (
    create_batch,
    record_activity,
    record_labour,
    record_purchase,
    transition_batch,
    update_batch,
)


class ProductionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_user(
            username="production-operator", password="test-password", is_staff=True
        )
        cls.unauthorized = get_user_model().objects.create_user(
            username="production-observer", password="test-password", is_staff=True
        )
        cls.inactive = get_user_model().objects.create_user(
            username="inactive-production", password="test-password", is_staff=True, is_active=False
        )
        cls.product = Product.objects.create(
            sku="WTP-SEEDLING-001",
            slug="test-seedling",
            name="Test Seedling",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=False,
        )
        for codename in (
            "view_operations",
            "manage_batches",
            "record_purchases",
            "record_labour",
            "record_activities",
        ):
            cls.actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="production", codename=codename
                )
            )

    def batch_values(self, **overrides):
        values = {
            "batch_number": "PB-TEST-001",
            "product_id": self.product.pk,
            "start_date": date(2026, 8, 1),
            "expected_ready_date": date(2026, 9, 1),
            "quantity_started": Decimal("100.000"),
            "notes": "Simple nursery batch",
            "actor": self.actor,
            "correlation_id": uuid.uuid4(),
            "idempotency_key": uuid.uuid4(),
        }
        values.update(overrides)
        return values

    def create_batch(self, **overrides):
        return create_batch(**self.batch_values(**overrides))

    def transition(self, batch, status, **overrides):
        values = {
            "batch_id": batch.pk,
            "to_status": status,
            "reason": f"Move to {status}",
            "actor": self.actor,
            "correlation_id": uuid.uuid4(),
            "idempotency_key": uuid.uuid4(),
        }
        values.update(overrides)
        return transition_batch(**values)


class BatchServiceTests(ProductionTestCase):
    def test_create_batch_uses_active_product_and_appends_initial_history(self):
        batch = self.create_batch()
        self.assertEqual(batch.status, ProductionBatch.Status.PLANNED)
        self.assertEqual(batch.current_quantity, Decimal("100.000"))
        self.assertEqual(batch.product, self.product)
        event = batch.history.get()
        self.assertEqual(event.operation, ProductionBatchEvent.Operation.CREATED)
        self.assertEqual(event.actor, self.actor)

    def test_inactive_product_and_invalid_dates_or_quantities_are_rejected_atomically(self):
        self.product.is_active = False
        self.product.save()
        with self.assertRaises(ValidationError):
            self.create_batch()
        self.assertEqual(ProductionBatch.objects.count(), 0)
        self.assertEqual(ProductionBatchEvent.objects.count(), 0)
        self.product.is_active = True
        self.product.save()
        for overrides in (
            {"quantity_started": Decimal("0")},
            {"quantity_started": Decimal("-1")},
            {"expected_ready_date": date(2026, 7, 31)},
            {"quantity_started": Decimal("1.0001")},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                self.create_batch(**overrides)
        self.assertEqual(ProductionBatch.objects.count(), 0)

    def test_creation_is_idempotent_and_changed_input_is_rejected(self):
        key = uuid.uuid4()
        correlation = uuid.uuid4()
        first = self.create_batch(idempotency_key=key, correlation_id=correlation)
        retry = self.create_batch(idempotency_key=key, correlation_id=correlation)
        self.assertEqual(retry.pk, first.pk)
        self.assertEqual(ProductionBatch.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.create_batch(
                idempotency_key=key,
                correlation_id=correlation,
                quantity_started=Decimal("99.000"),
            )

    def test_permission_requires_authenticated_active_staff_with_exact_capability(self):
        for actor in (None, self.unauthorized, self.inactive):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                self.create_batch(actor=actor)
        superuser = get_user_model().objects.create_superuser("production-superuser", password=None)
        batch = self.create_batch(actor=superuser)
        self.assertEqual(batch.created_by, superuser)

    def test_lifecycle_accepts_only_planned_to_active_to_ready_to_closed(self):
        batch = self.create_batch()
        for status in (
            ProductionBatch.Status.IN_PRODUCTION,
            ProductionBatch.Status.READY,
            ProductionBatch.Status.CLOSED,
        ):
            self.transition(batch, status)
            batch.refresh_from_db()
            self.assertEqual(batch.status, status)
        self.assertEqual(batch.history.count(), 4)
        with self.assertRaises(ValidationError):
            self.transition(batch, ProductionBatch.Status.PLANNED)

    def test_invalid_skips_backward_moves_and_ready_with_zero_are_rejected(self):
        batch = self.create_batch()
        with self.assertRaises(ValidationError):
            self.transition(batch, ProductionBatch.Status.READY)
        self.transition(batch, ProductionBatch.Status.IN_PRODUCTION)
        with self.assertRaises(ValidationError):
            self.transition(batch, ProductionBatch.Status.PLANNED)
        update_batch(
            batch_id=batch.pk,
            current_quantity=Decimal("0.000"),
            expected_ready_date=batch.expected_ready_date,
            notes=batch.notes,
            reason="All seedlings lost",
            actor=self.actor,
            correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            self.transition(batch, ProductionBatch.Status.READY)

    def test_update_allows_only_decrease_and_records_immutable_event(self):
        batch = self.create_batch()
        key = uuid.uuid4()
        correlation = uuid.uuid4()
        values = {
            "batch_id": batch.pk,
            "current_quantity": Decimal("92.000"),
            "expected_ready_date": batch.expected_ready_date + timedelta(days=2),
            "notes": "Eight operational losses",
            "reason": "Counted nursery losses",
            "actor": self.actor,
            "correlation_id": correlation,
            "idempotency_key": key,
        }
        updated = update_batch(**values)
        self.assertEqual(updated.current_quantity, Decimal("92.000"))
        retry = update_batch(**values)
        self.assertEqual(retry.pk, updated.pk)
        event = updated.history.filter(operation=ProductionBatchEvent.Operation.UPDATED).get()
        self.assertEqual(event.previous_quantity, Decimal("100.000"))
        self.assertEqual(event.current_quantity, Decimal("92.000"))
        with self.assertRaises(ValidationError):
            update_batch(**{**values, "idempotency_key": uuid.uuid4(), "current_quantity": Decimal("93")})
        with self.assertRaises(ValidationError):
            event.reason = "Rewritten"
            event.save()


class OperationalRecordServiceTests(ProductionTestCase):
    def setUp(self):
        self.batch = self.create_batch()

    def test_purchase_is_immutable_calculated_and_may_have_optional_batch(self):
        values = {
            "purchase_date": date(2026, 8, 2),
            "supplier": "Nursery Input Shop",
            "item_description": "Growing media",
            "category": ProductionPurchase.Category.GROWING_MEDIA,
            "quantity": Decimal("2.555"),
            "unit": "bags",
            "unit_cost": Decimal("1.00"),
            "batch_id": self.batch.pk,
            "reference": "REC-1",
            "notes": "For nursery use",
            "actor": self.actor,
            "correlation_id": uuid.uuid4(),
            "idempotency_key": uuid.uuid4(),
        }
        record = record_purchase(**values)
        self.assertEqual(record.total_cost, Decimal("2.56"))
        self.assertEqual(record.batch, self.batch)
        self.assertEqual(record_purchase(**values).pk, record.pk)
        standalone = record_purchase(**{**values, "batch_id": None, "idempotency_key": uuid.uuid4(), "correlation_id": uuid.uuid4(), "reference": "REC-2"})
        self.assertIsNone(standalone.batch)
        with self.assertRaises(ValidationError):
            record.supplier = "Changed"
            record.save()

    def test_labour_is_calculated_without_payroll_and_optional_batch_is_supported(self):
        values = {
            "work_date": date(2026, 8, 3),
            "worker": "Nursery Team A",
            "activity": "Pricking out",
            "effort_quantity": Decimal("1.25"),
            "effort_unit": ProductionLabour.EffortUnit.HOURS,
            "rate": Decimal("100.00"),
            "batch_id": self.batch.pk,
            "notes": "Operational record only",
            "actor": self.actor,
            "correlation_id": uuid.uuid4(),
            "idempotency_key": uuid.uuid4(),
        }
        labour = record_labour(**values)
        self.assertEqual(labour.total_cost, Decimal("125.00"))
        self.assertEqual(labour.batch, self.batch)
        standalone = record_labour(**{**values, "batch_id": None, "idempotency_key": uuid.uuid4(), "correlation_id": uuid.uuid4()})
        self.assertIsNone(standalone.batch)

    def test_nursery_activity_types_cover_authorized_work_and_are_optional_batch_records(self):
        selected = (
            NurseryActivity.Type.WATERING,
            NurseryActivity.Type.WEEDING,
            NurseryActivity.Type.PEST_MANAGEMENT,
            NurseryActivity.Type.DISEASE_MANAGEMENT,
            NurseryActivity.Type.FERTILIZING,
        )
        for activity_type in selected:
            record = record_activity(
                activity_date=date(2026, 8, 4),
                activity_type=activity_type,
                batch_id=self.batch.pk,
                description=f"Recorded {activity_type.lower()}",
                coverage_quantity=Decimal("50.000"),
                coverage_unit="seedlings",
                person_or_team="Nursery Team",
                cost=Decimal("25.00"),
                notes="Observed facts only",
                actor=self.actor,
                correlation_id=uuid.uuid4(),
                idempotency_key=uuid.uuid4(),
            )
            self.assertEqual(record.batch, self.batch)
        standalone = record_activity(
            activity_date=date(2026, 8, 4), activity_type=NurseryActivity.Type.CLEANING,
            batch_id=None, description="Cleaned shared nursery area", coverage_quantity=None,
            coverage_unit="", person_or_team="Nursery Team", cost=None, notes="",
            actor=self.actor, correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        self.assertIsNone(standalone.batch)

    def test_negative_cost_quantity_effort_and_incomplete_coverage_are_rejected(self):
        with self.assertRaises(ValidationError):
            record_purchase(
                purchase_date=date.today(), supplier="Supplier", item_description="Seeds",
                category=ProductionPurchase.Category.SEEDS, quantity=-1, unit="packet", unit_cost=1,
                batch_id=None, reference="", notes="", actor=self.actor,
                correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
            )
        with self.assertRaises(ValidationError):
            record_labour(
                work_date=date.today(), worker="Team", activity="Water", effort_quantity=1,
                effort_unit=ProductionLabour.EffortUnit.HOURS, rate=-1, batch_id=None, notes="",
                actor=self.actor, correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
            )
        with self.assertRaises(ValidationError):
            record_activity(
                activity_date=date.today(), activity_type=NurseryActivity.Type.WATERING,
                batch_id=None, description="Watered", coverage_quantity=1, coverage_unit="",
                person_or_team="", cost=None, notes="", actor=self.actor,
                correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
            )

    def test_each_command_requires_its_exact_permission(self):
        base = {
            "purchase_date": date.today(), "supplier": "Supplier", "item_description": "Seeds",
            "category": ProductionPurchase.Category.SEEDS, "quantity": 1, "unit": "packet",
            "unit_cost": 1, "batch_id": None, "reference": "", "notes": "",
            "actor": self.unauthorized, "correlation_id": uuid.uuid4(), "idempotency_key": uuid.uuid4(),
        }
        with self.assertRaises(PermissionDenied):
            record_purchase(**base)

    def test_production_operations_never_mutate_inventory(self):
        before = (
            StockPosition.objects.count(), InventoryMovement.objects.count(), Reservation.objects.count()
        )
        self.transition(self.batch, ProductionBatch.Status.IN_PRODUCTION)
        self.transition(self.batch, ProductionBatch.Status.READY)
        record_purchase(
            purchase_date=date.today(), supplier="Supplier", item_description="Seeds",
            category=ProductionPurchase.Category.SEEDS, quantity=1, unit="packet", unit_cost=10,
            batch_id=self.batch.pk, reference="", notes="", actor=self.actor,
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        after = (
            StockPosition.objects.count(), InventoryMovement.objects.count(), Reservation.objects.count()
        )
        self.assertEqual(after, before)

    def test_closed_batch_cannot_receive_new_operational_records(self):
        self.transition(self.batch, ProductionBatch.Status.IN_PRODUCTION)
        self.transition(self.batch, ProductionBatch.Status.READY)
        self.transition(self.batch, ProductionBatch.Status.CLOSED)
        with self.assertRaises(ValidationError):
            record_purchase(
                purchase_date=date.today(), supplier="Supplier", item_description="Seeds",
                category=ProductionPurchase.Category.SEEDS, quantity=1, unit="packet", unit_cost=10,
                batch_id=self.batch.pk, reference="", notes="", actor=self.actor,
                correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
            )


class ProductionStaffUITests(ProductionTestCase):
    def setUp(self):
        self.client.force_login(self.actor)

    def test_empty_dashboard_is_truthful_and_exposes_authorized_creation_actions(self):
        response = self.client.get(reverse("dashboard:production"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No active batches")
        self.assertContains(response, "+ New Batch")
        self.assertContains(response, "+ Record Purchase")
        self.assertNotContains(response, "PB-AVO-2606-02")

    def test_dashboard_and_mutation_forms_enforce_capabilities(self):
        self.client.force_login(self.unauthorized)
        self.assertEqual(self.client.get(reverse("dashboard:production")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:production_batch_create")).status_code, 403)
        self.client.logout()
        response = self.client.get(reverse("dashboard:production"))
        self.assertEqual(response.status_code, 302)

    def test_create_form_detail_and_related_history_are_operational(self):
        response = self.client.post(reverse("dashboard:production_batch_create"), {
            "batch_number": "PB-UI-001",
            "product": str(self.product.pk),
            "start_date": "2026-08-01",
            "expected_ready_date": "2026-09-01",
            "quantity_started": "64.000",
            "notes": "UI batch",
            "correlation_id": str(uuid.uuid4()),
            "idempotency_key": str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 302)
        batch = ProductionBatch.objects.get(batch_number="PB-UI-001")
        detail = self.client.get(
            reverse("dashboard:production_batch_detail", args=(batch.batch_number,))
        )
        self.assertContains(detail, "PB-UI-001")
        self.assertContains(detail, "Test Seedling")
        self.assertContains(detail, "Batch created")

    def test_batch_list_and_unknown_detail(self):
        self.create_batch()
        response = self.client.get(reverse("dashboard:production_batches"))
        self.assertContains(response, "PB-TEST-001")
        missing = self.client.get(
            reverse("dashboard:production_batch_detail", args=("UNKNOWN",))
        )
        self.assertEqual(missing.status_code, 404)

    def test_purchase_labour_and_activity_forms_record_optional_batch_relationships(self):
        batch = self.create_batch(batch_number="PB-UI-RELATED")
        common = lambda: {
            "batch": str(batch.pk),
            "correlation_id": str(uuid.uuid4()),
            "idempotency_key": str(uuid.uuid4()),
        }
        purchase = self.client.post(reverse("dashboard:production_purchase_create"), {
            **common(), "purchase_date": "2026-08-05", "supplier": "Input Supplier",
            "item_description": "Nursery trays", "category": ProductionPurchase.Category.NURSERY_TRAYS,
            "quantity": "2.000", "unit": "trays", "unit_cost": "500.00",
            "reference": "R-1", "notes": "",
        })
        self.assertEqual(purchase.status_code, 302)
        labour = self.client.post(reverse("dashboard:production_labour_create"), {
            **common(), "work_date": "2026-08-05", "worker": "Nursery Team",
            "activity": "Pricking out", "effort_quantity": "2.00",
            "effort_unit": ProductionLabour.EffortUnit.HOURS, "rate": "100.00", "notes": "",
        })
        self.assertEqual(labour.status_code, 302)
        activity = self.client.post(reverse("dashboard:production_activity_create"), {
            **common(), "activity_date": "2026-08-05",
            "activity_type": NurseryActivity.Type.WATERING, "description": "Watered seedlings",
            "coverage_quantity": "50.000", "coverage_unit": "seedlings",
            "person_or_team": "Nursery Team", "cost": "0.00", "notes": "",
        })
        self.assertEqual(activity.status_code, 302)
        self.assertEqual(batch.purchases.count(), 1)
        self.assertEqual(batch.labour_records.count(), 1)
        self.assertEqual(batch.activities.count(), 1)

    def test_staff_form_drives_controlled_transition_and_quantity_update(self):
        batch = self.create_batch(batch_number="PB-UI-LIFECYCLE")
        transition = self.client.post(
            reverse("dashboard:production_batch_transition", args=(batch.batch_number,)),
            {
                "to_status": ProductionBatch.Status.IN_PRODUCTION,
                "reason": "Nursery work started",
                "correlation_id": str(uuid.uuid4()),
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(transition.status_code, 302)
        update = self.client.post(
            reverse("dashboard:production_batch_update", args=(batch.batch_number,)),
            {
                "current_quantity": "95.000",
                "expected_ready_date": "2026-09-03",
                "notes": "Five losses counted",
                "reason": "Nursery count",
                "correlation_id": str(uuid.uuid4()),
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        self.assertEqual(update.status_code, 302)
        batch.refresh_from_db()
        self.assertEqual(batch.status, ProductionBatch.Status.IN_PRODUCTION)
        self.assertEqual(batch.current_quantity, Decimal("95.000"))

    def test_no_customer_facing_production_route_exists(self):
        self.client.logout()
        self.assertEqual(self.client.get("/production/").status_code, 404)
