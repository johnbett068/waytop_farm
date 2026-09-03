# Phase 2C Supplier Inventory decision gate

Status: **RATIFIED — AUTHORITATIVE FOR PHASE 2C**

Ratified by the owner: 31 August 2026

## Outcome

INV-01 through INV-12 in `phase-2c-inventory-audit.md` are approved with the refinements below.
This record authorizes the bounded Supplier Inventory implementation and no wider Procurement,
Accounting, Production, customer, or Product behavior.

## Ratified decisions

1. Inventory may contain first-class operational Supplies that are not Products.
2. Supplies never enter the public Product catalog, Availability, Reservations, Allocations,
   Commitments, Orders, Payments, or customer-facing routes.
3. `InventoryItem` is the single physical stock identity and has exactly one immutable owner:
   Product or InventorySupply, enforced by kind and database XOR constraints.
4. A Supply definition and a Purchase Order never change stock. Only a successfully posted
   Inventory RECEIPT changes on-hand quantity.
5. ProductionPurchase and Production READY remain completely decoupled from Inventory.
6. Supply quantities use Decimal(32,3). Each Supply declares whether fractional quantities are
   allowed; discrete Supplies accept whole quantities only.
7. Supplier purchasing and physical receiving are distinct. Simple Purchase Orders and partial
   Goods Receipts are authorized. Quotations, invoices, payables, Accounting, tax, vendor payments,
   and three-way matching are deferred.
8. Supplier is a shared first-class internal identity. A Supply does not belong to one Supplier.
9. Supply receipts use RECEIPT; operational issues use ISSUE; atomic transfers retain TRANSFER.
   Returns and multi-stage transfers are not added.
10. Negative on-hand is prohibited.
11. Adjustments use a two-step Request -> Approve workflow. Requester and approver must be distinct
    active staff. Approval posts the exact ADJUSTMENT_IN or ADJUSTMENT_OUT movement; history remains
    immutable.
12. Mutations require exact capabilities, atomic services, actor, reason, UUID correlation and
    idempotency identity, canonical fingerprints, identical-retry behavior, changed-reuse rejection,
    deterministic locks, and immutable audit evidence.

## Permissions

- `procurement.view` — view Suppliers and Supplier Purchase Orders;
- `procurement.manage_suppliers` — create, edit, and deactivate Suppliers;
- `procurement.manage_purchases` — create, place, and cancel simple Purchase Orders;
- `inventory.view` — view stock, Supply definitions, and history;
- `inventory.manage_supplies` — create InventorySupply definitions;
- `inventory.receive` — post Goods Receipts;
- `inventory.adjust` — request adjustments;
- `inventory.approve_adjustment` — approve adjustments; and
- existing `inventory.release` and `inventory.transfer` retain their existing movement meanings.

Normal Django superuser semantics apply. Every command also requires an authenticated, active staff
actor. No role-name logic is authorized.

## Implementation boundary

The implementation may add Supplier, Supplier history, InventorySupply, Supply history, simple
Purchase Orders and lines, Goods Receipts and lines, adjustment requests, staff forms/routes/views,
permissions, additive migrations, and focused/concurrency tests. It must reuse the existing physical
ledger and preserve all Product and Production behavior.

No customer Supply UI, Product conversion, automatic Production receipt/issue, PRE_ORDER behavior,
delivery, refund, payroll, Accounting, taxation, invoice, payable, supplier payment, quotation,
promotion, or demo data is authorized.
