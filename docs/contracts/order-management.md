# Future staff Order Management contracts

> **Superseded for V1.** Retained for historical UI context. See the [ratified V1 business contract](../architecture/v1-business-contract.md).

## Purpose

Specify query composition and command ownership for the future backend. Phase 3B creates no API, model, database write or business service.

## Query contracts

### List

`OrderOperationsListQuery(actor, filters, sort, page)` returns a permission-filtered page with `as_of`, total/page metadata and rows containing order identity/date/customer display, total/currency, fulfillment method, separate `order_status` and `payment_status`, priority/tags, estimated completion and last public/operational update. No status is derived by mutating source records.

Supported filters: validated `q`, inclusive local-business date range converted to timezone-aware bounds, fulfillment/payment/order enums, customer identifier, governed priority/tag IDs, sort allowlist and bounded page size.

### Detail orchestration

`OrderOperationsDetailQuery(actor, order_id)` composes:

- Order snapshot and OrderStatus events
- customer/contact/address snapshots according to permission
- Fulfillment(s), Fulfillment Lines, Delivery records and events
- Payment allocations/events; Refund records/allocations/events
- Return(s), Return Lines, inspection/disposition/events
- latest Availability/Feasibility assessment
- Inventory allocation/read projection, never writable balance fields
- customer notes versus staff-only Internal Notes
- attachments metadata
- permission-filtered timeline/activity projection
- allowed command capabilities and independent version tokens

Each subprojection has its own `as_of`, availability/error/permission status. Staff HTML/API can include internal assignment only for authorised roles. Customer APIs use entirely separate allowlists.

## Future models and relationships

Order owns immutable Order Items/snapshots and OrderStatusEvent. Fulfillment belongs to Order; Fulfillment Lines reference Order Items and quantities; Delivery belongs to Fulfillment. Payment and PaymentAllocation relate money to Order; Refund and RefundAllocation link reversals to original payment/allocation. Return belongs to Order/Fulfillment delivery, with Return Lines, Inspection and Disposition. AvailabilityAssessment is an expiring read result/reference, not a Production mutation. InternalNote and Attachment have object reference, visibility classification, author and audit metadata.

## Command contracts

- `ReviewOrder`, `AcceptOrder`, `CancelOrder`, `EvaluateOrderCompletion` — Order domain.
- `AssessFeasibility`, `AssignFulfillment`, `StartPreparation`, `CompleteFulfillmentQualityCheck`, `MarkReady`, `RecordCollection`, `RecordDelivery` — Fulfillment domain.
- `RequestRefund`, `ApproveRefund`, `ExecuteRefund` — Refund/Payment domain.
- `RequestReturn`, `AuthoriseReturn`, `ReceiveReturn`, `InspectReturn`, `ResolveReturn` — Return domain.
- Inventory movement commands are invoked explicitly by authorised domain services; Order never posts stock.

Every command accepts actor, target ID, expected version, reason/comment, source/channel, correlation and idempotency key. It validates permissions/invariants transactionally, appends owning status/audit events, and dispatches cross-domain reactions through explicit events/on-commit handlers—not direct lifecycle writes.

## Lifecycle invariants

Order, Fulfillment, Payment, Refund, Return and Production transitions are separately enumerated and audited. Production/Order/Fulfillment cannot mutate one another. Payment cannot change Fulfillment. Return/refund never rewrite original financial records. Inventory movement is the only stock-changing record. Fulfillment consumes inventory through allocation/movement services; Production releases through release/movement service.

## Partial operations

Quantities and amounts use explicit line allocations with uniqueness and upper-bound rules. Multiple Fulfillments/Deliveries and Payments are allowed. Refund/Return eligibility is calculated from immutable originals minus prior authorised allocations, using Decimal money and explicit units. Concurrency protection prevents over-fulfillment, over-return and over-refund.

## Permissions, validation and audit

List/detail and every subprojection/command require explicit permissions. Customer PII and internal notes are field-level protected. Attachments require type/size/malware/retention controls. Dates use Africa/Nairobi display and timezone-aware storage. State/priority/tag inputs use governed enums/configuration. Audit records actor, impersonation, before/after state, reason, IP/device/source where appropriate, correlation and timestamp.

## States and errors

Queries distinguish not found from permission internally but avoid unsafe disclosure. UI contracts support loading, empty, stale/offline, validation, conflict/current-version, system error, permission and success. A subservice failure may degrade its panel without misrepresenting other lifecycle status. Commands return field/non-field errors and 409-style version conflict guidance.

## Definition of Done

List/detail projections, filters, models/relationships, owned commands, lifecycle invariants, partial allocations, permissions, validation, audit and error contracts are explicit with no generic status or cross-domain direct mutation.
