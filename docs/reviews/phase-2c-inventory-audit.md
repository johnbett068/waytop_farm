# Phase 2C Inventory pre-implementation architecture audit and decision gate

Status: **AUDIT COMPLETE — IMPLEMENTATION NOT AUTHORIZED**

Audit date: 31 August 2026

Scope: Inventory-only operational supplies for a seedling nursery. This document records repository
facts, conflicts, recommendations, and decisions required before implementation. It creates no
runtime authority by itself.

## Reading key and authority

- **EXISTING FACT** — directly evidenced by current code, migrations, tests, or a cited authoritative
  repository contract.
- **INFERENCE** — a consequence derived from existing facts; it is not a new rule.
- **RECOMMENDATION** — proposed future design; it is not authorized until the owner ratifies it.
- **DECISION REQUIRED** — an unresolved business or permission rule that must be ratified before
  implementation.

The authority classification used in this audit follows `docs/document-authority.md`:

| Classification | Evidence and effect in this audit |
|---|---|
| **AUTHORITATIVE** | `architecture/v1-business-contract.md`, `architecture/availability-commitment-contract.md`, the ratified Phase 1 decision records, and `reviews/phase-2a-simple-production-decision-gate.md` within SP-01–SP-05. |
| **AUTHORITATIVE TECHNICAL POLICY** | `deployment-configuration.md`; notably, the non-empty local SQLite database must be preserved and PostgreSQL is required for PostgreSQL-specific concurrency evidence. |
| **CURRENT IMPLEMENTATION** | Current Django models, migrations, services, tests, admin, dashboard routes, and views. Code proves what exists but cannot invent a business rule. |
| **HISTORICAL / FUTURE** | `architecture/inventory-domain.md`, `contracts/inventory.md`, `contracts/inventory-ui.md`, `flows/inventory-lifecycle.md`, `flows/inventory-management.md`, Phase 3C/3D Inventory reviews, and the disconnected Inventory prototype templates. They are useful design evidence but not implementation authority. |
| **CONTRADICTORY** | Prototype screens describe supplies, Production receipts/issues, returns, multi-stage transfers, counts, approvals, and posted reversals that current models/services either cannot represent or explicitly reject. They must not be treated as working behavior. |
| **UNRESOLVED** | A general operational-supply identity, its lifecycle, supplier semantics, supply permissions, and its exact movement participation are not ratified. |

## 1. Executive summary

**EXISTING FACT:** The answer to the central question is **NO**. The current architecture cannot
store an Inventory-only supply that is not a Product. `InventoryItem.product` is a non-null,
protected, one-to-one relationship to `products.Product`; its `base_unit` must equal the Product's
`base_inventory_unit`. `StockPosition` is generic only relative to `InventoryItem`, but every current
Inventory Item is necessarily Product-backed.

**EXISTING FACT:** Every current V1 Product is authoritative Phase 2A business-wise a saleable
seedling. Creating hidden Products for trays, media, seeds, fertilizer, or chemicals would collapse
the Product/operational-supply boundary and contradict that rule.

**EXISTING FACT:** The physical ledger foundation is strong and reusable: immutable movements and
lines, non-negative position constraints, Decimal(32,3) quantities, service-only balance writes,
idempotency fingerprints, atomic posting, deterministic row locks, and PostgreSQL advisory locks.
Receipts, issues, and single-step transfers are operational. Adjustment and reversal values exist
in the enum but their posting is deliberately blocked until an approval workflow exists.

**EXISTING FACT:** Production purchases are immutable production-cost records with free-text item,
unit, and supplier. They do not create Inventory Items, lots, positions, movements, reservations, or
availability. Phase 2A makes that separation authoritative. A purchase and a receipt are distinct
facts.

**RECOMMENDATION:** Reuse the one physical ledger. Add a first-class `InventorySupply` definition
and evolve `InventoryItem` into an explicit Product-or-Supply stock identity, enforced by database
XOR constraints. Do not create a second balance or movement system. Product-backed items alone may
enter customer Availability/Reservation/Allocation/Commitment/Order paths.

**DECISION REQUIRED:** Ratify INV-01 through INV-12 in section 16 before any runtime work. Several
answers are already constrained by authority (no negative stock, no automatic Production receipt,
and no customer leakage), but the future supply model and command permissions still require an
explicit decision record.

## 2. Current Inventory architecture

### Persisted relationships

