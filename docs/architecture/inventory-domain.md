# Inventory domain architecture

## Purpose and authority

Inventory is the single source of truth for **stock** owned or controlled by WayTop Farm: what item and lot exists, in what quantity and unit, at which inventory location, in what condition, under which availability restriction, and through which posted movements it arrived there.

“Every physical item” does not mean every physical fact belongs in one database aggregate. Catalog owns commercial identity; Production owns nursery work-in-progress and biological observations; Fixed Assets will own depreciable equipment; Procurement owns purchasing commitments; Finance owns monetary postings. Inventory owns the quantity ledger for stock and traceable custody handoffs. No other domain edits stock balances.

Phase 3C.7 is architecture only. It creates no screens, models, migrations, APIs, movements, deductions, procurement, accounting or calculations.

## What is an Inventory Item?

An Inventory Item is a stable stock-keeping definition for a fungible or individually tracked physical item whose quantity/custody WayTop must control. It specifies identity, stock type, base unit and permitted conversions, lot/serial/expiry requirements, handling class, category, active state and optional Catalog reference. It is not a quantity or balance; quantities belong to ledger movements and projections.

| Item family | Examples | Inventory treatment |
|---|---|---|
| Saleable plants | Released seedlings, grafted plants, rooted cuttings | Inventory after approved Production release and posted receipt; grade/lot/location retained. |
| Propagation material | Seeds, rootstocks, scions, cuttings, mother-stock harvest | Inventory when received/harvested into controlled stock; issue moves custody into Production WIP. |
| Growing inputs | Potting soil, media, compost, fertilizer | Quantity-tracked consumables; lot/expiry where risk requires. |
| Controlled chemicals | Pesticides, fungicides and other treatments | Lot, expiry, hazardous classification, restricted location and evidence required. |
| Containers/supports | Trays, pots, polybags, labels, packaging | Consumable, reusable or returnable behavior configured per item—not inferred from category. |
| General consumables | Tape, PPE consumables, cleaning material | Inventory where material enough to count/control; low-value policy may permit simplified issue. |
| Tools | Secateurs, sprayers, grafting knives | Inventory only for stores custody/issue when quantity control is appropriate; serialised high-value tools belong to a future Asset/Tool Custody domain. |

The following are not Inventory Items: labour time, electricity/water consumed without stored quantity, transport, equipment hire, repairs, contract labour, service fees, land, buildings, customer orders, Production tasks, WIP observations, money, supplier quotations and accounting accounts. Fuel can be an Inventory Item when physically stored and measured; a fuel expense without stored custody is Finance/Expense evidence.

## Categories and classification

Categories form a versioned tree using stable IDs and parent references. Names and hierarchy may change without changing item identity or historical movements. A practical initial hierarchy is:

```text
Plant Stock
├── Fruit Seedlings
├── Vegetable Seedlings
├── Tree Seedlings
└── Herbs & Ornamentals
Propagation Materials
├── Seeds
├── Rootstocks
├── Scions & Budwood
└── Cuttings & Mother-stock Material
Growing Media & Soil Amendments
├── Potting Soil & Media
├── Compost & Manure
└── Conditioners
Crop Nutrition & Protection
├── Fertilizers
├── Pesticides
├── Fungicides
└── Biological Treatments
Containers & Nursery Supplies
├── Trays
├── Pots & Polybags
├── Labels
└── Packaging
Consumables
Tools & Reusables
```

Category is for navigation/reporting and default policy only. Independent attributes define `stock_type` (material, WIP-handoff, finished good, consumable, reusable), tracking method (none/lot/serial), hazard class, shelf-life/expiry, valuation class, default unit and storage constraints. New categories therefore require configuration, not redesign.

## Inventory locations and operational areas

An Inventory Location is a ledger endpoint where on-hand stock may legally rest. A Production Area is an operational context where WIP activity occurs. One real-world place may carry both classifications, but they remain separate roles with separate IDs/policies.

| Place | Inventory location? | Production area? | Rule |
|---|---:|---:|---|
| Nursery stockholding zone | Yes, when released/input stock is stored | Possibly | WIP benches are Production-only unless explicit stores custody exists. |
| General store | Yes | No | Normal input/consumable custody. |
| Chemical store | Yes | No | Restricted inventory location with hazard/expiry policy. |
| Packing area | Yes, if picked/packed stock rests there | Operational area | Staging location; never implies sale/dispatch. |
| Hardening area | Only if released stock is formally received there | Yes | Normally Production WIP before release; dual classification requires a boundary event. |
| Receiving area | Yes | No | Controlled inspection/quarantine location, not immediately available stock. |
| Dispatch area | Yes | No | Staged/allocated stock remains WayTop-owned until dispatch/sale handoff. |
| Future branch store | Yes | No/possibly | Child of a Branch with separate capability and scope. |
| In transit | Virtual location | No | Explicit transfer custody, never hidden subtraction/addition. |
| Quarantine/damaged/disposal staging | Yes | No | Restricted stock, excluded from available projection. |

Locations form a branch-scoped hierarchy (site → store/area → zone/bin) through stable IDs. Hierarchy does not authorize access implicitly. Active dates, allowed item/condition classes and capacity metadata are configuration. History remains resolvable after closure.

## Orthogonal stock states

A single `status` field is prohibited because “reserved”, “damaged” and “transferred” can coexist or describe different facts. Future projections compose:

