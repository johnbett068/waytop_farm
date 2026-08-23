# WayTop Farm V1 Availability and Commitment Contract

Status: **Ratified**
Effective: Phase 1E-A
Prepared: 15 August 2026
Scope: Minimum saleable Inventory, Availability, Commitment, Reservation and Source Allocation contracts

## 1. Authority and supersession

This contract refines the ratified [V1 business contract](v1-business-contract.md) and [Order, Customer and Payment contract](order-customer-payment-contract.md). AC01-AC28 were ratified for Phase 1E implementation.

This document is the canonical V1 authority for Availability and Commitment. Within that scope it supersedes conflicting workflow language in older Inventory, Production, Operations, frontend and phase-review documents. Those documents remain historical evidence and do not authorize runtime behavior.

The [Phase 1E decision gate](../reviews/phase-1e-decision-gate.md) records the pre-ratification blockers. Ratification resolved that gate through AC01-AC28.

Implementation remains staged by section 24; ratification does not authorize later-phase behavior during an earlier stage.

### 1.1 Repository contradictions surfaced

- `docs/architecture/operations.md` and `docs/architecture/state-machines.md` retain pre-ratification Order states, split/failed Payment language and Cash on Pickup-era flows. The ratified V1 and Order/Payment contracts already supersede those statements.
- Several frontend documents still describe customer branch selection and mock branch availability. Those are historical prototype specifications and cannot define the persistent Availability contract.
- The Inventory planning sequence places allocation after reservation, while the ratified Order/Payment confirmation boundary requires approved internal allocations in confirmation.
- The Phase 1E decision gate recommended a later staff source-allocation option. Ratified AC12 instead requires complete owner-approved allocation during confirmation.
- Production documents are explicitly future/mock contracts and contain no approved capacity calculation.

No historical document is deleted or rewritten by this contract.

## 2. Domain boundaries

The following facts remain distinct:

| Domain | Owns | Does not own |
|---|---|---|
| Catalog | Product identity, sale units, current prices and customer-facing copy | Physical stock, reservations or commitments |
| Order | Customer request, immutable commercial snapshots, ordered/confirmed quantities and lifecycle | Inventory sources or Production capacity |
| Payment | Evidence, verification and receipt state | Availability or Order lifecycle |
| Inventory | Physical quantities, internal locations, lots, movements, reservations and source allocations | Customer entitlement or Production WIP |
| Availability | A read calculation over authoritative Inventory and, later, Production-capacity providers | Stored stock, customer entitlement or lifecycle mutation |
| Commitment | Confirmed customer entitlement, quantity history, FIFO identity and supply history | Physical stock or forecasts |
| Production | Forecasts, batches, capacity decisions and releases | Physical Inventory before an Inventory receipt |
| Fulfillment | Picking/handoff/completion work and orchestration of supply consumption | Commercial commitment or stock balances |

Customer-facing availability is not physical stock. A Commitment is not a Reservation. A Reservation is not a Source Allocation. An allocation is not an Inventory movement. A Production forecast is not Inventory.

## 3. Definitions

- **Base unit:** the Product's indivisible V1 Inventory counting unit identified by `Product.base_inventory_unit`, such as `seedling`.
- **Sale unit:** a customer-orderable `ProductSaleUnit`; one sale unit contains its positive `base_quantity` of base units.
- **Inventory Item:** the Inventory identity for one saleable Product in one base unit.
- **Inventory Location:** an internal ledger endpoint where physical stock may rest. It is never selected by a customer.
- **Stock Lot:** traceable stock of one Inventory Item with common provenance and condition.
- **Stock Position:** the current quantity of one item at one location and lot.
- **Eligible stock:** positive on-hand stock at active, saleable item/location/lot records that is not held, quarantined, damaged, expired or otherwise restricted.
- **Commitment:** the immutable confirmed customer entitlement corresponding to exactly one Order Line.
- **Reservation:** an Inventory-owned partition of eligible physical quantity for one READY Commitment.
- **Source Allocation:** the internal location/lot split selected for a Reservation.
- **Supply Event:** append-only evidence that a positive quantity of a Commitment was actually supplied through Fulfillment and, for physical goods, an Inventory issue.
- **Aggregate Availability:** a customer-safe calculation that contains no location, lot, allocation or other-customer detail.
- **Future Capacity:** a Production-owned promise candidate. It is not Inventory and is unavailable until a separate Production-capacity contract is ratified.