| Record | Important relationship/field | Direction and nullability | Current constraints and boundary |
|---|---|---|---|
| `products.Product` | `base_inventory_unit`, `is_active`, `is_published` | Catalog root; no Inventory FK | SKU unique; inactive cannot be published; used base-unit meaning is protected. |
| `inventory.InventoryItem` | `product` | One-to-one to Product, `PROTECT`, **non-null**, unique | Base unit non-empty and must equal Product base unit; cannot delete; Product/base unit immutable once used. |
| `InventoryLocation` | no Branch relation | Independent internal location | Code unique/stable; active and `allows_saleable_stock`; cannot delete. |
| `StockLot` | `item` | Many-to-one to InventoryItem, `PROTECT`, non-null | `(item, lot_code)` unique; condition and provenance retained; direct condition changes blocked. |
| `StockPosition` | `item`, `location`, `lot` | Three protected, non-null FKs | `(item, location, lot)` unique; lot must belong to item; on-hand `Decimal(32,3) >= 0`; service-only writes. |
| `InventoryMovement` | actor; optional `reverses` | Actor protected/non-null; reversal one-to-one nullable | Unique idempotency key; conditional unique source pair; immutable/service-created. |
| `InventoryMovementLine` | movement, item, lot, endpoints | Required protected movement/item/lot; endpoint FKs nullable by shape | Positive Decimal(32,3); unique line number per movement; at least one endpoint; endpoints differ. |
| `Reservation` | commitment; inventory item | One-to-one Commitment and protected non-null item FK | Positive/equated initial, consumed, released, remaining quantities; state consistency; controlled writes. |
| `SourceAllocation` | reservation; stock position; operations | Protected non-null FKs; release operation nullable | Active position allocation uniqueness and allocation quantity equations. |
| `commitments.Commitment` | order, order line, inventory item | Protected non-null; OrderLine is one-to-one | `inventory_item.product_id` must equal `order_line.product_id`; only controlled lifecycle writes. |
| `orders.OrderLine` | Product, ProductSaleUnit, ProductPrice | Protected non-null catalog references | Commercial and price snapshots bind customer demand to a Product. |

**EXISTING FACT:** Inventory has no forms module, no Inventory-owned URL module, and no operational
Inventory views. Django admin registrations are read-only. Creation of Inventory Item, Location, and
Lot is not governed by an Inventory application service, while position/movement writes are.

**INFERENCE:** A future supply implementation must govern definition/lot creation explicitly; merely
making `product` nullable would permit ambiguous or ownerless Inventory Items and would leave current
string methods, ordering, service validation, and Availability assumptions unsafe.

## 3. Product vs Inventory boundary

### Current domain meanings

| Requested concept | Meaning proven by the repository |
|---|---|
| A. Product | Catalog identity with unique SKU, name/description, one base Inventory unit, active/publication state, sale units, and effective KES prices. Phase 2A says every current V1 Product is a saleable seedling. |
| B. Stockable item | Exactly one `InventoryItem`, which currently means the physical Inventory identity for exactly one Product in its base unit. |
| C. StockPosition | Current lockable, non-negative on-hand projection for one Inventory Item + Location + Lot. It is maintained only by posted Movement Lines. |
| D. InventoryMovement | Immutable, service-posted physical quantity event with type, actor, reason, source identity, retry identity, correlation, times, and positive directional lines. |
| E. Supply/input | No first-class Inventory concept. Production can describe an input purchase in free text, but this is not stock. Prototype templates are not persistence. |
| F. Saleable item | An active/published Product with an active ProductSaleUnit and effective ProductPrice; READY availability also requires a matching InventoryItem and eligible stock. |
| G. Production input | A free-text purchase/activity description in current Production operations. It has no Inventory identity or consumption movement link. |
| H. Customer-facing catalog item | An active, published Product exposed through Catalog; operational supplies have no supported customer surface. |
| I. Supplier purchase | A `ProductionPurchase`: immutable production-cost evidence with free-text supplier/item/unit and calculated cost; optionally linked to a Production Batch. |
| J. Stock receipt | A `RECEIPT` InventoryMovement whose lines increase destination StockPositions; no purchase is required or created. |

**AUTHORITATIVE:** Catalog owns saleable Product identity and customer-facing data; Inventory owns
physical quantities, lots, provenance, locations, movements, and availability.

**CURRENT IMPLEMENTATION:** Product → Inventory is mandatory, while Inventory → Product is exactly
one-to-one. This is narrower than the older future `contracts/inventory.md`, which proposed a stock
definition only optionally linked to Catalog.

**RECOMMENDATION:** Preserve Product as the customer seedling catalog. Do not represent an
operational supply by an unpublished/fake Product. A supply may become saleable only through an
independent, explicit future catalog decision—not automatically because it is stocked.

## 4. Production vs Inventory boundary

**AUTHORITATIVE:** The ratified SP-01–SP-05 decision record states that Production purchases do not
receive Inventory, and that no Production record changes `StockPosition`, posts an
`InventoryMovement`, or affects Availability, Commitments, Reservations, Allocations, Orders,
Payments, or Fulfillment. `READY` is an internal Production state only.

**CURRENT IMPLEMENTATION:** `ProductionPurchase` has purchase date, supplier text, item description,
category, Decimal(12,3) quantity, unit text, Decimal(14,2) unit cost, calculated total, optional
Batch, reference/note, actor, correlation, idempotency, and fingerprint. It has no FK to Supplier,
InventoryItem, StockLot, Movement, or receipt allocation. Production tests explicitly assert zero
Inventory side effects.

**INFERENCE:** Automatically converting a Production purchase into a receipt would violate the
current contract, confuse “ordered/bought” with “accepted into custody,” prevent honest partial or
rejected receipts, and risk treating the same cost record as both Production expense and Inventory
valuation without a ratified costing rule.

**RECOMMENDATION:** Keep the boundaries separate. If a later phase links them, use an explicit
Inventory receive command referencing a stable purchase or purchase-line identity and record
received quantities separately. Never make purchase creation itself a stock mutation.

## 5. Current stock/movement model

### Physical and non-physical changes