| Dimension | Illustrative values |
|---|---|
| Item lifecycle | Active, inactive, discontinued |
| Physical condition | Usable, quality hold, damaged, expired, rejected, disposed |
| Availability | Available, reserved, allocated, unavailable |
| Custody/location | Receiving, stored, in production, in transit, dispatch staging, customer/supplier handoff |
| Lot lifecycle | Open, depleted, closed, recalled |

“In Production” is a custody/domain handoff after issue, not available Inventory on-hand. “Transferred” is movement history; in-transit is a location/custody projection. “Disposed” is the result of a posted movement to a terminal disposition, not an editable label. Future values extend each dimension without multiplying contradictory combined states.

## Canonical transactions

Every posted transaction contains balanced movement lines over item/lot, quantity/unit, source/destination or external boundary, reason, effective and posting time, actor/approval, evidence, source-domain reference, idempotency key, correlation ID and immutable reversal links.

| Transaction | Purpose/owner | Source → destination | Future implication |
|---|---|---|---|
| Opening balance | Controlled cutover only; Inventory | External opening control → location | Approved evidence; never routine data entry. |
| Supplier receipt | Accept purchased stock; Inventory | Supplier/external → receiving/quarantine | References Procurement receipt/order but Inventory posts. |
| Internal/other receipt | Accept non-purchase stock; Inventory | Governed external/internal source → location | Reason/evidence mandatory. |
| Issue | Release stock to an authorized custodian/use; Inventory | location → external/operational custody | Generic only with governed reason; no negative stock by default. |
| Production consumption issue | Transfer materials into WIP custody; Inventory | store/lot → Production batch | References approved request/batch; Production cannot post. |
| Production release receipt | Receive approved finished seedlings; Inventory | approved Production release → inventory location/lot | Independent receipt; only this creates finished stock. |
| Transfer dispatch | Move stock between locations/branches; Inventory | source → in-transit | Source on-hand falls; destination does not rise yet. |
| Transfer receipt | Accept transferred stock; Inventory | in-transit → destination | Independent custody actor; variance handled explicitly. |
| Customer/Fulfillment sale issue | Record delivered/collected stock; Inventory | allocated/staging location → customer | Triggered through governed fulfillment/sale command, not Order table mutation. |
| POS sale issue | Record completed POS sale; Inventory | register-serving location → customer | Atomic orchestration/idempotency with sale completion; Inventory owns movement. |
| Customer return receipt | Receive returned goods for inspection; Inventory | customer → returns/quarantine | Never restores availability automatically. |
| Supplier return | Return rejected stock; Inventory | location/quarantine → supplier | References Procurement/supplier authorization. |
| Damage | Restrict or move damaged stock; Inventory | usable location/condition → damaged location/condition | Observation alone may place hold; quantity change needs posted movement. |
| Waste/disposal | Remove consumed/disposed physical quantity; Inventory | controlled location → disposal boundary | Reason, evidence and approval threshold. |
| Adjustment | Approved unexplained/authorized gain or loss; Inventory | adjustment control ↔ location | Exceptional; never substitutes for known receipt/issue. |
| Count variance adjustment | Reconcile approved count variance; Inventory | variance control ↔ counted location | Only after count investigation/approval. |
| Correction/reversal | Correct a posted movement; Inventory | Exact compensating lines | Original remains immutable; repost corrected transaction. |
| Reservation | Future commitment without physical movement; Inventory | Availability partition only | Does not change on-hand; expiry/release/consume transitions. |
| Allocation | Future fulfillment-specific commitment; Inventory | Reserved/available → allocated partition | Does not change on-hand until dispatch/sale issue. |

## Counts

Cycle and full counts share one governed workflow:

`Plan/freeze snapshot → assign blind count → record observations → recount where policy requires → investigate variance → independent approval → post variance movement → close`

Count observations never overwrite balances. Scope identifies branch/location/item/lot and snapshot time. Counters must not see expected quantity when blind-count policy applies. The counter cannot approve their own variance. Material variances require reason/evidence and Operations approval; large write-offs escalate under effective-dated policy. Concurrent movements are prevented, frozen, or reconciled explicitly rather than silently ignored.

## Transfers

Branch transfers are two-sided custody workflows:

`Draft → Submitted → Approved (when required) → Dispatched → In Transit → Partially/fully Received → Closed`

Cancelled/rejected alternatives are allowed before dispatch; post-dispatch correction uses return/reversal movements. Dispatch posts source-to-transit. Destination acceptance posts transit-to-destination. Shortage, excess, damage or wrong-item variance creates discrepancy lines and investigation; it never edits dispatch history. Initiator cannot self-approve, and source dispatcher cannot attest destination receipt except governed emergency review.

## Non-negotiable rules

- On-hand quantity is derived only from posted ledger movements.
- No domain writes an Inventory balance or movement table directly.
- Draft/cancelled transactions do not affect stock.
- Posted facts are immutable; correction uses linked reversal/repost.
- Lot, unit, location, condition and ownership/custody are explicit.
- Available, on-hand, reserved, allocated and in-transit are distinct projections.
- Negative stock is denied by default; any exception is explicit, time-bounded, approved and audited.
- Inventory authorization applies to source and destination scope, fields, conditions and approvals.
- Offline stock-changing commands are prohibited.