## 4. Minimum Inventory contract

### 4.1 Ratified records

The minimum V1 saleable-Inventory foundation contains:

1. `InventoryItem`: UUID identity, one-to-one protected Product reference, immutable base-unit snapshot, active flag and timestamps.
2. `InventoryLocation`: UUID identity, unique stable internal code, name, active flag, saleable-stock eligibility flag and timestamps. It has no required Branch relationship in this phase.
3. `StockLot`: UUID identity, protected Inventory Item reference, lot code unique within the item, condition, optional expiry date, active flag, provenance reference/text and timestamps.
4. `StockPosition`: one row unique by `(inventory_item, location, lot)`, with non-negative `Decimal(32,3)` `on_hand_base_quantity`, concurrency version and update time.
5. `InventoryMovement`: immutable command/audit header with UUID, movement type, actor, reason, source-domain reference, idempotency key, correlation ID, effective time and posted time.
6. `InventoryMovementLine`: immutable positive base quantity, item, lot, source location or external boundary, and destination location or external boundary.

No generic unit-of-measure graph is introduced in V1. Inventory Items use the Product base unit. A Product can have multiple sale units but exactly one saleable Inventory Item.

Once an Inventory Item has a Movement, Reservation or Commitment, its base-unit snapshot and the Product's corresponding base-unit meaning cannot be changed in place. A genuine unit correction requires a separately ratified conversion/migration operation.

### 4.2 Authority and projections

Immutable posted Movement Lines are the canonical history of why physical quantity changed. Stock Position is the transactionally maintained, lockable current-state record used for availability and concurrency. Every Position change must be caused by exactly one posted Movement Line in the same database transaction. Position rows must be rebuildable from the ledger; direct balance CRUD is forbidden.

`available`, `reserved`, `allocated` and `in_transit` are projections over Positions, Reservations and Allocations. They are not client-supplied balance columns.

### 4.3 Eligibility

A Position contributes to READY physical supply only when:

- Inventory Item, Location and Lot are active;
- Location permits saleable stock;
- Lot condition is `SALEABLE`;
- the optional expiry date has not passed in the Africa/Nairobi business date;
- on-hand quantity is positive; and
- no hold or restriction excludes it.

The ratified V1 lot conditions are `SALEABLE`, `HELD`, `QUARANTINED`, `DAMAGED` and `EXPIRED`. Only `SALEABLE` is eligible. Changing condition is an audited Inventory command; it is not a silent field edit.

### 4.4 Movement rules

V1 movement types are `RECEIPT`, `ISSUE`, `TRANSFER`, `ADJUSTMENT_IN`, `ADJUSTMENT_OUT` and `REVERSAL`. Quantities are always positive; direction is expressed by controlled source/destination endpoints. Negative quantity input is prohibited.

Receipts increase one destination Position. Issues decrease one source Position. Transfers decrease and increase explicit Positions in the same posted transaction. Adjustments require `inventory.adjust`, a non-empty reason and any separately configured approval. Corrections append reversing and corrected movements; posted history is never edited or deleted.

No operation may make on-hand negative. No opening stock, demo stock or Production output exists without an evidenced posted receipt.

## 5. Sale-unit to base-unit conversion

For every Order Line and Commitment:

`required_base_quantity = commercial_sale_unit_quantity * snapshotted_base_quantity`

`commercial_sale_unit_quantity` is a positive integer. `snapshotted_base_quantity` is the immutable `Decimal(12,3)` value already captured on the Order Line. Every persisted Inventory, Reservation, Allocation, Commitment-base and Supply-base quantity uses `Decimal(32,3)`. Multiplication is exact at three decimal places and must not round. Zero, negative, non-finite, overflowed or greater-than-three-decimal base quantities are rejected.

