import threading
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, tag

from .models import Product, ProductSkuSequence
from .services import create_seedling_product


@tag("postgresql_concurrency")
@skipUnless(connection.vendor == "postgresql", "PostgreSQL concurrency evidence requires PostgreSQL.")
class PostgreSQLProductSkuConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            "product-pg-manager", "products-pg@example.com", "test"
        )
        ProductSkuSequence.objects.bulk_create(
            ProductSkuSequence(category=category) for category in Product.Category.values
        )

    def _create(self, name):
        actor = get_user_model().objects.get(pk=self.actor.pk)
        return create_seedling_product(
            name=name,
            category=Product.Category.VEGETABLE,
            description="Concurrent Product",
            base_inventory_unit="seedling",
            is_active=True,
            is_published=False,
            sale_unit_name="Individual seedling",
            sale_unit_base_quantity=Decimal("1.000"),
            price_amount=None,
            price_effective_start=None,
            actor=actor,
        )[0]

    def test_concurrent_creates_receive_distinct_sequential_skus(self):
        barrier = threading.Barrier(2)
        results = []
        errors = []
        mutex = threading.Lock()

        def worker(name):
            close_old_connections()
            try:
                barrier.wait()
                product = self._create(name)
                with mutex:
                    results.append(product.sku)
            except Exception as error:
                with mutex:
                    errors.append(error)
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=worker, args=("Concurrent A",)),
            threading.Thread(target=worker, args=("Concurrent B",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(sorted(results), ["WTP-VEG-001", "WTP-VEG-002"])
