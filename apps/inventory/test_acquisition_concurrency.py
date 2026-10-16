import threading
import uuid
from datetime import date
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, tag

from apps.products.models import Product
from .acquisitions import acquire_external_stock
from .models import ExternalStockAcquisition, InventoryLocation, InventoryMovement, StockLot


@tag("postgresql_concurrency")
@skipUnless(connection.vendor == "postgresql", "PostgreSQL concurrency evidence requires PostgreSQL.")
class AcquisitionConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser("lot-concurrency", "lots@example.com", "test")
        self.product = Product.objects.create(name="Concurrent seedlings", sku="CONCURRENT-LOT", slug="concurrent-lot",
                                              category="VEG", base_inventory_unit="seedling")
        self.location = InventoryLocation.objects.create(name="Test site", code="CONCURRENT-SITE")

    def concurrent(self, keys):
        barrier = threading.Barrier(2)
        results, errors = [], []
        correlation = uuid.uuid4()

        def worker(key):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                barrier.wait(timeout=10)
                acquisition = acquire_external_stock(
                    product_id=self.product.pk, quantity="1.000", unit_cost="2.00",
                    acquisition_date=date(2026, 9, 9), location_id=self.location.pk,
                    condition="SALEABLE", actor=actor, correlation_id=correlation, idempotency_key=key,
                )
                results.append(acquisition.movement_line.lot.lot_code)
            except Exception as error:
                errors.append(error)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=worker, args=(key,)) for key in keys]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        return results

    def test_distinct_concurrent_acquisitions_have_distinct_lots(self):
        self.assertEqual(len(set(self.concurrent([uuid.uuid4(), uuid.uuid4()]))), 2)
        self.assertEqual(StockLot.objects.count(), 2)
        self.assertEqual(InventoryMovement.objects.count(), 2)

    def test_concurrent_retry_posts_only_one_lot_and_receipt(self):
        key = uuid.uuid4()
        self.assertEqual(len(set(self.concurrent([key, key]))), 1)
        self.assertEqual(StockLot.objects.count(), 1)
        self.assertEqual(ExternalStockAcquisition.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 1)
