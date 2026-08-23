# WayTop Farm business domains

> **Superseded for V1.** Retained as historical prototype design. The [ratified V1 business contract](v1-business-contract.md) is authoritative.

## Purpose

This is the canonical modular boundary map for WayTop’s future Django backend and staff application. It prevents Orders, Production, Inventory, POS and finance concerns from becoming one coupled application. Phase 3A implements documentation and frontend projections only.

## Domain map

| Domain | Purpose and responsibilities | Future models | Relationships and dependencies | Ownership boundary and important rules |
|---|---|---|---|---|
| Accounts | Staff/customer identity, roles, sessions and object permissions. | `User`, `StaffProfile`, `Role`, `PermissionGrant` | Referenced by Customer and Audit; consumes Settings policy. | Owns identity, not customer commerce records. Least privilege, separation of duties and disabled-user enforcement. |
| Customers | Customer identity, contacts, addresses, preferences and consent. | `Customer`, `CustomerContact`, `CustomerAddress`, `ConsentRecord` | Orders reference immutable customer snapshots; Notifications consume preferences. | Does not own Orders or Payments. Sensitive data is minimised and access audited. |
| Catalog | Sellable product/variant definitions, units, media and price-list configuration. | `Category`, `Product`, `ProductVariant`, `UnitOfMeasure`, `PriceList`, `ProductPrice` | Referenced by Cart, OrderItem snapshots, Production targets and Inventory items. | Catalog does not claim stock. Published prices are versioned; historical orders retain snapshots. |
| Orders | Customer commercial commitment and immutable line/price snapshots. | `Order`, `OrderItem`, `OrderContactSnapshot`, `OrderAddressSnapshot`, `OrderStatusEvent` | References Customer/Catalog snapshots; coordinates but does not own Payment or Fulfillment status. | Order lifecycle remains independent. Accepted financial facts are not silently edited. |
| Fulfillment | Customer delivery/pickup promise, preparation and completion. | `Fulfillment`, `FulfillmentLine`, `FulfillmentAssignment`, `FulfillmentStatusEvent`, `DeliveryWindow` | Belongs to Order; internally references Branch and authorised staff; consumes Inventory availability. | Branch assignment is internal. Fulfillment is independent of Payment and Production. Customer projections exclude routing. |
| Payments | Payment attempts, confirmations, allocation and refunds. | `Payment`, `PaymentAttempt`, `PaymentAllocation`, `PaymentStatusEvent`, `Refund` | Belongs to Order; integrates with future providers/POS. | Payment lifecycle is independent. Provider references and financial events are immutable; refunds reverse rather than overwrite. |
| Branches | Operational locations, areas, capabilities and transfer endpoints. | `Branch`, `OperationalArea`, `StorageLocation`, `BranchCapability` | Referenced internally by Inventory, Production, POS and Fulfillment Assignment. | Branch data and assignment are staff-only. Disabling a branch preserves history. |
| Procurement | Supplier master, purchase requests, quotations, purchase orders, delivery expectations, inspection evidence and approvals. | `Supplier`, `SupplierContact`, `PurchaseRequest`, `PurchaseRequestLine`, `Quotation`, `PurchaseOrder`, `PurchaseOrderLine`, `DeliverySchedule`, `GoodsInspection` | References Catalog/Inventory item definitions, Departments/Branches and Audit; publishes approved delivery evidence to Inventory and matching evidence to future Accounting. | Owns external supplier acquisition commitments, never stock, Inventory receipts, payables or payments. Purchase approval and receiving inspection do not change stock. |
| Inventory | Quantity ledger for saleable products and operational inputs. | `InventoryItem`, `StockLot`, `StockMovement`, `StockMovementLine`, `StockBalanceProjection`, `Transfer`, `StockCount` | Receives supplier/internal stock and released Production output; supplies Production/Sales/Fulfillment/POS; references Branch/location. | Stock is never edited directly. Receipts, issues, transfers, adjustments, sales, returns and count variances create movements. |
| Production | Propagation-neutral nursery work-in-progress, observations, inputs, labour, quality and release. | `PropagationMaterialAcceptance`, `SourceLot`, `ProductionBatch`, `PropagationActivity`, `BatchStageEvent`, `BatchObservation`, `BatchLoss`, `InputConsumption`, `LabourEntry`, `TreatmentApplication`, `WateringEvent`, `LocationEvent`, `QualityReview`, `QualityHold`, `ReleaseApproval` | References Catalog targets, Inventory issue/lot facts, Branch areas and Audit actors; approved release is consumed by a separate Inventory receipt. | Production acceptance records traceability/fitness, never a stock receipt. A batch need not originate from seed. Germination is conditional. WIP is not saleable stock until approved release and Inventory receipt. |
| POS | Staff-assisted sale workflow and till/session control. | `POSRegister`, `POSSession`, `POSSale`, `POSSaleLine`, `Tender`, `CashMovement` | Uses Catalog/Inventory/Payments/Customers and posts Order/Sale facts. | POS never bypasses price, stock-movement, payment or audit services. Closed sales/tenders are reversed, not edited. |
| Reporting | Read-only operational, production, inventory, sales and finance projections. | `ReportDefinition`, `SavedReport`, `ExportJob`, governed materialised projections | Consumes domain events/read models; no source-domain writes. | Metrics define grain, timezone and source. Reports never become hidden business logic or mutate facts. |
| Notifications | Delivery of customer/staff communications and preferences. | `Notification`, `NotificationTemplate`, `DeliveryAttempt`, `NotificationPreference` | Consumes public domain events and Settings channels. | Notification failure never rewrites business status. Templates are versioned; sensitive internal metadata is excluded. |
| Audit | Append-only history of security-sensitive and business-critical actions. | `AuditEvent`, `AuditCorrelation`, `AccessEvent` | Receives actor/source/reason/correlation metadata from every domain. | Audit is never deleted by normal users, never used as the sole transactional record, and cannot be rewritten. |
| Settings | Versioned business configuration, thresholds, numbering, support details and feature/channel policy. | `BusinessSetting`, `ThresholdPolicy`, `NumberSequencePolicy`, `SupportConfiguration`, `FeatureFlag` | Read by all domains through explicit configuration services. | Configuration changes are permissioned, effective-dated and audited. Settings do not contain transactional state. |

