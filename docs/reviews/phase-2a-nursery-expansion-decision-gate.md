# Phase 2A Nursery Operations expansion decision gate

Status: **OPEN — IMPLEMENTATION STOPPED ON AUTHORITATIVE CONTRADICTION**

Audit date: 1 September 2026

## Purpose

The latest Nursery Operations implementation directive was reconciled against the implemented and
ratified `phase-2a-simple-production-decision-gate.md` and the later Phase 2C Supplier Inventory
contract. The repository already implements the complete authorized Simple Phase 2A boundary:

- Product-backed ProductionBatch with `PLANNED -> IN_PRODUCTION -> READY -> CLOSED`;
- exact started/current quantities and append-only Batch events;
- separate immutable ProductionPurchase, ProductionLabour, and controlled NurseryActivity facts;
- explicit Production permissions, active-staff checks, atomic services, audit identities,
  idempotency/fingerprints, server-derived costs, staff forms, dashboard, history, and tests; and
- zero automatic Inventory, Availability, Order, Payment, or customer effects.

The new directive also requests or investigates structured germination, losses/rejections, ready
output, seed/input usage, nursery context, pest/disease treatment detail, and completed output that
may eventually become Inventory. Those concepts are outside the ratified Simple Phase 2A boundary
and require rules the directive expressly forbids the implementation from inventing.

No runtime code, model, migration, permission, or database record was changed while this gate is
open.

## Direct contradictions

1. The authoritative SP gate says Nursery activities with equal operational semantics may use one
   controlled Activity model. The new directive says not to collapse every concept into one generic
   Activity and describes structured inspection, treatment input, result, and follow-up facts. It
   does not decide which facts have materially different lifecycle or audit semantics.
2. SP-03 defines only `quantity_started` and decreasing `current_quantity`; READY is an internal
   state with no Inventory effect. The new directive asks for germinated, rejected/lost, ready, and
   completed-output quantities but supplies no governing equation or correction rules.
3. SP-03 and Phase 2C explicitly prohibit automatic Production-to-Inventory effects. The new
   directive requires controlled completed output and describes an eventual Output-to-Inventory
   relationship without deciding whether output is evidence only, which Inventory command receives
   it, or who independently authorizes that handoff.
4. Phase 2C authorizes InventorySupply receipts and the generic Inventory ISSUE movement, but does
   not authorize Production consumption, demand identity, lot/location selection, or automatic
   material use. The new directive requests input usage while naming unclear Inventory mutation
   ownership as a stop condition.

## Decisions required

### NX-01 — Authority and phase boundary

**Decision required:** Does the owner retain the completed Simple Phase 2A boundary, or explicitly
supersede/refine it with a new Nursery Operations expansion phase?

**Recommendation:** Keep Phase 2A complete and name this work Phase 2D (or another new phase). Do not
silently reinterpret SP-01 through SP-05.

### NX-02 — Quantity ledger and equations

**Decision required:** Define the authoritative meanings and exact equations for started, current
WIP, germinated, lost/rejected, graded, ready, and completed-output quantities. State whether the
facts are cumulative or point-in-time, whether partial output is allowed, how corrections work, and
what CLOSED requires.

The current equation remains only `0 <= current_quantity <= quantity_started`. No additional
quantity may be persisted until its relationship to current WIP is ratified.

### NX-03 — Production output evidence

**Decision required:** Is completed output a new append-only Production-owned record, or is READY's
current quantity the only completion fact? Define uniqueness/partial-output rules, lifecycle
prerequisites, actor/reason, idempotency, correction, and cumulative caps.

**Recommendation:** If a new output record is authorized, make it Production-owned evidence only.
It must create no StockPosition, Movement, Availability, Reservation, Allocation, Commitment, Order,
or Payment effect by itself.

### NX-04 — Inventory handoff

**Decision required:** Separately authorize or defer the Inventory-owned receipt that may accept a
Production output. Define the receiving permission, independent approval if any, destination
Location, StockLot identity/condition, source reference, idempotency, concurrency lock roots, partial
receipt rules, and duplicate prevention.

**Recommendation:** Continue to defer the handoff. READY and Production output should retain zero
Inventory effect until this complete cross-domain contract is approved.

### NX-05 — Production input consumption

**Decision required:** Define whether Production may request InventorySupply consumption. If yes,
define the Production demand identity, permitted Supply categories, source lot/location selection,
quantity unit, ISSUE permission, actor separation, reversal/correction policy, and whether recording
an activity may ever trigger consumption automatically.

**Recommendation:** Never make Activity creation consume stock automatically. Use a separate,
explicit Inventory-owned ISSUE command only after this contract is ratified.

### NX-06 — Structured nursery operations

**Decision required:** Identify which of germination, inspection, grading, loss/rejection,
pest/disease/weed observation, treatment, outcome, and follow-up require dedicated structured facts
rather than the current controlled NurseryActivity type plus description. For each selected fact,
define required fields, statuses, quantity effects, edit/correction rules, and permission mapping.

The current Activity model remains valid for watering, fertilizing, weeding, pest management,
disease management, grading, cleaning, and other observations that share its existing append-only
operational semantics.

### NX-07 — Nursery, area, seed lot, and location identity

**Decision required:** Decide whether nursery/bed/area is free operational context, a new Production
identity, or a controlled reference to InventoryLocation. Decide whether source seed lot is an
Inventory StockLot, a supplier/reference string, or separate Production provenance. Define behavior
when referenced records are inactive and prevent Production from taking ownership of Inventory
entities.

## Preserved boundaries while open

- No crop farming, harvest, harvested-product, livestock, field, irrigation, or customer Production
  behavior.
- No Product, Order, Payment, Fulfillment, PRE_ORDER, payroll, accounting, tax, or delivery changes.
- No automatic ProductionPurchase receipt, activity consumption, READY receipt, or output receipt.
- Existing Phase 1 lifecycle and Phase 2C Supplier Inventory semantics remain unchanged.
- The protected local SQLite database and all historical migrations remain unchanged.

## Exact next action

The owner should approve NX-01 through NX-07, preferably as a separately named Nursery Operations
expansion phase. Implementation may then proceed only for the selected structured facts and must
retain a separately authorized Inventory handoff.
