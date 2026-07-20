# Staff Order Management specification

## Purpose

Order Management is the internal operational workspace for reviewing customer commitments and coordinating domain-owned work from receipt through completion. It composes Order, Payment, Fulfillment, Return, Availability/Feasibility, Inventory and production-forecast reads without merging their lifecycles or mutating one domain from another.

## Displayed data

The list displays order number, customer, phone, date/time, total, fulfillment method, independent Order and Payment statuses, estimated completion and last update. Search/filter contracts cover order/customer/phone, date range, fulfillment, payment, Order status, customer, priority and tags. Desktop uses a scroll-contained table; mobile uses stacked cards.

The detail workspace displays customer/contact/address, immutable order lines and prices, lifecycle summary, composed operational timeline, Payment and Fulfillment summaries, internal notes, activity history, attachment placeholder, Fulfillment Quality Checklist placeholder and Quick Actions. Internal assignment is valid here because the route belongs exclusively to the future staff application.

## User actions

Active Phase 3B actions are navigation, responsive filter disclosure, frontend filter preview, Quick Action menu and confirmation-dialog preview. Assign Fulfillment, Start Preparation, Fulfillment Quality Check, Mark Ready, Record Collection/Delivery, Cancel Order and Request Refund are mock command affordances. Picking List, Receipt, attachments, notes and checklist mutations remain disabled.

Future actions route to the owning command service. An Order command cannot change Payment/Fulfillment/Production; a Fulfillment command cannot change Order/Production; Refund and Return create/advance their own records.

## Permissions

Future base permissions: `orders.view_order_list`, `orders.view_order`, plus action-specific Order permissions. Fulfillment, Payment, Refund, Return, Attachment, Internal Note and customer-data permissions are checked independently. Internal notes/assignments never enter customer serializers. Sensitive actions require separation of duty where policy applies.

## States

List and detail support loading, empty, offline/stale, system error, permission and success. Filters also produce an empty-results state. Offline disables all future commands. Individual panels require isolated failure/permission states when backed by separate services.

## Reusable components

Order Search, Filter Panel, Order Table, Order Card, Priority Badge, domain Status Badge, Order Summary, Lifecycle Summary, Operational Timeline, Activity Feed, Action Menu, Confirmation Dialog, State Surface and Pagination. Components render projections; they do not own transitions.

## Future models

`Order`, `OrderItem`, immutable contact/address/price snapshots and `OrderStatusEvent`; `Fulfillment`, `FulfillmentLine`, `FulfillmentAssignment`, `Delivery`, `FulfillmentStatusEvent`; `Payment`, `PaymentAllocation`, `PaymentStatusEvent`; `Refund`, `RefundAllocation`, `RefundStatusEvent`; `Return`, `ReturnLine`, `ReturnStatusEvent`, inspection/disposition; `InternalNote`, `Attachment`; Inventory allocation/movement projections; production forecast projections. Models remain in owning domains.

## Backend contracts

Future `StaffOrderListView` consumes a paginated `OrderOperationsListQuery`; `StaffOrderDetailView` uses an orchestration query that returns individually permissioned domain projections with `as_of` timestamps and allowed commands. It never returns one generic status.

List query parameters: `q`, `date_from`, `date_to`, `fulfillment_method`, `payment_status`, `order_status`, `customer`, `priority`, `tag`, `sort`, `page`. Query results provide stable public/internal IDs, display snapshots and separate statuses. Detail context includes `order`, optional `payment_summary`, fulfillment collection, return/refund summaries, availability assessment, inventory allocation read, public/internal activity and action capabilities.

Commands require CSRF, object permission, expected version, reason/comment, source and idempotency key. Responses return the owning domain’s canonical record/event; the UI refreshes the composed projection.

## Business rules

- Canonical Order: New → Under Review → Accepted → Processing → Completed or Cancelled.
- Fulfillment, Payment, Production and Return lifecycles remain independent and auditable.
- Availability/Feasibility reads released inventory, forecasts and incoming batches; it does not mutate Production.
- Production release authorizes a separate Inventory-owned receipt movement; Fulfillment consumes Inventory through governed requests; Order mutates neither.
- Partial fulfillments use Fulfillment Lines; multiple deliveries use multiple Delivery records.
- Split payments use allocations; partial refunds use Refund Allocations.
- Returns use Return/Return Lines and inspection/disposition; they never edit original financial facts.
- “Fulfillment Quality Check” is distinct from Production Quality Review.
- Estimated completion is a projection and must show confidence/source/last calculation in production.

## Definition of Done

Responsive list/table/cards, complete filters, detail workspace, independent lifecycle summary/timeline, partial-operation extension points, states, staff permissions, command/query contracts, dashboard links, accessible keyboard/focus behavior, token-only CSS and no backend behavior.