The Commitment stores all three immutable facts:

- commercial committed quantity;
- base quantity per sale unit snapshot; and
- total committed base quantity.

`OrderLine.confirmed_quantity` and `OrderLine.outstanding_quantity` remain whole-sale-unit commercial projections. Confirmation sets both to the ordered quantity. Supply reduces only outstanding quantity; cancellation moves its remaining value to zero while the Commitment preserves the cancelled quantity. The future services require a narrow internal mutation path for these counters because ordinary Order Line editing remains prohibited.

Future Catalog changes never alter an Order Line, Commitment, Reservation, Allocation or Supply Event. Availability converts base units back to sale units with floor division; the remainder is not advertised as a fractional sale unit.

Ratified V1 rule: a supplied quantity is a whole number of the snapshotted sale unit. Partial supply means fewer whole sale units than committed, not breaking one commercial sale unit. A future divisible-goods contract may revise this rule.

## 6. READY contract

READY means demand against current eligible physical Inventory only.

- A READY Commitment must have a matching READY Reservation.
- New READY availability excludes quantities reserved by any active Reservation.
- A Reservation can satisfy only its own Commitment.
- Eligible stock may be aggregated and split across multiple internal Locations and Lots.
- Lack of sufficient quantity at one Location does not fail confirmation when eligible aggregate quantity is sufficient.
- Customers never select or receive Location, Lot, Branch or allocation details.
- Confirmation creates the Commitment, Reservation and complete initial Source Allocation atomically.
- The system proposes a deterministic source split; the authorized confirmation actor approves or adjusts it before commit.
- The reserved quantity becomes unavailable to competing Orders at transaction commit.

## 7. PRE_ORDER contract

PRE_ORDER means demand intended for compatible future Production capacity. It never creates negative Inventory and cannot reserve or allocate nonexistent physical stock.

`Order.required_date` means the customer's latest acceptable ready-by calendar date in Africa/Nairobi. Eligible future capacity must have an expected-ready date on or before it. Required date controls eligibility, not FIFO priority.

A PRE_ORDER line creates one PRE_ORDER Commitment only when a ratified Production-capacity provider can be locked and reserved inside confirmation. No such provider currently exists. Therefore PRE_ORDER and mixed-Order confirmation remain unavailable; the system must report the missing capacity dependency rather than return zero or fabricate capacity.

After an approved Production Release is independently received into eligible Inventory, a future service may create a physical Reservation and Source Allocation against the existing PRE_ORDER Commitment. Its supply mode never changes to READY and Order history is not rewritten.

## 8. Commitment contract

There is exactly one Commitment per Order Line because V1 confirms the complete Order and each line has one supply mode. Partial supply creates multiple Supply Events, not multiple Commitments.

The Commitment contains:

- UUID business identity and database-generated monotonic FIFO sequence;
- protected Order and one-to-one protected Order Line references;
- immutable Product, sale-unit and supply-mode relationship through the Order Line;
- immutable commercial committed quantity;
- immutable base quantity per sale unit and total committed base quantity;
- mutable supplied, cancelled and outstanding commercial/base quantities controlled only by services;
- `ACTIVE`, `SATISFIED` or `CANCELLED` state;
- server-generated confirmation timestamp;
- copied required date for PRE_ORDER, null for READY;
- creation correlation and idempotency identity; and
- append-only Commitment events.

The quantity equation is:

`committed = supplied + cancelled + outstanding`

It applies independently to commercial and base quantities. `supplied` and `cancelled` never decrease; `outstanding` never increases above the original commitment. `SATISFIED` requires outstanding zero and cancelled zero. `CANCELLED` preserves supplied history and moves the remaining outstanding quantity to cancelled.

Commitment creation is available only inside the future atomic confirmation transaction. Direct CRUD and deletion are prohibited.

## 9. Reservation contract

Reservation is an Inventory fact distinct from customer entitlement and physical movement.

