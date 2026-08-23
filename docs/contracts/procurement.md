# Procurement contract (future)

> **Superseded and out of V1 scope.** Retained as reusable historical design; V1 permits only simple external/manual Inventory Receipt. See the [ratified V1 business contract](../architecture/v1-business-contract.md).

## Boundary

This is a future domain/UI contract only. Phase 3E implements no model, migration, API, persistence, purchase posting, Inventory receipt, payable, payment or calculation.

## Conceptual aggregates

- `Supplier` and versioned contacts/status/due-diligence evidence.
- `PurchaseRequest` with immutable lines, requester/department/branch, required date, priority, reason and approval state.
- `Quotation` and `QuotationLine` with supplier offer/version/validity/document evidence.
- `SourcingDecision` with comparison references, conflicts, reason and independent approval.
- `PurchaseOrder` and immutable `PurchaseOrderVersion/Line`, supplier snapshot, delivery/payment terms and approval/issue state.
- `DeliverySchedule` supporting multiple planned/actual deliveries.
- `GoodsDeliveryInspection` with delivered/accepted/rejected/damaged/hold evidence and line correlations.
- `ProcurementApprovalDecision`, `AttachmentMetadata` and append-only domain activity.

Names define ownership, not approved Django models.

## State machines

- Purchase Request: `Draft → Submitted → Approved → Converted to Purchase Order`, with `Rejected` and `Cancelled` governed alternatives. Conversion is a link, not destruction.
- Quotation: `Requested → Received → Validated → Compared → Selected/Not Selected/Expired`.
- Purchase Order: `Draft → Awaiting Approval → Approved → Issued → Partially Received → Completed`, with pre-issue rejection/cancellation and governed post-issue cancellation/version amendment.
- Delivery Inspection: `Expected → Arrived → Inspecting → Recorded`, with partial/rejected/hold outcomes by line. It never enters `Inventory Posted` as a Procurement-owned state; it references an independent Inventory result.

Approval and activity histories are append-only. Material PO changes create a new version and renewed approvals rather than editing an approved/issued version.

## Commands

Future named commands create/update/submit/cancel request; approve/reject request; invite/record quotation; prepare/select award; create/amend/approve/issue/cancel PO; schedule delivery; record delivery inspection; attach/classify document; activate/inactivate/review supplier.

Every consequential command carries actor/active role/delegation, capability, branch/department scope, expected aggregate/version, reason/evidence, approval reference, idempotency key, correlation ID and privacy-reviewed source context. Generic PATCH cannot bypass states.

## Inventory handoff

`Issued PO + supplier delivery → Procurement inspection evidence → Inventory receipt request → independently authorized Inventory receipt/rejection/variance result`

Procurement supplies stable PO/version/line, supplier/delivery note, supplier lot, delivered/accepted/rejected/held quantities and inspection evidence. Inventory validates item/lot/unit/condition/location and consumes each accepted inspection line at most once. Only Inventory posting changes stock. Partial acceptance leaves PO delivery expectations open.

## Production integration

Production/Departments create purchase requests for external goods/services. Procurement sources them. Inventory receives physical goods and later issues materials to Production. Production cannot select supplier by mutating Procurement or accept stock by recording usage.

## Future Accounting handoff

Procurement owns agreed price/terms and invoice attachment/reference; Inventory owns accepted quantities/receipt; Accounting owns invoice validation, three-way match result, payable, tax, ledger and payment. Neither PO approval nor goods inspection creates a payable.

## Query/UI projections

Queries provide permission/scope-filtered dashboard queues, suppliers, request/order lists/details, delivery inspections, approvals, attachments, activity and performance inputs. Every projection declares `as_of`, policy/version, stable pagination/sorting, field redaction and safe allowed-command hints.

Performance/spend projections come from Reporting with defined period, grain, currency, timezone, formula/version and freshness. Frontend mock charts never become calculation logic.

## Authorization and separation

Canonical capabilities are `procurement.view`, `create_request`, `approve_request`, `manage_supplier`, `manage_quotation`, `create_order`, `approve_order`, `issue_order`, `record_delivery`, `view_spend`, `export`.

Requester cannot approve their request. Quotation/award preparer or conflicted party cannot be sole award approver. PO creator/amender cannot be its only approver. Delivery inspector cannot conceal discrepancies through Inventory approval. Thresholds and Administrator escalation are effective-dated policy, not role-name branches.

## Audit and failure

Every decision preserves actor, role version, delegation, approver, reason, server time, correlation, branch and device context plus aggregate/version/before-after references. Rejection/cancellation/amendment appends history.

Offline consequential writes are prohibited. Permission, stale version, expired quote, inactive supplier, missing approval/evidence or idempotency conflict changes nothing. Cross-domain handoffs use stable events/outbox/idempotency, never direct-table writes.