| Current type/record | Implemented meaning | Posting status | Required permission |
|---|---|---|---|
| `RECEIPT` | External boundary → destination; increases on-hand | Operational | `inventory.receive` |
| `ISSUE` | Source → external boundary; decreases on-hand | Operational; cannot go negative | `inventory.release` |
| `TRANSFER` | Source → destination in one atomic event | Operational single-step transfer | `inventory.transfer` |
| `ADJUSTMENT_IN` | Intended positive correction into a destination | Enum/schema exists; service rejects | `inventory.adjust` before rejection |
| `ADJUSTMENT_OUT` | Intended negative correction from a source | Enum/schema exists; service rejects | `inventory.adjust` before rejection |
| `REVERSAL` | Intended linked correction of a prior movement | Schema reference exists; service rejects | `inventory.adjust` before rejection |
| Reservation | Partitions eligible stock for one READY Commitment | Separate Inventory record; no on-hand change | `commitments.allocate` through orchestration |
| Allocation | Selects Location/Lot StockPositions for Reservation | Separate record; no on-hand change | `commitments.allocate` |
| Reservation release | Reduces/releases reserved/allocation quantity | Separate event/operation; no physical movement | Order cancellation permission through orchestration |
| Return | No current movement type or workflow | Not implemented | None |

**EXISTING FACT:** Stock on hand can change only through `post_inventory_movement()`. Movement input
quantities are positive, finite Decimal(32,3); direction comes from endpoints. Position writes are
locked and versioned. Direct/bulk position and movement writes are blocked.

**EXISTING FACT:** `StockLot.Condition` is `SALEABLE`, `HELD`, `QUARANTINED`, `DAMAGED`, or `EXPIRED`.
Only SALEABLE at an active saleable location contributes to READY stock. There is no supply-specific
“usable” condition or stock-kind discriminator.

**RECOMMENDATION:** Initially permit ratified supply `RECEIPT`, `ISSUE`, and current atomic
`TRANSFER` operations only. Keep adjustments/reversals unavailable until INV-07 defines approval,
audit, and separation-of-duties. Do not model reservations, allocations, or releases as physical
movement types.

## 6. Purchase vs receipt analysis

**EXISTING FACT:** The architecture already distinguishes these concepts:

- Purchase answers what was bought, from whom, when, in what commercial unit, and at what cost.
- Receipt answers what accepted physical quantity entered a lot/location, by whom, when, why, and
  from which source reference.

**CURRENT GAP:** ProductionPurchase cannot safely drive partial receipt accounting. A non-empty
`(InventoryMovement.source_type, source_reference)` pair is conditionally unique, permitting only
one Movement for that exact pair. No received-quantity allocation relates a purchase line to one or
more Movement Lines. Purchase unit text also has no controlled conversion to Inventory base units.

**INFERENCE:** Reusing one purchase reference for multiple partial receipts would violate the unique
source constraint; inventing suffixed references would obscure the domain relationship. Unit cost
also has no current place on `StockLot` or Movement Line despite the broad V1 costing direction.

**RECOMMENDATION:** A later procurement slice should introduce a purchase header/line and immutable
receipt-allocation relationship, or another explicitly ratified equivalent. A receipt may reference
a purchase line but remains an independent Inventory command. Define commercial-to-base conversion
and costing before connecting cost to stock; do not infer it from text units.

## 7. Supplier analysis

**EXISTING FACT:** Repository-wide model search finds no `Supplier` or `Vendor` entity. Production
purchases use required free-text `supplier`; Inventory receipts use optional free-text source type
and reference and lot provenance. There is no shared supplier creation UI or identity.

**INFERENCE:** Free text can preserve a snapshot name but cannot enforce identity, status, duplicate
control, contact data, or cross-purchase reporting.

**DECISION REQUIRED:** INV-09 must decide whether this Inventory phase includes a first-class shared
Supplier master or retains supplier snapshots/provenance only.

**RECOMMENDATION:** Do not put supplier ownership on `InventorySupply`; one supply can come from many
suppliers. If a Supplier master is ratified, associate it with purchase/receipt evidence and retain a
historical name snapshot. Otherwise keep explicit supplier/source text on the receipt provenance
without claiming a reusable Supplier entity.

## 8. Unit/quantity analysis

**EXISTING FACT:** Product base units are strings up to 50 characters. Inventory quantities are
Decimal(32,3), always positive on movement input, and non-negative on-hand. ProductSaleUnit converts
a commercial sale unit to the Product base unit with positive Decimal(12,3) `base_quantity`.
ProductionPurchase independently stores quantity Decimal(12,3), unit text, and two-decimal KES cost.

**INFERENCE:** Existing Inventory precision can represent pieces/trays/packets as whole decimals and
kg/litres as fractional quantities to 0.001. It does not enforce that intrinsically discrete units
are integers. ProductSaleUnit is a customer commerce concept and cannot safely be reused for bags,
bottles, or supplier packs without coupling supplies to Catalog.

**RECOMMENDATION:** Give each supply one canonical Inventory base unit and retain Decimal(32,3)
ledger quantities. Ratify per-unit fractional policy or a `quantity_scale`/unit policy if pieces,
trays, and bottles must reject fractions. Add a separate supply purchase-unit conversion only when
the exact controlled conversion and effective-date rules are approved. Cost per unit belongs to a
future purchase/cost layer, not the physical balance itself.