- Confirmation creates one persistent READY Reservation per READY Commitment.
- It reserves the Commitment's exact total base quantity against its Inventory Item aggregate.
- It does not change on-hand.
- It has `ACTIVE`, `CONSUMED` or `RELEASED` state and immutable initial, consumed, released and remaining quantities satisfying the same additive equation.
- It cannot transfer to another Commitment, Order or Inventory Item.
- It cannot expire or be silently reduced in V1.
- Fulfillment consumption reduces remaining reservation only with a correlated Supply Event, Source Allocation consumption and Inventory ISSUE.
- Cancellation releases only the remaining quantity and appends a release event.
- A unique Commitment relationship and locked Inventory Item supply pool prevent two Orders from reserving the same availability.

PRE_ORDER capacity reservation is deferred to the Production-capacity contract and must not reuse the physical Inventory Reservation model before stock exists.

## 10. Source Allocation contract

Source Allocation is the Inventory-owned internal mapping from a READY Reservation to specific Stock Positions.

- Allocation occurs at confirmation for READY and is mandatory for the full reserved quantity.
- Grain is `(Inventory Item, Location, Lot, base quantity)` through a Stock Position.
- One Commitment may split across multiple Locations and Lots.
- The sum of active, unconsumed allocation quantity equals the Reservation's remaining quantity.
- Allocation cannot exceed the eligible unallocated on-hand quantity of a Position.
- Reallocation is an explicit command that releases old allocation lines and appends replacements atomically; history is never overwritten.
- Source selection is deterministic: earliest non-null expiry first, null expiry last, then lot creation time, location code and stable ID. This is source selection, not customer-entitlement FIFO.
- The confirming actor requires both `payments.verify` and `commitments.allocate`; later reallocation requires `commitments.allocate`.
- Customers and public responses never receive allocations, Locations, Lots or staff actors.

The older planning sequence `reservation -> later allocation` is superseded. The ratified contract creates reservation then owner-approved allocation within the same confirmation transaction, preserving the two facts while satisfying the approved internal-allocation boundary.

## 11. FIFO contract

Customer-entitlement FIFO belongs to Commitment, not Inventory lot costing and not source selection.

- Primary order is `confirmed_at ASC`.
- Equal timestamps use the database-generated Commitment sequence ascending.
- Incidental query ordering is forbidden.
- The competition pool is compatible Inventory Item plus supply mode.
- READY and PRE_ORDER do not share a pool because they compete for different supply authorities.
- Required date is an eligibility boundary and never promotes a later Commitment ahead of an earlier eligible Commitment.
- No manual FIFO override exists in V1. Owner authority changes source allocation, not entitlement priority.
- READY reservation under row locks naturally commits in confirmation order; PRE_ORDER release allocation must query outstanding eligible Commitments by the same persisted ordering.

## 12. Aggregate Availability contract

For one Inventory Item:

`eligible_physical_base = sum(eligible Stock Position on_hand)`

`reserved_ready_base = sum(active READY Reservation remaining)`

`available_ready_base = eligible_physical_base - reserved_ready_base`

The invariant requires the result to be non-negative. Source Allocations are a partition of Reservations and are not subtracted again.

For a ProductSaleUnit:

`promiseable_ready_sale_units = floor(available_ready_base / current_sale_unit.base_quantity)`

The customer-safe result may expose the non-negative sale-unit count, availability category and calculation timestamp. It excludes Locations, Lots, Branches, other Commitments, Reservations and Allocations.

Empty Inventory returns an honest READY count of zero. A missing or unhealthy Inventory provider returns unavailable/error, not a fabricated zero. PRE_ORDER availability returns `capacity unavailable` until the Production-capacity contract exists. A mixed Order is confirmable only when every READY line passes physical availability and every PRE_ORDER line passes the future-capacity provider.

## 13. Partial supply contract

Commitments may be supplied in multiple positive whole-sale-unit increments.

Each immutable `CommitmentSupplyEvent` records Commitment, commercial quantity, exact base quantity, actor, Fulfillment reference, Inventory ISSUE reference where physical, server timestamp, reason/note, correlation ID and unique idempotency key.

A supply transaction must atomically:

1. lock the Commitment, Reservation, affected Allocations and Stock Positions;
2. reject quantity above outstanding, reservation or allocation;
3. post the physical Inventory ISSUE;
4. consume the exact Allocation and Reservation quantities;
5. append the Supply Event; and
6. update supplied/outstanding counters.

One Commitment may be supplied by multiple Lots and Locations through multiple events. Supplied quantity can never exceed committed quantity. Remaining outstanding quantity stays entitled and is never silently reduced.

## 14. Production-capacity boundary

Phase 1E knows only an interface, not Production tables or formulas. A future provider must return lockable compatible capacity identified by Inventory Item/base unit, expected-ready date, remaining reservable quantity and stable source identity. It must distinguish owner-controlled forecast from approved Production Release and must never represent future capacity as negative Inventory.

The following remain deferred: Production Batch schema, forecast effectiveness, capacity reduction rules, capacity reservation lifecycle, release allocation, loss/shortfall handling and partial-release costing. Until ratified, PRE_ORDER and mixed confirmation are unavailable.

## 15. Confirmation transaction boundary

The future `VerifyPaymentAndConfirmOrder` transaction must call these domain operations without exposing partial endpoints:

1. authorize and lock Payment and Order;
2. lock Inventory Items in stable UUID order, then eligible Positions in stable ID order;
3. request lockable Production capacity for every PRE_ORDER line;
4. calculate and revalidate aggregate availability from current facts;
5. create one Commitment per line in line-number order;
6. create READY Reservations and owner-approved complete Source Allocations;
7. create future-capacity reservations for PRE_ORDER through the future provider;
8. confirm every Order Line quantity completely;
9. confirm Payment and append verification/status history;
10. move Order from PENDING to CONFIRMED and append that event under Phase 1F decision F02; and
11. commit once.

Any failure rolls back every domain change. There is no public or staff endpoint for creating a Commitment, Reservation or initial Allocation independently of confirmation.

## 16. Cancellation implications

Phase 1G implements authorized READY Order cancellation atomically:

- lock the Order and Commitments in line order;
- release every remaining physical Reservation (future-capacity release remains deferred);
- release every unconsumed Source Allocation;
- move each remaining outstanding quantity to cancelled without changing committed or supplied history;
- append Commitment, Reservation, Allocation and Order events; and
- move only CONFIRMED or PROCESSING Order to CANCELLED.

Physical stock already issued/supplied is not silently returned. Returns and refunds remain separate future domains. `PENDING -> CANCELLED` remains prohibited. Commitment expiry remains deferred; no timer releases customer entitlement.

## 17. Fulfillment boundary

Fulfillment consumes an ACTIVE Commitment, its Reservation and Source Allocations. It may request reallocation through the Inventory service but cannot edit Inventory rows. Supply and the physical ISSUE must be atomic and correlated. Phase 1G implements minimal completion after every Commitment outstanding quantity reaches zero using `fulfillment.complete`; Phase 1G-Final implements separate explicit entry into PROCESSING using `orders.process` without changing supply facts.

No driver, route, delivery or customer-tracking workflow is introduced by this contract.

## 18. Concurrency contract

PostgreSQL is authoritative. SQLite is suitable only for ordinary model/service tests and cannot prove competing confirmation safety.

- Use `transaction.atomic()` and `SELECT ... FOR UPDATE` under PostgreSQL `READ COMMITTED` isolation.
- Lock Payment, then Order, then Inventory Item supply-pool rows sorted by stable ID, then Stock Positions sorted by stable ID, then Reservations/Allocations as applicable.
- Every Inventory mutation locks its Inventory Item before Position rows so confirmation and receipts/issues share ordering.
- Recalculate eligibility and availability after locks are acquired.
- Database checks prohibit negative Position and quantity counters; unique constraints protect Order Line Commitment, Commitment Reservation, source references and idempotency keys.
- Cross-row sums are service-enforced inside locks and verified by PostgreSQL integration tests; ordinary `CHECK` constraints cannot enforce them.
- Deadlock/serialization failures may be retried with bounded backoff using the same idempotency key.
- A repeated identical command returns the prior result; reusing a key with different input is rejected.