## Cross-domain dependency rules

- Dependencies follow service/query contracts; domains do not reach into another domain’s tables to perform mutations.
- Historical snapshots remain stable when Customer or Catalog records change.
- Operational commands include actor, role, reason, source channel and idempotency/correlation metadata where consequential.
- Read projections may combine domains for dashboards; they never become a generic shared status or write model.
- Future Django apps may align with these domains, but model placement follows ownership rather than navigation convenience.

## Displayed information and user actions

This architecture appears indirectly in staff navigation, exception cards, independent statuses and audit-aware activity. Phase 3A actions are disabled previews. Future permissions determine which domain projections and commands a staff role may use.

## States and permissions

All staff modules require loading, empty, offline/read-stale, validation, error, permission and success states. Offline consequential writes are prohibited unless a later explicitly designed conflict-safe workflow exists. Accounts provides identity; each domain enforces object/action permission and Audit records decisions.

## Backend contracts and business rules

Commands mutate one owning domain transactionally and emit explicit events/on-commit work. Queries return role-safe projections. Inventory, finance and audit are ledger/event-oriented. Order, Fulfillment and Payment remain separate. Production release is the only normal bridge from WIP into saleable inventory.

## Definition of Done

All required domains have purpose, responsibilities, models, relationships, rules, ownership and dependencies; cross-domain mutation boundaries and permissions are explicit; the canonical production lifecycle can evolve without schema redesign.
