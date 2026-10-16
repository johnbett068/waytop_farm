from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from apps.inventory.models import InventoryItem, StockPosition
from .models import Product, ProductSaleUnit, ProductPrice
from .readiness import product_readiness
from .services import edit_product, add_product_price


class ReadinessTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser("configuration", "configuration@example.com", "test")
        self.product = Product.objects.create(name="Tomato Seedling", sku="LEGACY", slug="original", category="VEG", base_inventory_unit="seedling", is_published=True)
        self.unit = ProductSaleUnit.objects.create(product=self.product, name="Individual seedling", base_quantity=Decimal("5.000"))
        self.item = InventoryItem.objects.create(product=self.product, base_unit="seedling")
        self.at = timezone.now()
        self.client.force_login(self.actor)

    def price(self, **overrides):
        values = dict(sale_unit_id=self.unit.pk, actor=self.actor, amount=Decimal("25.50"), effective_start=self.at-timedelta(days=1))
        values.update(overrides)
        return add_product_price(**values)

    def status(self):
        return product_readiness(Product.objects.get(pk=self.product.pk), at=self.at)

    def test_ready_with_no_stock_and_preserved_conversion(self):
        self.price()
        self.assertTrue(self.status()["ready"])
        self.assertFalse(StockPosition.objects.exists())
        response = self.client.get(reverse("dashboard:catalog_product_detail", args=[self.product.pk]))
        self.assertContains(response, "POS Ready")
        self.assertContains(response, "5.000 seedling")

    def test_unpublished_and_inactive_reasons(self):
        self.price()
        self.product.is_published = False
        self.product.is_active = False
        self.product.save()
        self.assertFalse(self.status()["ready"])
        self.assertIn("Not published", self.status()["reasons"])
        self.assertIn("Product is inactive", self.status()["reasons"])

    def test_missing_price(self):
        self.assertFalse(self.status()["ready"])
        self.assertIn("Price not configured", self.status()["units"][0]["reasons"])

    def test_expired_price(self):
        self.price(effective_end=self.at-timedelta(hours=1))
        self.assertIn("Price expired", self.status()["units"][0]["reasons"])

    def test_future_price(self):
        self.price(effective_start=self.at+timedelta(days=1))
        self.assertIn("Price not yet effective", self.status()["units"][0]["reasons"])

    def test_zero_and_invalid_price(self):
        self.price(amount=Decimal("0"))
        self.assertFalse(self.status()["ready"])
        self.assertIn("Price is zero or invalid", self.status()["units"][0]["reasons"])
        with self.assertRaises(ValidationError):
            self.price(amount=Decimal("-1"))

    def test_no_active_unit(self):
        self.price()
        self.unit.is_active = False
        self.unit.save()
        self.assertIn("No active Sale Unit", self.status()["reasons"])

    def test_missing_inventory_still_in_management_and_not_sellable(self):
        product = Product.objects.create(name="Unlinked", sku="UNLINKED", slug="unlinked", category="VEG", base_inventory_unit="seedling", is_published=True)
        unit = ProductSaleUnit.objects.create(product=product, name="Single", base_quantity=1)
        self.price(sale_unit_id=unit.pk)
        self.assertFalse(product_readiness(product)["ready"])
        self.assertContains(self.client.get(reverse("dashboard:catalog_products")), "Unlinked")
        self.assertFalse(InventoryItem.objects.filter(product=product).exists())
        from apps.inventory.availability import AvailabilityUnavailable, get_ready_availability
        with self.assertRaises(AvailabilityUnavailable):
            get_ready_availability(product=product, sale_unit=unit)

    def test_edit_publication_preserves_identity_linkage_and_conversion(self):
        self.product.is_published = False
        self.product.save()
        response = self.client.post(reverse("dashboard:catalog_product_edit", args=[self.product.pk]), {"name":"Updated", "description":"Legitimate edit", "category":"FRT", "is_active":"on", "is_published":"on", "sku":"TAMPERED", "slug":"tampered"})
        self.assertEqual(response.status_code,302)
        self.product.refresh_from_db()
        self.unit.refresh_from_db()
        self.assertTrue(self.product.is_published)
        self.assertEqual((self.product.sku,self.product.slug),("LEGACY","original"))
        self.assertEqual(self.product.inventory_item.pk,self.item.pk)
        self.assertEqual(self.unit.base_quantity,Decimal("5.000"))

    def test_price_post_and_history_preservation(self):
        old = self.price(effective_end=self.at-timedelta(hours=1))
        original = (old.amount,old.effective_start,old.effective_end)
        response = self.client.post(reverse("dashboard:catalog_product_detail",args=[self.product.pk]), {"sale_unit_id":self.unit.pk,"amount":"30.25","effective_start":timezone.localtime(self.at).strftime("%Y-%m-%dT%H:%M"),"is_active":"on"})
        self.assertEqual(response.status_code,302)
        old.refresh_from_db()
        self.assertEqual((old.amount,old.effective_start,old.effective_end),original)
        self.assertEqual(ProductPrice.objects.count(),2)
        with self.assertRaises(ValidationError):
            self.price()
        self.assertEqual(ProductPrice.objects.count(),2)

    def test_permissions(self):
        user = get_user_model().objects.create_user("unprivileged",is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard:catalog_product_edit",args=[self.product.pk])).status_code,403)
        with self.assertRaises(PermissionDenied):
            self.price(actor=user)

    def test_stock_unit_mismatch(self):
        self.price()
        self.item.base_unit = "tray"
        with self.assertRaises(ValidationError):
            self.item.save()
        self.product.inventory_item = self.item
        result = product_readiness(self.product)
        self.assertFalse(result["ready"])
        self.assertIn("Inventory and Product stock units do not match",result["reasons"])

    def test_approved_publication_and_price_preserve_history_and_branch_stock(self):
        from django.db.models import Q
        from apps.dashboard.test_pos import POSLocationTests
        from apps.inventory.models import InventoryLocation
        from apps.inventory.availability import get_ready_availability
        # Reuse isolated branch inventory fixtures, never the development records.
        POSLocationTests.setUpTestData()
        product = POSLocationTests.product
        unit = POSLocationTests.unit
        unit.base_quantity = Decimal("150.000")
        unit.save()
        historical = ProductPrice.objects.get(sale_unit=unit)
        historical.is_active = False
        historical.effective_end = timezone.now()-timedelta(hours=1)
        historical.save()
        old = ProductPrice.objects.values().get(pk=historical.pk)
        product.is_published = False
        product.save()
        stock = list(StockPosition.objects.order_by("pk").values())
        edit_product(product_id=product.pk, actor=self.actor, name=product.name, description=product.description,
                     category=product.category, is_active=True, is_published=True)
        self.price(sale_unit_id=unit.pk, amount=Decimal("300.00"), effective_start=timezone.now())
        product.refresh_from_db()
        self.assertTrue(product_readiness(product)["ready"])
        self.assertEqual(ProductPrice.objects.values().get(pk=historical.pk),old)
        self.assertEqual(list(StockPosition.objects.order_by("pk").values()),stock)
        self.assertEqual(ProductPrice.objects.filter(sale_unit=unit,is_active=True).count(),1)
        with self.assertRaises(ValidationError):
            self.price(sale_unit_id=unit.pk,amount=Decimal("300.00"),effective_start=timezone.now())
        self.assertEqual(ProductPrice.objects.filter(sale_unit=unit,is_active=True).count(),1)
        self.assertEqual(get_ready_availability(product=product,sale_unit=unit,location_id=POSLocationTests.bomet.pk).available_sale_units,0)
