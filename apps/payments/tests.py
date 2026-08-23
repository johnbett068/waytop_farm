import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order, OrderLine
from apps.orders.services import ContactInput, OrderLineInput, create_pending_order
from apps.products.models import Product, ProductPrice, ProductSaleUnit

from .models import Payment, PaymentEvidence, PaymentStatusEvent, PaymentVerificationAttempt
from .services import record_rejected_verification_attempt, submit_payment_evidence


class PaymentFoundationTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku="WTP-PAY-001",
            slug="payment-product",
            name="Payment Product",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=True,
        )
        self.sale_unit = ProductSaleUnit.objects.create(
            product=self.product, name="Individual", base_quantity=1
        )
        ProductPrice.objects.create(
            sale_unit=self.sale_unit,
            amount=Decimal("75.25"),
            effective_start=timezone.now() - timedelta(hours=1),
        )

    def create_order(self):
        return create_pending_order(
            channel=Order.Channel.ECOMMERCE,
            fulfillment_method=Order.FulfillmentMethod.CUSTOMER_COLLECTION,
            lines=[
                OrderLineInput(
                    product_id=self.product.id,
                    sale_unit_id=self.sale_unit.id,
                    quantity=2,
                    supply_mode=OrderLine.SupplyMode.READY,
                )
            ],
            creation_idempotency_key=uuid.uuid4(),
            contact=ContactInput(name="Payment Buyer", phone="0724 853 914"),
        )

    def grant(self, user, app_label, codename):
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
        for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            user.__dict__.pop(cache_name, None)

    def test_order_creation_creates_one_full_pending_mpesa_payment(self):
        order = self.create_order()
        payment = order.payment
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(payment.amount, Decimal("150.50"))
        self.assertEqual(payment.amount, order.total_amount)
        self.assertEqual(payment.currency, Payment.Currency.KES)
        self.assertEqual(payment.method, Payment.Method.MPESA)
        self.assertEqual(payment.state, Payment.State.PENDING)
        self.assertIsNone(payment.provider_reference)
        self.assertIsNone(payment.verified_by)
        self.assertIsNone(payment.verified_at)

    def test_rejected_verification_attempt_requires_authorized_service(self):
        order = self.create_order()
        evidence = PaymentEvidence.objects.create(
            payment=order.payment,
            reference_claim="UNTRUSTED",
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
        )
        actor = get_user_model().objects.create_user(
            username="attempt-bypass", password=None, is_staff=True
        )
        attempt = PaymentVerificationAttempt(
            payment=order.payment,
            evidence=evidence,
            actor=actor,
            outcome=PaymentVerificationAttempt.Outcome.REJECTED,
            reason="Direct bypass",
            idempotency_key=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            attempt.save()
        self.assertFalse(PaymentVerificationAttempt.objects.exists())

    def test_customer_evidence_is_append_only_and_raw_message_is_encrypted_at_rest(self):
        payment = self.create_order().payment
        raw_message = "QAB12C3D4E Confirmed. Ksh150.50 paid to WayTop."
        evidence = submit_payment_evidence(
            payment=payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim=" QAB12C3D4E ",
            submitted_message=f"  {raw_message}  ",
        )
        self.assertEqual(evidence.reference_claim, "QAB12C3D4E")
        self.assertEqual(evidence.submitted_message, raw_message)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT submitted_message FROM payments_paymentevidence WHERE id = %s",
                [evidence.id.hex],
            )
            stored = cursor.fetchone()[0]
        self.assertTrue(stored.startswith("fernet$"))
        self.assertNotIn(raw_message, stored)
        evidence.reference_claim = "CHANGED"
        with self.assertRaises(ValidationError):
            evidence.save()
        with self.assertRaises(ValidationError):
            evidence.delete()

    def test_multiple_and_duplicate_unverified_evidence_submissions_are_retained(self):
        payment = self.create_order().payment
        first = submit_payment_evidence(
            payment=payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim="QAB12C3D4E",
        )
        second = submit_payment_evidence(
            payment=payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim="QAB12C3D4E",
        )
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(payment.evidence.count(), 2)
        self.assertEqual(payment.state, Payment.State.PENDING)

    def test_empty_evidence_is_rejected(self):
        payment = self.create_order().payment
        with self.assertRaises(ValidationError):
            submit_payment_evidence(
                payment=payment,
                submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            )

    def test_pos_and_staff_evidence_sources_enforce_native_permissions(self):
        payment = self.create_order().payment
        actor = get_user_model().objects.create_user(
            username="evidence-staff", password="safe-password", is_staff=True
        )
        with self.assertRaises(PermissionDenied):
            submit_payment_evidence(
                payment=payment,
                submission_source=PaymentEvidence.SubmissionSource.POS,
                reference_claim="POSREF",
                actor=actor,
            )
        self.grant(actor, "pos", "process_sale")
        submit_payment_evidence(
            payment=payment,
            submission_source=PaymentEvidence.SubmissionSource.POS,
            reference_claim="POSREF",
            actor=actor,
        )
        with self.assertRaises(PermissionDenied):
            submit_payment_evidence(
                payment=payment,
                submission_source=PaymentEvidence.SubmissionSource.STAFF,
                reference_claim="STAFFREF",
                actor=actor,
            )
        self.grant(actor, "payments", "verify")
        submit_payment_evidence(
            payment=payment,
            submission_source=PaymentEvidence.SubmissionSource.STAFF,
            reference_claim="STAFFREF",
            actor=actor,
        )

    def test_rejected_verification_is_authorized_audited_and_idempotent(self):
        payment = self.create_order().payment
        evidence = submit_payment_evidence(
            payment=payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim="UNMATCHED",
        )
        verifier = get_user_model().objects.create_user(
            username="verifier", password="safe-password", is_staff=True
        )
        key = uuid.uuid4()
        with self.assertRaises(PermissionDenied):
            record_rejected_verification_attempt(
                payment=payment,
                evidence=evidence,
                actor=verifier,
                reason="Reference does not belong to this Order",
                idempotency_key=key,
            )
        self.grant(verifier, "payments", "verify")
        first = record_rejected_verification_attempt(
            payment=payment,
            evidence=evidence,
            actor=verifier,
            reason="Reference does not belong to this Order",
            idempotency_key=key,
        )
        second = record_rejected_verification_attempt(
            payment=payment,
            evidence=evidence,
            actor=verifier,
            reason="Reference does not belong to this Order",
            idempotency_key=key,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.outcome, PaymentVerificationAttempt.Outcome.REJECTED)
        payment.refresh_from_db()
        self.assertEqual(payment.state, Payment.State.PENDING)
        self.assertEqual(payment.order.status, Order.Status.PENDING)

    def test_approved_verification_and_confirmed_events_are_unavailable(self):
        payment = self.create_order().payment
        evidence = submit_payment_evidence(
            payment=payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim="QAB12C3D4E",
        )
        verifier = get_user_model().objects.create_user(username="verifier", password="safe-password")
        with self.assertRaises(ValidationError):
            PaymentVerificationAttempt.objects.create(
                payment=payment,
                evidence=evidence,
                actor=verifier,
                outcome=PaymentVerificationAttempt.Outcome.APPROVED,
                reason="Would otherwise verify",
                idempotency_key=uuid.uuid4(),
            )
        with self.assertRaises(ValidationError):
            PaymentStatusEvent.objects.create(
                payment=payment,
                previous_state=Payment.State.PENDING,
                new_state=Payment.State.CONFIRMED,
                actor=verifier,
                idempotency_key=uuid.uuid4(),
            )
        payment.state = Payment.State.CONFIRMED
        with self.assertRaises(ValidationError):
            payment.save()

    def test_database_prevents_reuse_of_a_confirmed_provider_reference(self):
        first = self.create_order().payment
        second = self.create_order().payment
        verifier = get_user_model().objects.create_user(username="db-verifier", password="safe-password")
        confirmed_at = timezone.now()
        models.QuerySet(model=Payment, using="default").filter(pk=first.pk).update(
            state=Payment.State.CONFIRMED,
            provider_reference="QAB12C3D4E",
            verified_by=verifier,
            verified_at=confirmed_at,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet(model=Payment, using="default").filter(pk=second.pk).update(
                state=Payment.State.CONFIRMED,
                provider_reference="QAB12C3D4E",
                verified_by=verifier,
                verified_at=confirmed_at,
            )

    def test_payment_amount_and_confirmation_metadata_constraints_are_enforced(self):
        payment = self.create_order().payment
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet(model=Payment, using="default").filter(pk=payment.pk).update(amount=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.QuerySet(model=Payment, using="default").filter(pk=payment.pk).update(
                state=Payment.State.CONFIRMED
            )

    def test_raw_evidence_is_not_exposed_in_admin_or_public_payment_page(self):
        payment = self.create_order().payment
        raw_message = "QAB12C3D4E private M-Pesa message"
        evidence = submit_payment_evidence(
            payment=payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            submitted_message=raw_message,
        )
        public = self.client.get(reverse("payments:payment"))
        self.assertNotContains(public, raw_message)

        superuser = get_user_model().objects.create_superuser(
            username="payment-admin", password="safe-password"
        )
        self.client.force_login(superuser)
        detail = self.client.get(reverse("admin:payments_paymentevidence_change", args=(evidence.pk,)))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, raw_message)
        self.assertContains(detail, "Raw message stored securely")

    @override_settings(
        DEBUG=False,
        PAYMENT_EVIDENCE_ENCRYPTION_KEYS=[],
        PAYMENT_EVIDENCE_ALLOW_DEVELOPMENT_FALLBACK=False,
    )
    def test_production_cannot_use_the_development_evidence_key_fallback(self):
        field = PaymentEvidence._meta.get_field("submitted_message")
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "Production requires PAYMENT_EVIDENCE_ENCRYPTION_KEYS.",
        ):
            field.get_prep_value("sensitive payment evidence")

    def test_payment_evidence_admin_requires_verify_permission(self):
        evidence = submit_payment_evidence(
            payment=self.create_order().payment,
            submission_source=PaymentEvidence.SubmissionSource.ECOMMERCE,
            reference_claim="QAB12C3D4E",
        )
        staff = get_user_model().objects.create_user(
            username="ordinary-admin", password="safe-password", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.get(
            reverse("admin:payments_paymentevidence_change", args=(evidence.pk,))
        )
        self.assertEqual(response.status_code, 403)

    def test_ratified_payment_permission_exists(self):
        self.assertTrue(
            Permission.objects.filter(
                content_type__app_label="payments", codename="verify"
            ).exists()
        )