**EXISTING FACT:** Negative on-hand is rejected both by database constraint and locked service
validation. This must remain unchanged.

## 9. Permission analysis

**EXISTING FACT:** `InventoryItem.Meta.permissions` installs:

- `inventory.view`
- `inventory.receive`
- `inventory.release`
- `inventory.adjust`
- `inventory.approve_adjustment`
- `inventory.transfer`

Movement posting requires an authenticated, active, staff actor with the mapped capability; normal
Django superuser semantics apply. Admin is view-only and requires `inventory.view`. Commitment
allocation uses `commitments.allocate`, not an Inventory movement permission.

**CURRENT GAP:** No permission governs supply definition creation. The name `release` currently
authorizes all ISSUE movements, including customer supply; it may be too broad for operational input
consumption. `approve_adjustment` exists but no approval model/service exists. Dashboard Inventory
placeholders check only authenticated active staff status, not `inventory.view`.

**RECOMMENDATION:** Add a definition capability such as `inventory.manage_supplies`; decide whether
operational ISSUE reuses `inventory.release` or needs `inventory.issue_supplies`; retain
`inventory.receive`, `inventory.transfer`, `inventory.adjust`, and `inventory.approve_adjustment`
only for the commands their final contracts define. All reads must require `inventory.view` plus
authenticated, active staff status. Never branch on role names.

**DECISION REQUIRED:** Ratify the exact INV-10 codename-to-command table and whether adjustment
requester/approver separation is mandatory before permissions or forms are added.

## 10. Idempotency/concurrency analysis

**EXISTING FACT:** `post_inventory_movement()` is atomic. It validates a UUID idempotency key,
acquires a PostgreSQL transaction advisory lock derived from that key, fingerprints all meaningful
input, returns the same Movement for an identical retry, and rejects changed-input reuse. It then
locks Items, Lots, Locations, and Positions in deterministic order, rechecks a retry after the Item
lock, applies all lines atomically, and prevents insufficient/negative stock.

**EXISTING FACT:** SQLite executes ordinary tests but provides no PostgreSQL advisory-lock evidence.
The retained PostgreSQL concurrency suite is in `apps/orders/test_postgresql_concurrency.py`; it
tests competing confirmations/reservations, supply versus cancellation, processing, and completion.
It does not test concurrent standalone Inventory receipts or supply adjustments.

**INFERENCE:** Concurrent receipts to the same position are protected by Item/Position locking on
PostgreSQL, but creation of a new Supply/InventoryItem/Lot introduces new uniqueness races. A generic
InventoryItem must remain the canonical lock root for all physical stock kinds. Partial receipt
source identity also needs a line/allocation-level uniqueness contract.

**RECOMMENDATION:** Route supply definition, receipt, issue, and any adjustment through atomic
services with actor, UUID idempotency/correlation, canonical fingerprints, deterministic locks, and
identical-retry/changed-reuse behavior. Add direct PostgreSQL tests for simultaneous first receipt,
receipt/issue collision, competing issue, and adjustment/issue if adjustment is ratified.

## 11. Audit/history analysis

**EXISTING FACT:** Posted Movement/Line history is immutable and non-deletable. It records actor,
reason, source type/reference, idempotency key, request fingerprint, correlation ID, effective time,
posted time, item, lot, quantity, and endpoints. Reservation and allocation operations/events add
separate immutable history. Position is current state, not canonical history.

**CURRENT GAP:** Inventory Item, Location, and Lot creation lacks actor, reason, correlation,
idempotency, and an append-only definition event. Adjustment approval/rejection and condition-change
history do not exist. Receipt provenance can identify a source but not supplier identity, commercial
unit/cost, acceptance/rejection, or partial purchase allocation.

**RECOMMENDATION:** Minimum supply-definition audit: actor, created time, reason, source command,
idempotency key/fingerprint, correlation ID, and immutable code/name/base-unit creation snapshot.
Minimum receipt/issue audit: preserve all current Movement fields plus supply, lot, base quantity,
endpoints, and explicit source/demand reference. Minimum adjustment audit: request actor/time/reason,
count/evidence, before/observed/delta, independent decision actor/time/reason, and the eventual linked
Movement. Never edit posted history.

## 12. Current UI analysis

**CURRENT IMPLEMENTATION:** Dashboard routes exist for Inventory dashboard, items/detail, lots,
movements, receiving, transfers, counts, and adjustments. Every route calls `_empty()` and renders a
truthful empty-state page. `_empty()` requires login plus active staff status but not
`inventory.view`. There are no Inventory forms or POST handlers.

**HISTORICAL / FUTURE:** `templates/dashboard/inventory/` contains elaborate mock screens for media,
chemicals, trays, supplier receipts, Production consumption/releases, customer returns, staged
transfers, counts, adjustments, and reversals. Current views do not render those templates. Their
sample facts and capabilities are not persisted, and several flows exceed current authority.

**CURRENT GAP:** Staff cannot create a supply, create a Product-backed Inventory Item/lot/location,
receive stock, issue/consume it, see a real balance/history, or request/approve an adjustment through
the dashboard. Admin is intentionally read-only.