No success claim is permitted until PostgreSQL tests prove two competing transactions cannot over-reserve the same supply.

## 19. Permissions

Capabilities are Django permissions, not role names:

| Capability | Authority |
|---|---|
| `orders.view` | View authorized Order/Commitment summary without sources |
| `orders.cancel` | Future governed cancellation |
| `orders.process` | Explicitly start fulfillment work for a valid CONFIRMED READY Order |
| `payments.verify` | Verify payment within the atomic confirmation transaction |
| `pos.process_sale` | Create a POS-origin PENDING Order only |
| `inventory.view` | View authorized Inventory projections and internal sources |
| `inventory.receive` / `inventory.release` | Post governed receipts/issues |
| `inventory.adjust` | Request/post adjustment under approval policy |
| `commitments.view` | View internal Commitment/Reservation history |
| `commitments.allocate` | Approve initial source split and perform reallocation |
| `fulfillment.complete` | Future completion after zero outstanding quantity |

Confirmation requires active staff status plus `payments.verify` and `commitments.allocate`; it does not infer authority from a role label. Customer availability requires no internal Inventory permission but uses a redacted query contract.

## 20. Auditability

Append-only domain records capture:

- every Inventory Movement and correction;
- Commitment creation, supply and cancellation effects;
- Reservation creation, consumption and release;
- Allocation creation, approval, consumption, release and reallocation;
- manual adjustments and approvals; and
- rejected confirmation attempts at the existing audit boundary.

Each applicable record contains actor, server timestamp, previous/new state, positive quantity and unit, reason, source reference, correlation ID and idempotency key. Initial confirmation records the same correlation across Payment, Order, Commitment, Reservation and Allocation facts. No generic event-sourcing framework is introduced.

## 21. Invariants

1. Physical on-hand and READY available quantity never become negative.
2. Every Position change has one immutable posted Movement cause.
3. Movement input quantity is positive and expressed in the Item base unit.
4. One Product has at most one saleable Inventory Item in V1.
5. One Order Line has exactly one Commitment after successful confirmation and none while PENDING.
6. Commitment commercial/base quantities equal the immutable Order Line conversion.
7. `committed = supplied + cancelled + outstanding` in both units.
8. One READY Commitment has exactly one Reservation; PRE_ORDER has no physical Reservation before Inventory exists.
9. `initial reserved = consumed + released + remaining`.
10. Active Allocation remaining totals equal Reservation remaining.
11. Allocations reference eligible Positions and cannot collectively exceed their unallocated on-hand.
12. Source Allocation never changes customer entitlement or FIFO position.
13. PRE_ORDER never creates negative or fictional Inventory.
14. Payment and Order remain PENDING if any availability/capacity/commitment write fails.
15. Customers never receive Branch, Location, Lot, Reservation or Allocation detail.
16. Posted movements, Commitments and audit records cannot be edited or deleted through ordinary operations.

## 22. Forbidden behavior

- Fabricated opening stock, demo stock, availability or Production capacity.
- Customer-selected Branch, Location, Lot or source allocation.
- Direct balance editing or negative movement commands.
- Treating a Reservation, Allocation or Commitment as on-hand stock.
- Subtracting Reservations and Allocations twice.
- Splitting one commercial sale unit in V1.
- Silent reduction of committed or outstanding entitlement.
- Commitment creation before successful atomic confirmation.
- Payment or Order confirmation without all line commitments and supply reservations.
- PRE_ORDER or mixed confirmation while the Production-capacity provider is unavailable.
- FIFO ordering based on incidental database or Python list order.
- Manual FIFO override in V1.
- Raw cross-domain table mutation instead of owned service commands.

## 23. Deferred decisions

The following do not block READY foundation implementation after this contract is ratified, but they block the named later capability:

| Deferred decision | Consequence |
|---|---|
| Production capacity, reservation and release contract | PRE_ORDER and mixed confirmation remain unavailable |
| Production partial-release costing | No Production costing implementation |
| Commitment expiry/abandonment policy | No automatic release or expiry |
| Returns and restocking | Supplied stock cannot automatically re-enter availability |
| Detailed Fulfillment and Delivery | Only the future minimal supply/completion handoff is defined |
| Thresholds for adjustment approval | Adjustments require policy configuration before use |
| Branch/location hierarchy | Locations remain flat internal ledger endpoints |
| Divisible commercial sale units | V1 supply events use whole sale-unit counts |

