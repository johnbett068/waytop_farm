# WayTop Farm V1 Business Contract

Status: **Ratified**
Effective: Phase 0A
Authority: This document is the canonical V1 business contract. Where an older architecture, contract, flow, prototype, or test conflicts with it, this document takes precedence.

## Scope and channels

Ecommerce and Point of Sale are order-entry channels for one `Order` concept. POS does not own a separate sale lifecycle. An Order may contain ready-stock and preorder lines. Customers see aggregate supply and never select or see internal locations.

V1 excludes Cash on Pickup, returns, refunds, detailed delivery jobs, route/driver management, and deep Procurement. External delivery is represented only by the minimum fulfillment information needed to complete an Order. Daily Handover is not a business capability.

## Order and payment confirmation boundary

The active Order lifecycle is:

`PENDING -> CONFIRMED -> PROCESSING -> FULFILLED`

Authorized cancellation is the only V1 exception transition:

`CONFIRMED | PROCESSING -> CANCELLED`

An Order starts `PENDING` with no customer stock commitment. The payment owner must verify payment ownership and revalidate availability in one atomic transaction. Only that transaction may simultaneously:

1. mark Payment confirmed;
2. move Order to `CONFIRMED`;
3. create the ready-stock and/or future-production commitments; and
4. permit entry into `PROCESSING`.

An unconfirmed payment must never accompany a `CONFIRMED` or `PROCESSING` Order. Failed revalidation leaves the Order pending and creates no commitment. Confirmation must be idempotent and auditable.

## Availability, commitments, and allocation

Physical availability never becomes negative. Aggregate availability may be assembled from multiple internal locations; the owner confirms or adjusts the hidden allocation. Customers see only the aggregate result.

Confirmed commitments are served FIFO by confirmation timestamp. A database-generated sequence is the deterministic tie-break when timestamps match. Ready-stock commitments reference physical inventory supply. Preorder commitments may consider future Production Batches whose expected ready date satisfies the customer's required date.

Forecast is planning information, not guaranteed physical stock. Planning uses the effective owner-controlled forecast. The owner must revise it as conditions change. Forecast edits do not rewrite historical commitments or Production Releases and cannot create negative physical inventory.

## Production releases

A Production Batch may have multiple partial Production Releases. Every release has independent quantity, time, actor, source Batch, and audit identity. The cumulative released quantity must never exceed the quantity legitimately available for release. Inventory derived from Production retains the Production Release and Batch provenance.

The editable forecast and an actual Production Release are different facts. Changing a forecast never changes a historical release.

## External and manual inventory

Externally acquired or manually introduced inventory enters through a simple Inventory Receipt with product, quantity, unit cost, description/source, and lot identity. It must not create a fake Production Batch. Production-derived and external/manual stock remain distinguishable by provenance. V1 does not require a deep Procurement workflow.

## Costing direction and unresolved decision

V1 inventory costing direction is **lot-specific costing**. Each lot retains its quantity, unit cost, and source/provenance. FIFO and weighted-average costing are not implemented in V1.

Production expenses attributable to a Production Batch contribute to its cost. General or other expenses do not automatically enter Production Batch cost.

For a single release, `production attributable cost / actual released quantity` describes the conceptual unit-cost direction. It is **not an approved implementation formula for multiple partial releases**. The Production phase must explicitly decide how Batch expenses are allocated across multiple releases without duplicating the same expense. Phase 0A and Phase 1 must not invent or implement that formula.

## Ownership boundaries

- Catalog owns sellable product identity and customer-facing product data.
- Inventory owns physical quantity, lots, provenance, locations, movements, and physical availability.
- Production owns forecasts, Batches, expenses attributable to Batches, quality decisions, and Production Releases.
- Order owns the commercial request, snapshots, required date, channel, lifecycle, and confirmed commitments.
- Payment owns payment evidence, ownership verification, and payment status.
- Fulfillment is deliberately minimal in V1 and records only what is necessary to complete the Order.

No domain silently changes another domain's facts. Cross-domain confirmation is an explicit atomic application transaction with audit evidence.

## Phase 1C customer foundation

`accounts.User` remains an internal authentication identity. `customers.Customer` is a separate business identity and has no User, Product, Branch, Inventory, Production, Order, Payment, or Fulfillment relationship in Phase 1C. Anonymous walk-in commerce does not require a fabricated Customer record.

Customer profiles and Customer addresses are mutable current information. A future Order must copy immutable customer/contact/address snapshots when the Order is created; historical Orders must never derive their recorded contact or delivery facts solely from a subsequently edited Customer profile.

Phone and email remain optional, non-unique contact fields. Phase 1D ratified Kenyan E.164 phone storage, lowercase email storage, explicit staff-selected Customer matching, and no automatic merge or identity association. Shared contacts remain valid, and neither field becomes a unique Customer identifier or an authorization credential by itself. The detailed rules are defined in the [Order, Customer and Payment contract](order-customer-payment-contract.md).

The current Customer address vocabulary is limited to county, town/area, address line, optional label, and optional delivery instructions. One active address may be explicitly marked as the default. Customer addresses never select or expose an internal Branch.

## Phase sequencing

Phase 0A aligns documentation, active prototype behavior, routes, and regression tests only. It creates no V1 domain models or migrations. Phase 1 may begin only after Phase 0A checks pass and must implement from this contract, preserving the unresolved Production costing decision for the Production phase.
