import threading
import uuid
from datetime import date
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, tag

from apps.inventory.adjustments import approve_inventory_adjustment, request_inventory_adjustment
from apps.inventory.models import (
    InventoryAdjustmentRequest, InventoryLocation, InventoryMovement, StockPosition,
)
from apps.inventory.services import MovementLineInput, post_inventory_movement
from apps.inventory.supply_services import create_inventory_supply

from .models import SupplierPurchaseOrder
from .services import (
    PurchaseLineInput, ReceiptLineInput, create_purchase_order, post_goods_receipt,
    save_supplier, transition_purchase_order,
)


@tag("postgresql_concurrency")
@skipUnless(connection.vendor == "postgresql", "PostgreSQL concurrency evidence requires PostgreSQL.")
class PostgreSQLSupplierInventoryConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.manager = get_user_model().objects.create_superuser("pg-manager", "pg@example.com", "test")
        self.approver = get_user_model().objects.create_superuser("pg-approver", "ap@example.com", "test")
        self.supplier = save_supplier(
            code="PG-SUP", name="PG Supplier", actor=self.manager, reason="Setup",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        self.supply = create_inventory_supply(
            code="PG-MEDIA", name="PG Media", category="GROWING_MEDIA", base_unit="kg",
            allows_fractional_quantity=True, actor=self.manager, reason="Setup",
            correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        self.location = InventoryLocation.objects.create(code="PG-MAIN", name="PG Main")
        self.po = create_purchase_order(
            number=f"PO-{uuid.uuid4().hex[:8]}", supplier_id=self.supplier.pk,
            order_date=date.today(), expected_date=None, reference="", notes="",
            lines=(PurchaseLineInput(self.supply.pk, Decimal("100.000"), "kg", Decimal("1.000"), Decimal("10.00")),),
            actor=self.manager, reason="Setup", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )
        transition_purchase_order(
            purchase_order_id=self.po.pk, to_status=SupplierPurchaseOrder.Status.ORDERED,
            actor=self.manager, reason="Place", correlation_id=uuid.uuid4(), idempotency_key=uuid.uuid4(),
        )

    def _run(self, functions):
        barrier = threading.Barrier(len(functions))
        results, errors = [], []
        lock = threading.Lock()
        def worker(function):
            close_old_connections()
            try:
                barrier.wait()
                value = function()
                with lock: results.append(value)
            except Exception as error:
                with lock: errors.append(error)
            finally: close_old_connections()
        threads = [threading.Thread(target=worker, args=(function,)) for function in functions]
        for thread in threads: thread.start()
        for thread in threads: thread.join(20)
        self.assertTrue(all(not thread.is_alive() for thread in threads), "Concurrency worker timed out")
        return results, errors

    def _receipt_values(self, *, number, quantity, key, correlation, lot="PG-LOT"):
        return dict(
            number=number, purchase_order_id=self.po.pk, delivery_note_reference=f"DN-{number}",
            receipt_date=date.today(), lines=(ReceiptLineInput(
                self.po.lines.get().pk, quantity, Decimal("0.000"), "", lot, self.location.pk,
            ),), actor_id=self.manager.pk, reason="Concurrent receipt",
            correlation_id=correlation, idempotency_key=key,
        )

    @staticmethod
    def _post_receipt(values):
        actor = get_user_model().objects.get(pk=values["actor_id"])
        return post_goods_receipt(actor=actor, **{k: v for k, v in values.items() if k != "actor_id"})

    def test_identical_initial_receipts_are_one_effect(self):
        values = self._receipt_values(
            number="GRN-PG-IDEM", quantity=Decimal("10.000"), key=uuid.uuid4(), correlation=uuid.uuid4()
        )
        results, errors = self._run((lambda: self._post_receipt(values), lambda: self._post_receipt(values)))
        self.assertEqual(errors, [])
        self.assertEqual(len({result.pk for result in results}), 1)
        self.assertEqual(StockPosition.objects.get().on_hand_base_quantity, Decimal("10.000"))

    def test_receipt_and_issue_serialize_on_same_lot(self):
        first = self._post_receipt(self._receipt_values(
            number="GRN-PG-FIRST", quantity=Decimal("10.000"), key=uuid.uuid4(), correlation=uuid.uuid4()
        ))
        position = StockPosition.objects.select_related("lot").get()
        receipt_values = self._receipt_values(
            number="GRN-PG-SECOND", quantity=Decimal("5.000"), key=uuid.uuid4(),
            correlation=uuid.uuid4(), lot=position.lot.lot_code,
        )
        def issue():
            actor = get_user_model().objects.get(pk=self.manager.pk)
            return post_inventory_movement(
                movement_type=InventoryMovement.Type.ISSUE,
                lines=(MovementLineInput(position.item_id, position.lot_id, Decimal("3.000"), position.location_id),),
                actor=actor, reason="Concurrent issue", idempotency_key=uuid.uuid4(),
            )
        _results, errors = self._run((lambda: self._post_receipt(receipt_values), issue))
        self.assertEqual(errors, [])
        position.refresh_from_db()
        self.assertEqual(position.on_hand_base_quantity, Decimal("12.000"))

    def test_competing_adjustments_cannot_create_negative_stock(self):
        self._post_receipt(self._receipt_values(
            number="GRN-PG-ADJ", quantity=Decimal("5.000"), key=uuid.uuid4(), correlation=uuid.uuid4()
        ))
        position = StockPosition.objects.select_related("lot").get()
        requests = [request_inventory_adjustment(
            item_id=position.item_id, lot_id=position.lot_id, location_id=position.location_id,
            direction=InventoryAdjustmentRequest.Direction.OUT, base_quantity=Decimal("4.000"),
            actor=self.manager, reason="Concurrent variance", correlation_id=uuid.uuid4(),
            idempotency_key=uuid.uuid4(),
        ) for _ in range(2)]
        functions = []
        for request in requests:
            key, correlation = uuid.uuid4(), uuid.uuid4()
            def approve(request_id=request.pk, key=key, correlation=correlation):
                actor = get_user_model().objects.get(pk=self.approver.pk)
                return approve_inventory_adjustment(
                    adjustment_id=request_id, actor=actor, reason="Concurrent approval",
                    correlation_id=correlation, idempotency_key=key,
                )
            functions.append(approve)
        results, errors = self._run(tuple(functions))
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValidationError)
        position.refresh_from_db()
        self.assertEqual(position.on_hand_base_quantity, Decimal("1.000"))