**RECOMMENDATION:** Replace only the necessary placeholders after ratification with a compact module:
Stock, Supplies, Receive Stock, Adjust Stock, and Stock History. Keep Product stock and operational
supplies visibly distinguished. Do not expose Inventory pages or supply records to customers.

## 13. Database/migration analysis

**EXISTING FACT:** The applied migration graph contains 38 migrations. Inventory has five applied
migrations: `0001_initial`, `0002_reservation_reservationevent_and_more`,
`0003_alter_sourceallocationoperation_kind_and_more`,
`0004_alter_sourceallocationoperation_kind`, and `0005_initial_history_constraints`.
Production has applied `0001_initial`. No migration was created or executed during this audit.

**EXISTING FACT:** Existing unique/check constraints include Product↔InventoryItem one-to-one;
non-empty base unit; unique location code; unique `(item, lot_code)`; unique
`(item, location, lot)`; non-negative on-hand; positive movement lines; unique idempotency; unique
non-empty movement source pair; valid endpoints/reversal reference; and reservation/allocation
quantity equations. Django creates FK and uniqueness indexes as part of these migrations.

**INFERENCE:** A schema change is necessary. The existing table cannot represent non-Product stock
without violating its non-null Product FK and validation. Simply adding Supply metadata to Product
would violate the domain boundary.

**RECOMMENDATION:** Use new additive migrations only. Add the Supply definition and nullable supply
link/discriminator first, backfill every existing InventoryItem as Product-backed, then alter
`product` nullable and add database constraints that require exactly one owner. Review ordering,
string representations, service `select_related`, and historical data before enforcing final XOR.
Do not rewrite migrations 0001–0005.

**EXISTING FACT:** The local `db.sqlite3` is protected development data under technical policy. It
was read only for migration state during this audit; no migrate, flush, seed, or data write ran.

## 14. Test coverage analysis

### Covered now

**EXISTING FACT:** `apps/inventory/tests.py` covers Product one-to-one/base-unit behavior, protected
relationships, lot/location rules, service-only/immutable writes, receipt, issue, transfer,
multi-line rollback, Decimal precision, endpoint validation, negative-stock prevention,
idempotent retry/changed reuse, source uniqueness, permissions, unavailable adjustments/reversals,
constraints, read-only admin, and no fabricated stock.

**EXISTING FACT:** `apps/inventory/test_availability.py` covers eligible Product stock aggregation,
sale-unit floor conversion, lot/location/item status and expiry, reservation subtraction, PRE_ORDER
rejection, provider failures, customer-safe aggregation, and query non-mutation.

**EXISTING FACT:** `apps/inventory/test_reservations.py`, Commitment supply tests, Order lifecycle
tests, and the PostgreSQL Order concurrency suite cover READY reservation/allocation/FIFO,
release/consumption, physical ISSUE integration, authorization, audit/idempotency, and competing
sales lifecycle mutations. Production tests assert that batches and purchases never mutate
Inventory.

### Missing for the proposed scope

**RECOMMENDATION:** Future focused tests must cover:

1. supply definition creation, normalization, uniqueness, immutability/deactivation, permissions,
   idempotency, and concurrent duplicate creation;
2. database XOR: exactly one of Product or Supply, never neither/both, with safe existing-row
   migration and protected history;
3. Product and Supply base-unit matching and fractional-unit policy;
4. supply receipt creating the correct lot/position/movement once, including first-position races,
   partial receipts, source uniqueness, and rollback;
5. supply issue/consumption, transfer, negative-stock denial, inactive/held/expired records, and
   concurrent issue/receipt behavior;
6. adjustment request/approval/rejection/separation, exact linked movements, retry identity, and
   concurrency—but only if INV-07 authorizes adjustment;
7. categorical exclusion of Supply items from Product queries, public catalog, ProductSaleUnit,
   Availability, Commitment, Reservation, Allocation, Order, Payment, and customer routes;
8. continued Production purchase/READY zero-side-effect behavior and explicit receipt separation;
9. permission-denial and normal superuser behavior for every new read/command; and
10. staff UI empty/success/error/duplicate-submit flows with no fabricated rows.

No tests were run in this audit because runtime behavior was intentionally unchanged; verification
was limited to read-only inspection and `git diff --check` after documentation creation.

## 15. Identified technical gaps

1. **EXISTING FACT:** Mandatory Product FK prevents non-Product stock.
2. **EXISTING FACT:** Services and model presentation dereference `item.product` directly.
3. **EXISTING FACT:** Availability has no stock-kind filter because Product ownership is currently
   structurally guaranteed.
4. **EXISTING FACT:** No first-class supply/category/unit policy or Supplier model exists.
5. **EXISTING FACT:** Definition/lot/location creation lacks controlled services and audit events.
6. **EXISTING FACT:** Adjustment/reversal schema is ahead of the deliberately blocked service.
7. **EXISTING FACT:** Product-oriented `SALEABLE` lot condition does not define supply usability.
8. **EXISTING FACT:** Purchase text units have no controlled base-unit conversion, and partial
   purchase receipts have no allocation model.
9. **EXISTING FACT:** Dashboard Inventory pages are staff-only empty placeholders and omit
   `inventory.view`; prototypes are disconnected.
10. **EXISTING FACT:** No direct PostgreSQL concurrency tests cover standalone receipt/issue races.

