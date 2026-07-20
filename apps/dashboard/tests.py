from django.test import SimpleTestCase
from django.urls import reverse


class StaffDashboardTests(SimpleTestCase):
    def test_dashboard_exposes_staff_foundation_contract(self):
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        for marker in (
            "data-staff-app", "data-staff-navigation", "data-metric-card",
            "data-staff-table", "data-production-alert", "data-task-card",
            "data-activity-timeline", "data-notification-card", "data-quick-action",
            "data-staff-search", "data-confirmation-dialog", "data-staff-drawer",
        ):
            self.assertContains(response, marker)
        for section in (
            "Today’s orders", "Awaiting fulfillment assignment", "Orders in preparation",
            "Inventory exceptions", "Production exceptions", "Today’s tasks",
            "Recent activity", "Notifications", "Quick actions",
        ):
            self.assertContains(response, section)

    def test_dashboard_uses_propagation_neutral_language(self):
        response = self.client.get(reverse("dashboard:dashboard"))
        for copy in ("Grafted Hass Avocado", "Anna F1 Tomato", "Hardening overdue", "Quality hold", "Awaiting quality review", "High mortality"):
            self.assertContains(response, copy)
        self.assertNotContains(response, "Seed-only lifecycle")

    def test_dashboard_states_are_exercisable(self):
        for state in ("loading", "empty", "error", "permission", "offline", "success"):
            response = self.client.get(reverse("dashboard:dashboard") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')
            self.assertContains(response, f"data-dashboard-{state}")

    def test_dashboard_is_frontend_only(self):
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertContains(response, "Frontend architecture preview")
        self.assertContains(response, "No task, order, stock, production or financial record is changed")


class OrderManagementTests(SimpleTestCase):
    def test_order_list_exposes_filters_table_cards_and_states(self):
        response = self.client.get(reverse("dashboard:orders"))
        self.assertEqual(response.status_code, 200)
        for marker in ("data-order-management", "data-order-filter-panel", "data-order-search", "data-order-table", "data-order-cards", "data-orders-loading", "data-orders-empty", "data-orders-offline", "data-orders-permission", "data-orders-error"):
            self.assertContains(response, marker)
        for copy in ("Fulfillment", "Payment", "Order status", "Customer", "Priority", "Tags", "Estimated completion", "Last updated"):
            self.assertContains(response, copy)

    def test_order_detail_composes_independent_lifecycles(self):
        response = self.client.get(reverse("dashboard:order_detail", args=["WTF-260716-1042"]))
        self.assertEqual(response.status_code, 200)
        for copy in ("Independent lifecycles", "Order", "Payment", "Fulfillment", "Return", "Availability", "Inventory", "Availability / Feasibility Check passed", "Fulfillment Quality Check", "Partial-operation ready", "Multiple-delivery ready"):
            self.assertContains(response, copy)
        self.assertContains(response, "no production state changed")
        self.assertContains(response, "No card owns or changes another domain")

    def test_order_detail_has_staff_workspace_components(self):
        response = self.client.get(reverse("dashboard:order_detail", args=["WTF-260716-1042"]))
        for copy in ("Customer information", "Products and fulfillment lines", "Operational timeline", "Payment summary", "Fulfillment summary", "Internal notes", "Activity history", "Attachments", "Quality checklist", "Quick Actions", "Print Picking List", "Print Receipt"):
            self.assertContains(response, copy)
        for marker in ("data-operational-timeline", "data-order-activity", "data-action-menu", "data-order-action-dialog"):
            self.assertContains(response, marker)

    def test_order_management_states_are_exercisable(self):
        for state in ("loading", "empty", "error", "permission", "offline", "success"):
            list_response = self.client.get(reverse("dashboard:orders") + f"?state={state}")
            detail_response = self.client.get(reverse("dashboard:order_detail", args=["WTF-260716-1042"]) + f"?state={state}")
            self.assertContains(list_response, f'data-state-mode="{state}"')
            self.assertContains(detail_response, f'data-state-mode="{state}"')

    def test_order_pages_are_frontend_only(self):
        response = self.client.get(reverse("dashboard:order_detail", args=["WTF-260716-1042"]))
        self.assertContains(response, "Actions do not change Order, Fulfillment, Payment, Return, Production or Inventory")


class ProductionManagementTests(SimpleTestCase):
    def test_all_production_routes_render(self):
        routes = (
            ("dashboard:production", ()), ("dashboard:source_lots", ()),
            ("dashboard:production_batches", ()), ("dashboard:production_tasks", ()),
            ("dashboard:production_exceptions", ()),
            ("dashboard:production_batch_detail", ("PB-AVO-2606-04",)),
        )
        for route, args in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-production-page")

    def test_dashboard_is_exception_first_and_not_inventory(self):
        response = self.client.get(reverse("dashboard:production"))
        for copy in ("Active batches", "In propagation", "Growing", "Hardening", "Awaiting quality review", "Ready for release", "High mortality", "Resource alerts", "Upcoming tasks"):
            self.assertContains(response, copy)
        self.assertContains(response, "Production work-in-progress is not inventory")
        self.assertContains(response, "Inventory-owned movement")

    def test_source_lots_are_propagation_method_neutral(self):
        response = self.client.get(reverse("dashboard:source_lots"))
        for copy in ("Seed", "Avocado rootstock", "Hass scion material", "Stem cuttings", "Cost placeholder", "Traceability"):
            self.assertContains(response, copy)

    def test_batches_expose_required_operational_fields(self):
        response = self.client.get(reverse("dashboard:production_batches"))
        for copy in ("Batch number", "Propagation method", "Current stage", "Age", "Location", "Assigned staff", "Health status", "Expected release", "Estimated quantity", "Current quantity", "Notes"):
            self.assertContains(response, copy)
        for method in ("Grafting", "Seed", "Stem cutting"):
            self.assertContains(response, method)

    def test_batch_detail_exposes_governed_records(self):
        response = self.client.get(reverse("dashboard:production_batch_detail", args=["PB-AVO-2606-04"]))
        for copy in ("Batch overview", "Tasks", "Labour records", "Input usage", "Expenses", "Quality", "Progress photos", "Activity log"):
            self.assertContains(response, copy)
        for field in ("Batch number", "Crop", "Variety", "Propagation method", "Current stage", "Responsible supervisor", "Start date", "Expected release"):
            self.assertContains(response, field)
        self.assertContains(response, "Approval does not create Inventory")
        self.assertContains(response, "No stock deducted")

    def test_batch_workspace_preserves_independent_record_boundaries(self):
        response = self.client.get(reverse("dashboard:production_batch_detail", args=["PB-AVO-2606-04"]))
        for copy in (
            "Tasks describe work; they do not record cost or consume inventory",
            "Multiple labour entries may link to one task",
            "Usage records are not Inventory deductions or Procurement receipts",
            "Expenses remain distinct from material inputs and labour time records",
            "No accounting entry",
            "Germinated", "not applicable to grafting",
            "Append-only operational history",
        ):
            self.assertContains(response, copy)
        for tab in ("overview", "tasks", "labour", "inputs", "expenses", "quality", "photos", "activity"):
            self.assertContains(response, f'data-workspace-tab="{tab}"')
            self.assertContains(response, f'data-workspace-panel="{tab}"')

    def test_batch_workspace_is_frontend_only(self):
        response = self.client.get(reverse("dashboard:production_batch_detail", args=["PB-AVO-2606-04"]))
        self.assertContains(response, "Frontend workspace preview only")
        self.assertContains(response, "is created, calculated, or changed")

    def test_exception_and_task_workspaces_have_governed_language(self):
        exceptions = self.client.get(reverse("dashboard:production_exceptions"))
        tasks = self.client.get(reverse("dashboard:production_tasks"))
        for copy in ("High mortality", "Poor establishment", "Poor growth", "Poor quality", "Delayed batch", "Quality hold", "Input shortage", "Awaiting release approval"):
            self.assertContains(exceptions, copy)
        for copy in ("Sowing", "Transplanting", "Watering", "Fertilizing", "Spraying", "Pruning", "Hardening", "Quality Inspection", "Ready for Release", "Completed", "Overdue", "Upcoming"):
            self.assertContains(tasks, copy)
        self.assertContains(tasks, "never silently advances a batch stage")

    def test_production_states_are_exercisable(self):
        for state in ("loading", "empty", "error", "permission", "offline", "success"):
            response = self.client.get(reverse("dashboard:production") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')
            self.assertContains(response, f"data-production-{state}")


class InventoryManagementTests(SimpleTestCase):
    def test_all_inventory_routes_render(self):
        routes = (
            ("dashboard:inventory", ()), ("dashboard:inventory_items", ()),
            ("dashboard:inventory_item_detail", ("PLT-AVO-HASS",)),
            ("dashboard:inventory_lots", ()), ("dashboard:inventory_movements", ()),
            ("dashboard:inventory_receiving", ()), ("dashboard:inventory_transfers", ()),
            ("dashboard:inventory_counts", ()), ("dashboard:inventory_adjustments", ()),
        )
        for route, args in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-inventory-page")
                self.assertContains(response, "Authorization simulation — not secure")

    def test_inventory_dashboard_exposes_metrics_alerts_activity_and_actions(self):
        response = self.client.get(reverse("dashboard:inventory"))
        for copy in (
            "Total inventory items", "Available stock", "Reserved stock", "Quality hold",
            "Low stock alerts", "Out of stock", "In transit", "Pending receipts",
            "Pending transfers", "Pending cycle counts", "Recent Inventory activity",
            "Quick actions", "Receive stock", "Transfer stock", "Count stock",
            "Adjust stock", "View ledger", "Create alert",
        ):
            self.assertContains(response, copy)

    def test_inventory_items_expose_required_fields_filters_and_pagination(self):
        response = self.client.get(reverse("dashboard:inventory_items"))
        for copy in (
            "Category", "Location", "Available quantity", "Reserved quantity", "Condition",
            "Status", "Last movement", "Actions", "Search", "Sort by",
            "Showing 1–6 of 286 items",
        ):
            self.assertContains(response, copy)
        for state in ("loading", "empty", "error", "permission", "offline"):
            self.assertContains(response, f"data-inventory-{state}")

    def test_inventory_item_detail_is_tabbed_workspace(self):
        response = self.client.get(reverse("dashboard:inventory_item_detail", args=["PLT-AVO-HASS"]))
        for tab in ("overview", "movements", "lots", "locations", "reservations", "transfers", "counts", "activity"):
            self.assertContains(response, f'data-inventory-tab="{tab}"')
            self.assertContains(response, f'data-inventory-panel="{tab}"')
        for copy in ("Item information", "Current stock", "Available", "Reserved", "Quality hold", "In transit", "Reorder level", "Recent activity"):
            self.assertContains(response, copy)

    def test_inventory_workflows_preserve_domain_boundaries(self):
        movements = self.client.get(reverse("dashboard:inventory_movements"))
        receiving = self.client.get(reverse("dashboard:inventory_receiving"))
        transfers = self.client.get(reverse("dashboard:inventory_transfers"))
        counts = self.client.get(reverse("dashboard:inventory_counts"))
        adjustments = self.client.get(reverse("dashboard:inventory_adjustments"))
        self.assertContains(movements, "Production cannot create stock")
        self.assertContains(movements, "Receipt is a projection, not a stock event")
        self.assertContains(receiving, "does not create a Procurement payable")
        self.assertContains(transfers, "In Transit")
        self.assertContains(transfers, "Variance")
        self.assertContains(counts, "Blind count")
        self.assertContains(counts, "Independent approval")
        self.assertContains(adjustments, "no user edits a balance")
        self.assertContains(adjustments, "separately approved posted movement")

    def test_inventory_actions_are_capability_labelled_without_role_checks(self):
        for route in ("dashboard:inventory", "dashboard:inventory_receiving", "dashboard:inventory_transfers", "dashboard:inventory_counts", "dashboard:inventory_adjustments"):
            response = self.client.get(reverse(route))
            self.assertContains(response, "data-capability=")
        with open("static/js/staff-inventory.js", encoding="utf-8") as script:
            source = script.read()
        self.assertNotIn("if (fixture.role", source)
        self.assertNotIn("role ==", source)

    def test_inventory_states_are_exercisable(self):
        for state in ("loading", "empty", "error", "permission", "offline", "success"):
            response = self.client.get(reverse("dashboard:inventory") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')

    def test_inventory_is_frontend_only(self):
        response = self.client.get(reverse("dashboard:inventory"))
        self.assertContains(response, "Frontend Inventory preview only")
        self.assertContains(response, "is created, calculated, persisted, or changed")


class ProcurementManagementTests(SimpleTestCase):
    def test_all_procurement_routes_render(self):
        routes = (
            ("dashboard:procurement", ()), ("dashboard:suppliers", ()),
            ("dashboard:supplier_detail", ("SUP-0004",)),
            ("dashboard:purchase_requests", ()),
            ("dashboard:purchase_request_detail", ("PR-2607-0041",)),
            ("dashboard:purchase_orders", ()),
            ("dashboard:purchase_order_detail", ("PO-2607-0051",)),
            ("dashboard:procurement_receiving", ()),
            ("dashboard:supplier_performance", ()),
        )
        for route, args in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-procurement-page")
                self.assertContains(response, "Authorization simulation — not secure")

    def test_procurement_dashboard_has_metrics_alerts_activity_and_actions(self):
        response = self.client.get(reverse("dashboard:procurement"))
        for copy in (
            "Pending purchase requests", "Pending quotations", "POs awaiting approval",
            "Orders awaiting delivery", "Goods awaiting receipt", "Overdue deliveries",
            "Supplier performance", "Recent Procurement activity", "Quick actions",
            "Create purchase request", "Supplier directory", "Receive goods",
            "Approve request", "Reports",
        ):
            self.assertContains(response, copy)
        for alert in ("Supplier delay", "Purchase awaiting approval", "Late delivery", "Quality issue", "Price increase", "Outstanding receipt"):
            self.assertContains(response, alert)

    def test_supplier_directory_exposes_required_profile_fields(self):
        response = self.client.get(reverse("dashboard:suppliers"))
        for copy in (
            "Supplier type", "Products supplied", "Lead time", "County", "Performance",
            "Phone", "Email", "Preferred", "Active",
        ):
            self.assertContains(response, copy)
        detail = self.client.get(reverse("dashboard:supplier_detail", args=["SUP-0004"]))
        self.assertContains(detail, "Primary contact")
        self.assertContains(detail, "On-time delivery")

    def test_purchase_request_lifecycle_and_detail(self):
        response = self.client.get(reverse("dashboard:purchase_requests"))
        for state in ("Draft", "Submitted", "Approved", "Rejected", "Cancelled", "Converted to PO"):
            self.assertContains(response, state)
        detail = self.client.get(reverse("dashboard:purchase_request_detail", args=["PR-2607-0041"]))
        for copy in ("Requester", "Department", "Required date", "Priority", "Estimated cost", "Items", "Approval history", "Requester cannot approve"):
            self.assertContains(detail, copy)

    def test_purchase_order_workspace_has_all_tabs_and_states(self):
        response = self.client.get(reverse("dashboard:purchase_order_detail", args=["PO-2607-0051"]))
        for tab in ("overview", "supplier", "items", "delivery", "approvals", "documents", "activity"):
            self.assertContains(response, f'data-procurement-tab="{tab}"')
            self.assertContains(response, f'data-procurement-panel="{tab}"')
        orders = self.client.get(reverse("dashboard:purchase_orders"))
        for state in ("Draft", "Awaiting Approval", "Approved", "Issued", "Partially Received", "Completed", "Cancelled"):
            self.assertContains(orders, state)

    def test_goods_receiving_does_not_own_inventory(self):
        response = self.client.get(reverse("dashboard:procurement_receiving"))
        for copy in (
            "Partial receipts", "Rejected items", "Quality hold", "Inspection notes",
            "Receiving history", "separate authorized transaction alone changes stock",
            "never creates an Inventory receipt", "does not create a Procurement payable",
        ):
            self.assertContains(response, copy)

    def test_supplier_performance_is_mock_and_reporting_owned(self):
        response = self.client.get(reverse("dashboard:supplier_performance"))
        for copy in ("On-time deliveries", "Rejected deliveries", "Average lead time", "Order accuracy", "Quality rating", "Procurement spend", "Mock trend"):
            self.assertContains(response, copy)
        self.assertContains(response, "future Reporting service owns")

    def test_procurement_uses_capabilities_not_role_comparisons(self):
        response = self.client.get(reverse("dashboard:procurement"))
        self.assertContains(response, "data-procurement-capability=")
        with open("static/js/staff-procurement.js", encoding="utf-8") as script:
            source = script.read()
        self.assertNotIn("if (fixture.role", source)
        self.assertNotIn("role ==", source)

    def test_procurement_states_are_exercisable(self):
        for state in ("loading", "empty", "error", "permission", "offline", "success"):
            response = self.client.get(reverse("dashboard:procurement") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')
            self.assertContains(response, f"data-procurement-{state}")

    def test_procurement_is_frontend_only(self):
        response = self.client.get(reverse("dashboard:procurement"))
        self.assertContains(response, "Frontend Procurement preview only")
        self.assertContains(response, "is created, posted, calculated, persisted, or changed")


class POSFrontendTests(SimpleTestCase):
    def test_all_pos_routes_render_with_shared_contract(self):
        routes = (
            ("dashboard:pos", ()),
            ("dashboard:pos_sale", ()),
            ("dashboard:pos_parked", ()),
            ("dashboard:pos_transactions", ()),
            ("dashboard:pos_receipt", ("POS-260718-0042",)),
        )
        for route, args in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-pos-page")
                self.assertContains(response, "Authorization simulation — not secure")

    def test_pos_dashboard_exposes_register_metrics_activity_and_actions(self):
        response = self.client.get(reverse("dashboard:pos"))
        for copy in (
            "Today’s sales", "Open register", "Pending transactions", "Parked sales",
            "Recent transactions", "Top selling products", "Quick actions",
            "New Sale", "Park Sale", "Close Register", "View Transactions",
            "Current cashier", "Register status", "Session summary",
        ):
            self.assertContains(response, copy)

    def test_sale_workspace_covers_fast_cashier_flow(self):
        response = self.client.get(reverse("dashboard:pos_sale"))
        for copy in (
            "Search product", "Fruit seedlings", "Vegetables", "Growing media",
            "Recently sold", "Popular", "Barcode", "QR", "available",
            "Add to cart", "Discount", "Sale notes", "Subtotal", "Tax placeholder",
            "Total", "Walk-in Customer", "Existing Customer", "Find customer",
            "Customer details", "Loyalty placeholder", "Cash", "M-Pesa", "Card",
            "Mixed Payment", "Store Credit", "Complete Sale",
        ):
            self.assertContains(response, copy)
        for marker in (
            "data-pos-search", "data-pos-product", "data-add-product",
            "data-remove-line", "data-quantity-minus", "data-quantity-plus",
            "data-cart-subtotal", "data-cart-total", "data-complete-sale",
        ):
            self.assertContains(response, marker)

    def test_parked_history_receipt_and_returns_are_mock_projections(self):
        parked = self.client.get(reverse("dashboard:pos_parked"))
        for copy in ("Resume sale", "Cancel parked sale", "do not reserve Inventory"):
            self.assertContains(parked, copy)
        history = self.client.get(reverse("dashboard:pos_transactions"))
        for copy in (
            "Reference", "Customer", "Cashier", "Status", "Payment method", "Total",
            "Return workflow coming in Phase 4B",
        ):
            self.assertContains(history, copy)
        receipt = self.client.get(reverse("dashboard:pos_receipt", args=["POS-260718-0042"]))
        for copy in (
            "Receipt Preview", "Future print", "Future PDF", "Future email",
            "Mock receipt preview", "Inventory issue", "Accounting",
        ):
            self.assertContains(receipt, copy)

    def test_pos_actions_use_capabilities_without_role_comparisons(self):
        response = self.client.get(reverse("dashboard:pos"))
        self.assertContains(response, "data-pos-capability=")
        with open("static/js/staff-pos.js", encoding="utf-8") as script:
            source = script.read()
        self.assertIn("capabilities:", source)
        self.assertNotIn("if (fixture.role", source)
        self.assertNotIn("role ==", source)
        self.assertNotIn("role ===", source)

    def test_pos_states_are_exercisable(self):
        for state in ("loading", "empty", "error", "permission", "offline", "success"):
            response = self.client.get(reverse("dashboard:pos") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')
            self.assertContains(response, f"data-pos-{state}")

    def test_pos_is_frontend_only(self):
        response = self.client.get(reverse("dashboard:pos_sale"))
        self.assertContains(response, "Frontend POS preview only")
        self.assertContains(response, "No sale, order, payment, tender, cash movement")
        self.assertContains(response, "no payment, Inventory issue or Accounting event")


class DeliveryFrontendTests(SimpleTestCase):
    def test_all_delivery_routes_render_with_shared_contract(self):
        routes = (
            ("dashboard:delivery", ()),
            ("dashboard:delivery_jobs", ()),
            ("dashboard:delivery_job_detail", ("DEL-260718-0048",)),
        )
        for route, args in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "data-delivery-page")
                self.assertContains(response, "Authorization simulation — not secure")

    def test_dashboard_exposes_required_queues_and_actions(self):
        response = self.client.get(reverse("dashboard:delivery"))
        for copy in (
            "Awaiting customer confirmation", "Ready for dispatch", "Out for delivery",
            "Delivered today", "Failed deliveries", "Customer pickups awaiting collection",
            "Quick actions", "Record confirmation", "Dispatch delivery", "Record collection",
        ):
            self.assertContains(response, copy)

    def test_jobs_expose_required_fields_and_statuses(self):
        response = self.client.get(reverse("dashboard:delivery_jobs"))
        for copy in (
            "Delivery Number", "Order Reference", "Customer", "Phone", "Delivery Address",
            "Expected Date", "Current Status", "Notes", "Transport Notes",
            "Home Delivery", "Customer Pickup", "Awaiting Customer Confirmation",
            "Customer Confirmed", "Out for Delivery", "Delivered", "Delivery Failed",
            "Ready for Collection", "Collected", "Completed",
        ):
            self.assertContains(response, copy)

    def test_detail_covers_confirmation_dispatch_completion_failure_and_pickup(self):
        response = self.client.get(reverse("dashboard:delivery_job_detail", args=["DEL-260718-0048"]))
        for copy in (
            "Customer & destination", "Products & quantities", "Order Summary",
            "Customer contacted", "Confirmation received", "Preferred delivery time",
            "Special instructions", "Before dispatch checklist", "Quantity verified",
            "Healthy seedlings", "Packed", "Labels attached", "Simple dispatch",
            "Dispatch Date", "Expected Delivery Date", "Delivery completion",
            "Received By", "Failed delivery", "Customer unavailable", "Wrong location",
            "Customer postponed", "Weather", "Transport issue", "Reschedule Date",
            "Ready for Collection", "Collected By", "Collection Time",
            "Activity timeline", "Dispatched", "Delivered / Collected", "Rescheduled",
        ):
            self.assertContains(response, copy)

    def test_delivery_uses_canonical_capabilities_without_role_comparisons(self):
        response = self.client.get(reverse("dashboard:delivery"))
        self.assertContains(response, 'data-delivery-capability="fulfillment.view"')
        with open("static/js/staff-delivery.js", encoding="utf-8") as script:
            source = script.read()
        self.assertIn("capabilities:", source)
        self.assertNotIn("if (fixture.role", source)
        self.assertNotIn("role ==", source)
        self.assertNotIn("role ===", source)

    def test_delivery_states_are_exercisable(self):
        for state in ("loading", "empty", "error", "permission", "offline", "success"):
            response = self.client.get(reverse("dashboard:delivery") + f"?state={state}")
            self.assertContains(response, f'data-state-mode="{state}"')
            self.assertContains(response, f"data-delivery-{state}")

    def test_delivery_is_lightweight_frontend_only(self):
        response = self.client.get(reverse("dashboard:delivery_job_detail", args=["DEL-260718-0048"]))
        self.assertContains(response, "Frontend Delivery preview only")
        self.assertContains(response, "No Order, Fulfillment, dispatch, collection, Inventory")
        self.assertContains(response, "no driver, vehicle or route was created")
        self.assertContains(response, "does not reserve or deduct Inventory")
