import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import OperationalError, close_old_connections
from django.test import TransactionTestCase

from apps.commitments.models import Commitment
from apps.dashboard import test_pos_bookings as fixtures
from apps.orders.models import Order
from apps.orders.services import OrderLineInput
from apps.payments.models import Payment
from apps.payments.pos import checkout_pos
from apps.production.capacity import remaining_capacity


class BookingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        fixtures.POSBookingTests.setUpTestData.__func__(fixtures.POSBookingTests)
        self.actor = fixtures.POSBookingTests.actor
        self.batch = fixtures.POSBookingTests.batch
        self.location = fixtures.POSBookingTests.bomet
        self.unit = fixtures.POSBookingTests.unit

    def attempt(self, quantity, key, barrier=None):
        close_old_connections()
        try:
            if barrier:
                barrier.wait(timeout=10)
            order = checkout_pos(
                lines=[OrderLineInput(self.batch.product_id, self.unit.pk, quantity, "PRE_ORDER", self.batch.pk)],
                location_id=self.location.pk, customer=None, method="CASH", reference="",
                actor=self.actor, idempotency_key=key, activity="bookings",
            )
            return str(order.pk)
        except (ValidationError, OperationalError) as error:
            return error
        finally:
            close_old_connections()

    def test_two_cashiers_cannot_oversubscribe_and_rejected_sqlite_writes_can_retry(self):
        keys = (uuid.uuid4(), uuid.uuid4())
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.attempt, quantity, key, barrier) for quantity, key in zip((2000, 2001), keys)]
            results = [future.result(timeout=30) for future in futures]
        # SQLite rejects contending writers; retry those whole atomic commands.
        for i, result in enumerate(results):
            if isinstance(result, OperationalError):
                results[i] = self.attempt((2000, 2001)[i], keys[i])
        self.assertEqual(sum(isinstance(result, str) for result in results), 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Payment.objects.filter(state="CONFIRMED").count(), 1)
        self.assertEqual(Commitment.objects.count(), 1)
        self.assertGreaterEqual(remaining_capacity(self.batch), Decimal("0"))

    def test_concurrent_same_key_creates_one_booking_payment_and_commitment(self):
        key = uuid.uuid4()
        barrier = threading.Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.attempt, 1000, key, barrier) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        results = [self.attempt(1000, key) if isinstance(value, OperationalError) else value for value in results]
        self.assertTrue(all(isinstance(value, str) for value in results), results)
        self.assertEqual(results[0], results[1])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Commitment.objects.count(), 1)
        self.assertEqual(remaining_capacity(self.batch), Decimal("2500.000"))