**INFERENCE:** These are additive architecture gaps, not evidence that the existing ledger should be
replaced. Most physical quantity behavior can be reused once stock identity and eligibility are made
explicit.

## 16. Identified business decisions

The audit directive states the desired boundary, but the current authority index does not yet
ratify a Phase 2C runtime contract. The following proposed answers therefore require owner approval
as one decision gate.

### INV-01 — Can Inventory contain stockable supplies that are not Products?

**CURRENT ANSWER:** No; the schema requires Product.

**DECISION REQUIRED / RECOMMENDATION:** **YES.** Authorize first-class Inventory-only operational
supplies without creating Products.

### INV-02 — Should Inventory supplies ever appear in the customer Product catalog?

**AUTHORITATIVE CONSTRAINT:** Current Products are saleable seedlings; Catalog owns customer-facing
identity.

**DECISION REQUIRED / RECOMMENDATION:** **NO automatic or implicit appearance.** A supply remains
internal. Selling one later requires a separate explicit Catalog Product and a separately ratified
mapping policy.

### INV-03 — Should receiving a supply automatically create stock?

**EXISTING FACT:** A posted RECEIPT already creates/increments StockPosition in the same transaction;
creating an item or purchase does not.

**DECISION REQUIRED / RECOMMENDATION:** **YES only when an authorized receipt is successfully
posted.** Supply definition and purchase entry create no stock. Failed/draft preview creates none.

### INV-04 — Should Production purchases automatically create Inventory receipts?

**AUTHORITATIVE ANSWER:** **NO.** SP-01–SP-05 expressly forbid it.

**RECOMMENDATION:** Do not reopen this decision. A future explicit receipt may reference purchase
evidence but must be independently authorized and idempotent.

### INV-05 — What stock movement types are allowed for supplies?

**EXISTING FACT:** RECEIPT, ISSUE, and TRANSFER post; ADJUSTMENT_IN, ADJUSTMENT_OUT, and REVERSAL are
defined but blocked. Reservation/allocation/release are non-physical records. RETURN is absent.

**DECISION REQUIRED / RECOMMENDATION:** Initially allow supply RECEIPT, ISSUE, and the current atomic
TRANSFER. Keep adjustment/reversal blocked pending INV-07. Do not add RETURN or prototype-specific
types in this phase.

### INV-06 — Can supplies have decimal quantities?

**EXISTING FACT:** The ledger is Decimal(32,3).

**DECISION REQUIRED / RECOMMENDATION:** **YES, to three decimal places**, with a controlled base unit
per supply. Require whole quantities for unit policies classified discrete, if that policy is
included; otherwise explicitly accept decimals for every supply in the first slice.

### INV-07 — Can staff adjust supply stock?

**CURRENT ANSWER:** No posting service exists despite permissions/enum values.

**DECISION REQUIRED / RECOMMENDATION:** **YES only through a separately approved request/review
workflow** with reason/evidence, requester/approver separation, exact delta, immutable decision,
idempotency, and linked movement. If that workflow is not approved now, defer Adjust Stock entirely.

### INV-08 — Are negative on-hand quantities allowed?

**AUTHORITATIVE/CURRENT ANSWER:** **NO.** The V1 contract, database constraint, and locked service all
deny negative physical stock.

**RECOMMENDATION:** Do not reopen or weaken this invariant.

### INV-09 — Should Inventory supplies have suppliers?

**CURRENT ANSWER:** No Supplier entity exists; Production stores free text.

**DECISION REQUIRED / RECOMMENDATION:** Preserve optional supplier/source provenance on receipts,
but do not attach one supplier as an attribute of a supply. Decide separately whether this phase
creates a shared Supplier master; the minimal Inventory slice can defer it and retain source text.

### INV-10 — What permissions are required?

**DECISION REQUIRED / RECOMMENDATION:** Require active authenticated staff plus:

| Command | Proposed capability |
|---|---|
| Read supply/stock/history | `inventory.view` |
| Create/update-before-use/deactivate supply definition | `inventory.manage_supplies` (new) |
| Post receipt | existing `inventory.receive` |
| Post operational issue/consumption | decide new `inventory.issue_supplies` versus existing broad `inventory.release` |
| Transfer | existing `inventory.transfer` |
| Request adjustment | existing `inventory.adjust` |
| Approve/reject adjustment | existing `inventory.approve_adjustment` |

Normal Django superuser semantics apply. No role-name logic. The issue codename and separation rule
must be explicitly selected before implementation.

### INV-11 — What audit/idempotency rules apply?

**EXISTING FACT:** Physical mutations already require atomic posting, actor, reason, source,
idempotency/fingerprint, correlation, timestamps, immutable lines, and locked revalidation.

**DECISION REQUIRED / RECOMMENDATION:** Apply the same envelope to every supply definition and stock
mutation. Identical retry returns the original result; same key with changed input rejects; posted
history cannot be edited/deleted. Adjustment additionally requires immutable request and approval.

### INV-12 — Should supply stock participate in Availability, Reservation, Allocation, or Orders?

**AUTHORITATIVE CONSTRAINT:** Those current customer paths are Product/OrderLine based.

**DECISION REQUIRED / RECOMMENDATION:** **NO.** Enforce this structurally with explicit stock kind,
Product-only Availability lookup/filtering, and regression tests. Supplies also have no Payment or
customer UI effect.

