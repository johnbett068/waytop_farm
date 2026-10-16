import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.commitments.supply import supply_ready_commitment
from apps.inventory.availability import get_ready_availability
from apps.inventory.models import InventoryItem, InventoryLocation, InventoryMovement, Reservation, SourceAllocation, StockLot, StockPosition
from apps.inventory.services import MovementLineInput, post_inventory_movement
from apps.orders.models import Order, OrderLine
from apps.orders.services import OrderLineInput, create_pending_order
from apps.payments.models import Payment, PaymentEvidence
from apps.products.models import Product, ProductPrice, ProductSaleUnit


class POSLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser("pos-test", "pos@example.com", "test")
        cls.bomet = InventoryLocation.objects.create(code="BOMET", name="Bomet")
        cls.other = InventoryLocation.objects.create(code="OTHER", name="Other Branch")
        cls.product = Product.objects.create(name="POS Tomato", sku="POS-TOMATO", slug="pos-tomato", category="VEG", base_inventory_unit="seedling", is_published=True)
        cls.unit = ProductSaleUnit.objects.create(product=cls.product, name="Single seedling", base_quantity=Decimal("1.000"))
        ProductPrice.objects.create(sale_unit=cls.unit, amount=Decimal("12.55"), effective_start=timezone.now()-timedelta(days=1))
        cls.item = InventoryItem.objects.create(product=cls.product, base_unit="seedling")
        cls.lot = StockLot.objects.create(item=cls.item, lot_code="POS-LOT", condition="SALEABLE")
        for location, quantity in ((cls.bomet, "5.000"), (cls.other, "20.000")):
            post_inventory_movement(movement_type="RECEIPT", lines=[MovementLineInput(item_id=cls.item.pk, lot_id=cls.lot.pk, quantity=Decimal(quantity), destination_location_id=location.pk)], actor=cls.actor, reason="Isolated fixture", idempotency_key=uuid.uuid4())

    def setUp(self):
        self.client.force_login(self.actor)

    def add(self, quantity=2):
        self.client.get(reverse("dashboard:pos"))
        return self.client.post(reverse("dashboard:pos"), {"action":"add", "location_id":self.bomet.pk, "sale_unit_id":self.unit.pk, "quantity":quantity}, follow=True)

    def payload(self):
        saved = self.client.session["pos_cart"]
        return {"location_id":saved["location"], "idempotency_key":saved["key"], "customer":"", "payment_method":"MPESA", "reference":"POS-MPESA-REF"}

    def create(self):
        self.add()
        self.client.post(reverse("dashboard:pos_sale"), self.payload())
        return Order.objects.get()

    def confirm(self, order):
        url = reverse("dashboard:pos_order_detail", args=(order.pk,))
        for _ in range(2):
            self.client.post(url, {"action":"confirm", "reference":"POS-MPESA-REF"})
        self.assertEqual(PaymentEvidence.objects.count(), 1)
        order.refresh_from_db()
        self.assertEqual(order.status, "CONFIRMED")
        return order

    def test_bomet_default_and_location_specific_catalog(self):
        response = self.client.get(reverse("dashboard:pos"))
        self.assertEqual(response.context["location"], self.bomet)
        self.assertEqual(self.client.session["pos_cart"]["location"], str(self.bomet.pk))
        self.assertContains(response, f'<option value="{self.bomet.pk}" selected>Bomet</option>', html=True)
        self.assertEqual(response.context["products"][0]["available"], 5)
        self.assertEqual(get_ready_availability(product=self.product, sale_unit=self.unit).available_sale_units,25)
        self.assertContains(self.client.get(reverse("dashboard:pos"), {"q":"POS-TOMATO"}), "POS Tomato")
        self.assertEqual(self.client.get(reverse("dashboard:pos"), {"q":"missing"}).context["products"], [])

    @override_settings(DEBUG=False)
    def test_production_missing_location_is_rejected_in_view_and_service(self):
        self.add()
        for invalid in (None, "", "null", str(uuid.uuid4())):
            data = self.payload()
            if invalid is None:
                data.pop("location_id")
            else:
                data["location_id"] = invalid
            self.client.post(reverse("dashboard:pos_sale"), data)
            with self.assertRaises(ValidationError):
                create_pending_order(channel="POS", fulfillment_method="CUSTOMER_COLLECTION", lines=[OrderLineInput(self.product.pk,self.unit.pk,1,"READY")], actor=self.actor, creation_idempotency_key=uuid.uuid4(),location_id=invalid)
        self.assertEqual(Order.objects.count(),0)

    def test_cart_changes_decimal_totals_and_no_inventory_mutation(self):
        response=self.add()
        self.assertEqual(response.context["total"],Decimal("25.10"))
        response=self.client.post(reverse("dashboard:pos"), {"action":"update","location_id":self.bomet.pk,"sale_unit_id":self.unit.pk,"quantity":3},follow=True)
        self.assertEqual(response.context["total"],Decimal("37.65"))
        self.client.post(reverse("dashboard:pos"), {"action":"remove","sale_unit_id":self.unit.pk})
        self.assertEqual(self.client.session["pos_cart"]["lines"],{})
        self.assertEqual(InventoryMovement.objects.count(),2)
        self.assertFalse(Reservation.objects.exists())

    def test_oversell_invalid_quantities_and_inactive_unpublished_products_rejected(self):
        for quantity in (0,-1,"1.5",6):
            self.add(quantity)
            self.assertEqual(self.client.session["pos_cart"]["lines"],{})
        self.product.is_published=False
        self.product.save()
        self.add()
        self.assertEqual(self.client.session["pos_cart"]["lines"],{})
        self.product.is_active=False
        self.product.is_published=True
        # The existing catalog constraint already forbids inactive + published.
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.product.save()
        self.product.is_published=False
        self.product.save()
        self.assertEqual(self.client.get(reverse("dashboard:pos")).context["products"],[])

    def test_order_confirmation_and_consumption_stay_at_selected_location(self):
        # Legacy pending-order confirmation retains its separate supply workflow.
        order = self.direct_order()
        self.confirm(order)
        self.assertEqual(order.payment.state,"CONFIRMED")
        self.assertEqual(InventoryMovement.objects.count(),2)
        self.assertEqual(SourceAllocation.objects.get().stock_position.location,self.bomet)
        self.assertEqual(get_ready_availability(product=self.product,sale_unit=self.unit,location_id=self.bomet.pk).available_sale_units,3)
        self.assertEqual(get_ready_availability(product=self.product,sale_unit=self.unit,location_id=self.other.pk).available_sale_units,20)
        self.client.post(reverse("dashboard:pos_order_detail",args=(order.pk,)),{"action":"process","correlation_id":uuid.uuid4(),"idempotency_key":uuid.uuid4()})
        order.refresh_from_db()
        self.assertEqual(order.status,"PROCESSING")
        reservation=Reservation.objects.get()
        supply_ready_commitment(commitment_id=reservation.commitment.id,commercial_quantity=2,actor=self.actor,reason="Test supply",source_type="TEST",source_reference="POS",correlation_id=uuid.uuid4(),idempotency_key=uuid.uuid4())
        self.assertEqual(StockPosition.objects.get(location=self.bomet).on_hand_base_quantity,Decimal("3.000"))
        self.assertEqual(StockPosition.objects.get(location=self.other).on_hand_base_quantity,Decimal("20.000"))

    def test_switch_location_revalidates_cart_and_inactive_location_is_invalid(self):
        self.add()
        self.client.post(reverse("dashboard:pos"),{"action":"location","location_id":self.other.pk})
        self.assertTrue(self.client.session["pos_cart"]["lines"])
        self.assertTrue(self.client.get(reverse("dashboard:pos")).context["cart_valid"])
        self.assertEqual(self.client.get(reverse("dashboard:pos")).context["products"][0]["available"],20)
        self.other.is_active=False
        self.other.save()
        self.client.post(reverse("dashboard:pos_sale"),self.payload())
        self.assertFalse(Order.objects.exists())

    def test_pos_permission_required(self):
        user=get_user_model().objects.create_user(username="no-pos",is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard:pos")).status_code,403)
        self.assertEqual(self.client.post(reverse("dashboard:pos_sale"),{}).status_code,403)

    def direct_order(self, quantity=2, **overrides):
        values = dict(channel="POS", fulfillment_method="CUSTOMER_COLLECTION", lines=[OrderLineInput(self.product.pk, self.unit.pk, quantity, "READY")], actor=self.actor, creation_idempotency_key=uuid.uuid4(), location_id=self.bomet.pk)
        values.update(overrides)
        return create_pending_order(**values)

    def test_location_required_in_development_and_ineligible_locations_rejected(self):
        for debug in (True, False):
            with self.settings(DEBUG=debug):
                for location in (None, "", "null", str(uuid.uuid4())):
                    with self.assertRaises(ValidationError):
                        self.direct_order(location_id=location)
        for field in ("is_active", "allows_saleable_stock"):
            setattr(self.bomet, field, False)
            self.bomet.save()
            with self.assertRaises(ValidationError):
                self.direct_order()
            setattr(self.bomet, field, True)
            self.bomet.save()
        self.assertFalse(Order.objects.exists())

    def test_no_bomet_does_not_select_first_location(self):
        self.bomet.is_active = False
        self.bomet.save()
        response = self.client.get(reverse("dashboard:pos"))
        self.assertIsNone(response.context["location"])
        self.assertEqual(self.client.session["pos_cart"]["location"], "")

    def test_same_key_different_location_and_order_location_mutation_rejected(self):
        key = uuid.uuid4()
        order = self.direct_order(creation_idempotency_key=key)
        self.assertEqual(self.direct_order(creation_idempotency_key=key).pk, order.pk)
        with self.assertRaises(ValidationError):
            self.direct_order(creation_idempotency_key=key, location_id=self.other.pk)
        order.location = self.other
        with self.assertRaises(ValidationError):
            order.save(_confirmation_service_write=True)
        order.refresh_from_db()
        self.assertEqual(order.location, self.bomet)

    def test_empty_branch_disables_add_and_revalidates_existing_cart(self):
        empty = InventoryLocation.objects.create(code="EMPTY", name="Empty Branch")
        self.add()
        response = self.client.post(reverse("dashboard:pos"), {"action":"location", "location_id":empty.pk}, follow=True)
        self.assertContains(response, "Out of stock at Empty Branch")
        self.assertFalse(response.context["cart_valid"])
        self.assertEqual(response.context["products"][0]["available"], 0)
        before = self.client.session["pos_cart"]["lines"]
        self.client.post(reverse("dashboard:pos"), {"action":"add", "location_id":empty.pk, "sale_unit_id":self.unit.pk, "quantity":1})
        self.assertEqual(self.client.session["pos_cart"]["lines"], before)
        self.client.post(reverse("dashboard:pos_sale"), self.payload())
        with self.assertRaises(ValidationError):
            self.direct_order(location_id=empty.pk)
        self.assertFalse(Order.objects.exists())

    def test_checkout_and_confirmation_recheck_stock_without_cross_branch_fallback(self):
        with self.assertRaises(ValidationError):
            self.direct_order(quantity=6)
        first = self.direct_order(quantity=4)
        second = self.direct_order(quantity=4)
        self.confirm(first)
        url = reverse("dashboard:pos_order_detail", args=(second.pk,))
        response = self.client.post(url, {"action":"confirm", "reference":"SECOND-MPESA"}, follow=True)
        second.refresh_from_db()
        self.assertEqual(second.status, "PENDING")
        self.assertEqual(Reservation.objects.count(), 1)
        self.assertEqual(SourceAllocation.objects.count(), 1)
        self.assertEqual(InventoryMovement.objects.count(), 2)
        with self.assertRaises(ValidationError):
            self.direct_order(quantity=2)

    def test_multi_lot_allocation_and_cross_branch_reallocation_rejected(self):
        from django.db import transaction
        from apps.inventory.reservations import AllocationSourceInput, reallocate_ready_reservation
        lot = StockLot.objects.create(item=self.item, lot_code="POS-SECOND", condition="SALEABLE")
        post_inventory_movement(movement_type="RECEIPT", lines=[MovementLineInput(item_id=self.item.pk, lot_id=lot.pk, quantity=Decimal("3.000"), destination_location_id=self.bomet.pk)], actor=self.actor, reason="Isolated second lot", idempotency_key=uuid.uuid4())
        order = self.direct_order(quantity=7)
        self.confirm(order)
        self.assertEqual(SourceAllocation.objects.count(), 2)
        self.assertEqual(set(SourceAllocation.objects.values_list("stock_position__location_id", flat=True)), {self.bomet.pk})
        reservation = Reservation.objects.get()
        other_position = StockPosition.objects.get(location=self.other)
        with self.assertRaises(ValidationError), transaction.atomic():
            reallocate_ready_reservation(reservation_id=reservation.pk, approved_sources=[AllocationSourceInput(other_position.pk, Decimal("7.000"))], actor=self.actor, reason="Reject cross branch", source_type="TEST", source_reference="POS", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())
        self.assertEqual(SourceAllocation.objects.count(), 2)

    def test_supply_rejects_unavailable_branch_even_when_other_branch_has_stock(self):
        order = self.confirm(self.direct_order())
        self.client.post(reverse("dashboard:pos_order_detail",args=(order.pk,)), {"action":"process", "correlation_id":uuid.uuid4(), "idempotency_key":uuid.uuid4()})
        self.bomet.is_active = False
        self.bomet.save()
        with self.assertRaises(ValidationError):
            supply_ready_commitment(commitment_id=Reservation.objects.get().commitment_id, commercial_quantity=2, actor=self.actor, reason="Unavailable branch", source_type="TEST", source_reference="POS", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4())
        self.assertEqual(InventoryMovement.objects.count(), 2)
        self.assertEqual(StockPosition.objects.get(location=self.other).on_hand_base_quantity, Decimal("20.000"))

    def test_mixed_sale_units_cannot_oversell_and_preorder_is_rejected(self):
        pair = ProductSaleUnit.objects.create(product=self.product, name="Pair", base_quantity=Decimal("2.000"))
        ProductPrice.objects.create(sale_unit=pair, amount=Decimal("24.00"), effective_start=timezone.now()-timedelta(days=1))
        self.add(4)
        self.client.post(reverse("dashboard:pos"), {"action":"add", "location_id":self.bomet.pk, "sale_unit_id":pair.pk, "quantity":1})
        self.assertNotIn(str(pair.pk), self.client.session["pos_cart"]["lines"])
        with self.assertRaises(ValidationError):
            self.direct_order(lines=[OrderLineInput(self.product.pk,self.unit.pk,4,"READY"), OrderLineInput(self.product.pk,pair.pk,1,"READY")])
        with self.assertRaises(ValidationError):
            self.direct_order(lines=[OrderLineInput(self.product.pk,self.unit.pk,1,"PRE_ORDER")])

    def test_actual_customer_relationship_is_preserved(self):
        from apps.customers.models import Customer
        customer = Customer.objects.create(display_name="Isolated actual customer", phone="0712345678")
        self.add()
        payload = self.payload()
        payload["customer"] = customer.pk
        self.client.post(reverse("dashboard:pos_sale"), payload)
        self.assertEqual(Order.objects.get().customer, customer)

    def test_priced_product_without_inventory_is_visible_but_not_sellable(self):
        product = Product.objects.create(name="Unlinked priced product", sku="UNLINKED-PRICED", slug="unlinked-priced", category="VEG", base_inventory_unit="seedling", is_published=True)
        unit = ProductSaleUnit.objects.create(product=product, name="Single", base_quantity=1)
        ProductPrice.objects.create(sale_unit=unit, amount=Decimal("10.00"), effective_start=timezone.now()-timedelta(days=1))
        response = self.client.get(reverse("dashboard:pos"))
        entry = next(e for e in response.context["products"] if e["unit"].pk == unit.pk)
        self.assertTrue(entry["availability_error"])
        self.assertEqual(entry["available"],0)
        self.assertContains(response,"Availability could not be verified")
        self.client.post(reverse("dashboard:pos"),{"action":"add","location_id":self.bomet.pk,"sale_unit_id":unit.pk,"quantity":1})
        self.assertEqual(self.client.session["pos_cart"]["lines"],{})
        self.assertFalse(InventoryItem.objects.filter(product=product).exists())

    def test_unpriced_product_is_excluded_with_configuration_guidance(self):
        product = Product.objects.create(name="No approved price", sku="NO-PRICE", slug="no-price", category="VEG", base_inventory_unit="seedling", is_published=True)
        ProductSaleUnit.objects.create(product=product, name="Single", base_quantity=1)
        response = self.client.get(reverse("dashboard:pos"), {"q":"NO-PRICE"})
        self.assertEqual(response.context["products"],[])
        self.assertContains(response,"Review Product configuration")