## 24. Implementation phases

### Phase 1E-A - saleable Inventory persistence

Implement Inventory Item, Location, Lot, Position, immutable Movement/Line, eligibility rules, permissions and PostgreSQL locking tests. No stock is seeded.

Implementation status: **complete for persistence and movement posting**. PostgreSQL competing-transaction verification remains pending because the repository is configured only for SQLite. Adjustment/reversal posting remains unavailable until its deferred approval workflow exists.

### Phase 1E-B - Commitment and FIFO persistence

Implement Commitment and append-only events/counters. Commitment creation remains an internal operation unavailable outside future confirmation.

Implementation status: **complete for Commitment/FIFO persistence**. The internal creation
operation requires an existing outer confirmation transaction and is not exposed through a route,
API or writable admin. Supply, cancellation and Order confirmation remain unavailable.

### Phase 1E-C - READY Availability query

Implement aggregate physical/reserved/base-unit calculations and customer-safe sale-unit projections. PRE_ORDER returns an explicit unavailable dependency.

Implementation status: **complete for the read-only aggregate READY query**. Eligible physical
Inventory is aggregated and converted to current Sale Units without exposing sources. Phase 1E-C
originally reported reservation coverage as `NOT_IMPLEMENTED`; Phase 1E-D has now supplied the
persistent provider. No Commitment is treated as a Reservation and PRE_ORDER remains unavailable.

### Phase 1E-D - Reservation and Source Allocation

Implement READY Reservation, complete owner-approved location/lot allocation, reallocation history, cross-row transaction checks and concurrency tests. No confirmation endpoint is exposed.

Implementation status: **complete for READY Reservation and Source Allocation persistence and
service boundaries**. Availability now subtracts active Reservation remaining quantity. Initial
allocation and reallocation require a caller-owned atomic transaction, enforce READY/FIFO and
complete-allocation invariants, lock the Inventory Item and eligible Positions in deterministic
order, and preserve allocation history. PostgreSQL competing-transaction verification remains
unavailable because the repository has no PostgreSQL test environment; SQLite results are not
treated as concurrency proof. Supply consumption, cancellation and confirmation remain unavailable.

### Phase 1E-E - post-confirmation supply foundation

Implement Commitment Supply Events and the atomic Inventory issue/reservation/allocation consumption service. Do not implement Fulfillment UI, completion or cancellation.

Implementation status: **complete for the post-confirmation READY supply foundation**. The resolved
decision gate requires active Allocations to be consumed by creation/authorization sequence, then
Allocation UUID, without a caller-selected split. Authenticated active staff require
`inventory.release` under normal Django permission semantics. One atomic idempotent service posts the
Inventory ISSUE, consumes Allocation and Reservation quantity, appends supply/consumption history,
and advances Commitment and Order Line supplied/outstanding counters while leaving Order and Payment state
unchanged. Phase 1G later adds cancellation-only Reservation release and minimal Fulfillment
completion. PRE_ORDER remains unavailable. PostgreSQL competing-transaction verification remains pending because no PostgreSQL
test environment is configured.

### Production-capacity ratification and persistence

Ratify and implement the minimum future-capacity provider before PRE_ORDER or mixed confirmation.

### Phase 1F - atomic confirmation

Implementation status: **complete for the separately authorized READY-only Phase 1F boundary**.
Phase 1F decision F02 ends confirmation at CONFIRMED; entry into PROCESSING is a separate decision
gate. PRE_ORDER and mixed confirmation remain unavailable.

## 25. Ratified-decision consequences

The material ratified decisions and consequences are:

1. **Stored lockable Positions plus immutable ledger:** enables concurrency but requires strict same-transaction dual maintenance and reconciliation tests.
2. **Flat internal Locations without Branch:** avoids inventing a Branch domain but postpones hierarchy/scope behavior.
3. **Whole sale-unit supply:** preserves current integer Order Line counters but disallows breaking a tray or other commercial unit.
4. **Complete source allocation at confirmation:** satisfies the current confirmation contract and owner-control rule but requires the confirming actor to hold allocation authority.
5. **No FIFO override:** maximizes deterministic fairness but prevents urgent manual reprioritization.
6. **PRE_ORDER unavailable until Production capacity exists:** preserves truthfulness but prevents confirming preorder and mixed Orders during early rollout.
7. **Cancellation quantity:** adding cancelled quantity makes outstanding truthful after cancellation without rewriting committed or supplied history.

Alternative choices for any item require a contract revision before implementation because they change schema, permissions, locking or customer promises.

## 26. Explicit ratification checklist

Already ratified upstream:

- [x] One Order domain for Ecommerce and POS.
- [x] PENDING creation makes no commitment or allocation.
- [x] Confirmation is atomic with Payment, Order, availability and commitments.
- [x] Physical Inventory never becomes negative.
- [x] Customers see aggregate supply and no internal source.
- [x] Commitment FIFO uses confirmation time and a database sequence.
- [x] READY uses physical supply; PRE_ORDER uses future capacity without negative Inventory.
- [x] Entire Order confirmation; no partial line confirmation.

Ratified Phase 1E decisions:

- [x] AC01 - One saleable Inventory Item per Product using the Product base unit; no generic UOM graph.
- [x] AC02 - Flat internal Inventory Locations with no required Branch relationship in this phase.
- [x] AC03 - Lot eligibility conditions and optional expiry rules in section 4.3.
- [x] AC04 - Immutable Movement ledger plus transactionally maintained lockable Stock Positions.
- [x] AC05 - Positive directional movement types and no direct balance edits.
- [x] AC06 - Exact three-decimal conversion with no rounding at commitment creation.
- [x] AC07 - Whole sale-unit supply; partial supply cannot split one commercial sale unit.
- [x] AC08 - One Commitment per Order Line with immutable commercial and base quantities.
- [x] AC09 - Commitment equation includes supplied, cancelled and outstanding quantities.
- [x] AC10 - READY confirmation creates one aggregate physical Reservation per Commitment.
- [x] AC11 - Reservations are persistent, non-transferable and have no automatic expiry.
- [x] AC12 - Complete owner-approved Source Allocation is mandatory in READY confirmation.
- [x] AC13 - Allocation grain is Inventory Item, Location and Lot and may split across sources.
- [x] AC14 - Source selection order is expiry, lot creation, location code and stable ID.
- [x] AC15 - Reallocation preserves Reservation and Commitment and appends history.
- [x] AC16 - FIFO pools partition by compatible Inventory Item and supply mode.
- [x] AC17 - Required date is a latest acceptable ready-by Nairobi date and does not change FIFO.
- [x] AC18 - No manual FIFO override in V1.
- [x] AC19 - Customer READY count uses aggregate eligible on-hand minus active Reservations and floor conversion.
- [x] AC20 - Missing providers return unavailable/error, never fabricated zero.
- [x] AC21 - PRE_ORDER and mixed confirmation remain unavailable until Production capacity is ratified.
- [x] AC22 - Production receipt may later attach physical Reservation/Allocation without changing PRE_ORDER mode.
- [x] AC23 - Supply Events, Inventory ISSUE and Reservation/Allocation consumption are atomic.
- [x] AC24 - Cancellation moves unsupplied quantity to cancelled and releases remaining supply partitions.
- [x] AC25 - PostgreSQL lock ordering and idempotent retry contract in section 18.
- [x] AC26 - `commitments.view` and `commitments.allocate` are added as native capabilities.
- [x] AC27 - Confirmation actor requires both `payments.verify` and `commitments.allocate`.
- [x] AC28 - Implementation sequence in section 24, including Production capacity before Phase 1F.

AC01-AC28 are ratified. Implementation remains limited to the explicitly authorized phase; later capabilities stay unavailable until their staged prerequisites are implemented and verified.