## 17. Recommended future Inventory model

**RECOMMENDATION:** Use one physical ledger with two explicit stock-definition owners:

```text
Product (saleable seedling) ──0..1──┐
                                   ├── InventoryItem ──< StockLot
InventorySupply (internal) ─0..1───┘                       │
                   exactly one owner                       └──< StockPosition
                                                                  │
                                                   InventoryMovementLine
```

Proposed minimum `InventorySupply` fields are UUID, unique stable code, name, controlled category
(or defer category rather than free-form fake classification), canonical base unit, active flag,
created/updated timestamps, and controlled creation audit identity. It owns no stock quantity,
supplier, price, ProductSaleUnit, or customer publication field.

Proposed `InventoryItem` evolution:

- nullable protected one-to-one `product`;
- nullable protected one-to-one `supply`;
- explicit immutable kind (`PRODUCT`/`SUPPLY`) if useful for readable constraints and queries;
- database XOR requiring exactly one owner and agreement with kind;
- base unit must equal the selected owner's canonical base unit;
- owner/kind/base-unit meaning immutable after any movement, reservation, or commitment;
- StockLot, StockPosition, Movement, and MovementLine continue to reference InventoryItem unchanged.

**RECOMMENDATION:** Availability must accept a Product and resolve only a Product-kind InventoryItem.
Reservation/Commitment validation must continue to require the same Product. Supply Items must be
ineligible regardless of location/lot condition. Define a supply-appropriate usable/held condition
policy before posting supply stock; do not silently interpret `SALEABLE` as “usable in Production.”

**RECOMMENDATION:** Reject alternatives that (a) create hidden Products, (b) add quantity directly to
Supply, or (c) create a parallel supply balance/movement ledger. They respectively break Catalog
semantics, ledger integrity, or single-source stock history.

## 18. Recommended staff workflow

**RECOMMENDATION:** After gate approval, implement the smallest server-backed workflow:

1. **Supplies:** list/search active and inactive definitions; create a supply code/name/base unit;
   creation posts no stock.
2. **Receive Stock:** select Supply, existing/new controlled lot, destination, accepted base
   quantity, date, reason, source/supplier reference, and retry identity; successful RECEIPT posts
   Movement/Line and creates or increments Position.
3. **Stock:** show Product Stock and Operational Supplies with an explicit type label, canonical unit,
   aggregate on-hand, and no mixed-unit grand total.
4. **Stock History:** filter immutable movements by supply, lot, location, type, date, source, and
   correlation; expose no edit/delete action.
5. **Issue/Consume:** if INV-05/10 authorize it, post an ISSUE against a stated operational demand;
   do not fabricate Production consumption integration.
6. **Adjust Stock:** expose only if INV-07 ratifies the full request/approval workflow; otherwise show
   no enabled adjustment command.

Every page requires `inventory.view`; each form additionally requires its exact command capability.
The server reauthorizes and validates inside the transaction. Duplicate submit uses the same
idempotency key.

## 19. Explicit non-goals

This audit does not authorize or propose implementation of customer supply pages; making supplies
Products; crop farming/harvesting/livestock/field/irrigation behavior; automatic Production READY or
purchase handoff; Production WIP consumption; PRE_ORDER capacity; deep Procurement; purchase
approval/payables/accounting/tax/COGS/valuation; payroll/HR; returns/refunds; delivery; promotion;
generic unit graphs; negative stock; multi-stage transfer/count workflows; offline writes; demo/seed
data; or changes to Orders, Payments, Availability, Reservations, Allocations, Commitments, or
Fulfillment.

## 20. Implementation readiness

**CURRENT STATUS:** **NOT READY / BLOCKED ON OWNER DECISIONS.** The repository has a reusable ledger,
but runtime work must not start until INV-01–INV-12 are ratified, with explicit selection for:

- the Product-or-Supply stock identity and XOR model;
- supply unit/fraction policy and usable condition;
- allowed movements and whether adjustment is in or out;
- Supplier master versus receipt provenance text;
- exact permission codenames, especially supply issue; and
- the categorical customer Availability/Order exclusion.

After ratification, implementation can be additive. It will require new models/fields/constraints,
new migrations (never rewritten history), service and UI work, focused/regression tests, protected
SQLite migration according to technical policy, and PostgreSQL-specific concurrency verification
when that environment is available.

## 21. Exact next action

**DECISION REQUIRED:** The owner should approve INV-01 through INV-12 exactly as recommended above,
or provide explicit replacements for any numbered item. Do not begin implementation on an implied or
partial approval.

Once ratified, create a separate Phase 2C implementation authorization bounded to the approved
Supply definition, Product-or-Supply InventoryItem migration, Product-only customer eligibility,
receipt/issue commands, selected permissions, staff pages, migrations, and tests. Preserve the
authoritative rule that Production purchases and READY batches create no Inventory automatically.

## 22. Ratification and implementation record

Status: **IMPLEMENTED AND RELEASE-VERIFIED — 1 September 2026**

The owner ratified INV-01 through INV-12 in
`phase-2c-supplier-inventory-decision-gate.md`. That later authoritative record supersedes the
pre-decision `NOT READY` status in section 20 without changing this audit's historical findings.

### Implemented scope

- Added first-class Supplier and immutable Supplier audit history.
- Added first-class InventorySupply and append-only definition history. Supply code, base unit, and
  fractional/discrete policy are stable; staff may update the name/category and deactivate or
  reactivate the definition through the audited service.
- Evolved InventoryItem to explicit PRODUCT or SUPPLY ownership with a database XOR constraint.
- Retained one StockLot/StockPosition/InventoryMovement ledger for both kinds while making all
  customer Availability, Reservation, Allocation, Commitment, Order, and Payment paths explicitly
  Product-only.
- Added simple Supplier Purchase Orders, immutable commercial snapshots and totals, place/cancel
  transitions, partial Goods Receipts, accepted/rejected quantities, rejection reasons, delivery
  references, and receipt-to-InventoryMovement evidence.
- Added two-person Inventory adjustment request/approval orchestration. Direct adjustment posting is
  rejected; approval posts the exact authorized movement and cannot create negative stock.
- Added permission-protected Supplier, Supply, Purchase Order, Goods Receipt, Inventory overview,
  stock, history, and adjustment pages. The Purchase Order form explains purchase units, deterministic
  base conversion, KES unit cost, internal versus supplier references, calculates the displayed total,
  and states that creating an order adds no stock.
- Refactored every Supplier, Supply, Purchase Order, Goods Receipt, and adjustment form into
  responsive block/grid field groups. Labels render above controls, help and validation text render
  below them, checkboxes retain native sizing, and the existing field names, IDs, POST targets, and
  service contracts remain unchanged.
- Added one shared Inventory and Procurement shortcut bar to the staff shell. It provides direct
  links to the Inventory overview, on-hand stock, receipt form, Supply definitions, Purchase Orders,
  Suppliers, and ledger history on every Inventory or Procurement screen, with a linked Inventory
  breadcrumb and accessible active-page state.
- The Inventory overview separates saleable seedling Products from operational Supplies, shows
  authoritative zero/out-of-stock states and recent movements, and explicitly reports that no
  low-stock threshold exists rather than inventing one.

ProductionPurchase and Production READY transitions retain zero Inventory side effects. No customer
Supply UI, Product conversion, Production consumption, PRE_ORDER, returns, Accounting, tax, payable,
vendor-payment, payroll, promotion, or demo-data behavior was added.

### Models and migrations

Inventory adds InventorySupply, InventorySupplyEvent and InventoryAdjustmentRequest and changes
InventoryItem ownership. Procurement adds Supplier, SupplierEvent, SupplierPurchaseOrder,
SupplierPurchaseOrderLine, PurchaseOrderEvent, SupplierGoodsReceipt and GoodsReceiptLine.

Only additive migrations were created:

- `inventory.0006_inventorysupplyevent_alter_inventoryitem_options_and_more`
- `procurement.0001_initial`
- `procurement.0002_suppliergoodsreceipt_goods_receipt_number_not_empty_and_more`

Historical migrations were not modified. The Inventory migration's RunPython is necessary because
the explicit `kind=PRODUCT` backfill must occur before Product is made nullable and the XOR constraint
is installed; it aborts if an old InventoryItem unexpectedly lacks a Product. No other data migration
or SQL escape hatch was used.

The migrations were applied to the preserved local SQLite development database. Applied migrations
increased from 38 to 41 and tables from 44 to 54. SQLite `PRAGMA integrity_check` returned `ok`.
The preserved database still contains its existing user, Product and two ProductionBatch records;
Phase 2C Supplier, Supply, Purchase Order, Goods Receipt, InventoryMovement and StockPosition tables
remain empty because no demo or fabricated business data was created.

### Permissions

The implementation uses `procurement.view`, `procurement.manage_suppliers`,
`procurement.manage_purchases`, `inventory.view`, `inventory.manage_supplies`, `inventory.receive`,
`inventory.adjust`, and `inventory.approve_adjustment`. Services require an authenticated, active
staff actor and the exact permission; normal Django superuser semantics remain intact. No permission
was granted automatically.

### Verification evidence

- Focused staff UI layout/navigation tests: **8 passed**, covering all 21 rendered Inventory and
  Procurement screens and every required shortcut destination.
- Full SQLite suite: **333 passed**, with 12 PostgreSQL-only tests skipped.
- Full PostgreSQL 18 suite in a real disposable local cluster: **333 passed with no skips**, including
  all 12 multithreaded concurrency tests.
- `manage.py check`: no issues.
- production-profile `manage.py check --deploy`: passed, with only the two owner-controlled HSTS
  preload/include-subdomains advisories.
- `makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: passed; only Git's Windows LF-to-CRLF notices were emitted.

Technical defects found and fixed during PostgreSQL verification were nullable-join row locks in the
new purchasing path and pre-existing Product Inventory paths. Each lock was narrowed to its intended
authoritative row with `select_for_update(of=("self",))`; no lifecycle semantics changed.

### Remaining technical debt

There is no Phase 2C release blocker. Low-stock/reorder thresholds, multi-line dynamic browser forms,
returns, invoices/payables, valuation/COGS, supplier payments, and automatic Production material
consumption remain intentionally deferred. A Goods Receipt records accepted/rejected base quantity;
its linked immutable Purchase Order line remains the authoritative purchase unit and conversion
snapshot, avoiding a second conflicting unit definition on receipt.
