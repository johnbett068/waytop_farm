# Phase 2A Simple Production Operations decision gate

Status: **RATIFIED — AUTHORITATIVE FOR PHASE 2A**

Audit date: 31 August 2026

Ratified by the owner: 31 August 2026. SP-01 through SP-05 are approved exactly as recommended.

## Outcome

The Simple Production Operations directive ratifies a seedling-nursery scope and clearly excludes
Inventory mutation, PRE_ORDER integration, payroll, accounting, supplier management, and fabricated
data. Those boundaries are compatible with the current Phase 1 architecture.

The decisions below resolve the former stop conditions and authorize the bounded Phase 2A runtime
implementation. They do not authorize a Production-to-Inventory handoff or any excluded domain.

## Repository evidence

- `apps.products.Product` contains identity, description, base Inventory unit, publication state,
  and timestamps. It has no category, product type, or `is_seedling` field. Documentation describes
  a seedling-only master catalog, but documentation fixtures are not persisted Product
  classification and cannot enforce Production selection.
- There is no Production Django app, model, migration, service, or installed permission.
- Existing Phase 1 mutation services require an authenticated, active staff actor **and** an
  explicit Django capability. The current Production placeholder is read-only and permits any
  authenticated active staff user.
- Inventory changes only through `post_inventory_movement()`. The Simple Production directive does
  not authorize a Production-to-Inventory handoff, so batches, purchases, labour, and activities
  must remain operational records with no Inventory side effect.
- The configured local backend is SQLite. All 37 configured migrations are applied and
  `makemigrations --check --dry-run` reports no changes at this baseline.

## Decisions required

### SP-01 — Eligible Product relationship

**Question:** Which persisted Products may be selected for a Production Batch?

The model cannot currently distinguish a saleable seedling from a future input or other Product.
Choose one rule:

1. every active Product is, by business invariant, a seedling and is eligible;
2. add an authoritative Product classification and permit only active seedling Products; or
3. provide another explicit eligibility rule based on an existing persisted field.

**Recommended decision:** ratify that every current V1 Product represents a saleable seedling and
that only active Products are batch-eligible. Add classification later only if the Product catalog
will contain non-seedling items. This keeps Simple Production additive and avoids an unnecessary
Product migration.

### SP-02 — Production permissions

**Question:** Which exact Django permissions authorize reads and each mutation?

Active-staff status alone matches the current empty placeholder but not the capability checks used
by authoritative Phase 1 mutation services. Adding permissions without ratification is expressly
forbidden by the directive.

**Recommended decision:** install these minimum capabilities on `ProductionBatch`:

- `production.view_operations` — view dashboard, batch lists, and batch details;
- `production.manage_batches` — create batches and perform allowed transitions/quantity updates;
- `production.record_purchases` — create purchase records;
- `production.record_labour` — create labour records; and
- `production.record_activities` — create nursery activity records.

Every read or command must additionally require authentication, active status, and staff status.
Normal Django superuser semantics apply. Confirm whether all five capabilities are approved or
provide replacement codenames and mappings.

### SP-03 — Batch lifecycle and quantity changes

**Question:** What are the exact legal transitions and mutation rules?

The four labels do not establish whether creation may start in `IN_PRODUCTION`, whether a Batch can
move backward, what `READY` means without Inventory, whether `CLOSED` is terminal, or how
`current_quantity` may change.

**Recommended decision:**

- create only in `PLANNED`;
- allow `PLANNED -> IN_PRODUCTION -> READY -> CLOSED` only;
- make `CLOSED` terminal and forbid reopening;
- define `READY` as an internal Production state only, with no Inventory or customer-availability
  effect;
- use the Product `base_inventory_unit` for both quantities with Decimal precision of three places;
- require `quantity_started > 0` and `0 <= current_quantity <= quantity_started`;
- allow current quantity to decrease while the Batch is not `CLOSED`, requiring an actor and reason;
- require `current_quantity > 0` before entering `READY`; and
- require `expected_ready_date >= start_date`.

Confirm this complete rule or provide the replacement transition table and quantity constraints.

### SP-04 — Cost and effort semantics

**Question:** Are totals authoritative entered values or server-derived values?

Purchase and Labour request both a rate/unit cost and total cost, while Labour permits either hours
or days. The brief does not specify equations, rounding, or correction behavior.

**Recommended decision:**

- store Purchase `quantity`, `unit_cost`, and a server-derived `total_cost = quantity * unit_cost`;
- store Labour `effort_quantity`, controlled `effort_unit` (`HOURS` or `DAYS`), `rate`, and a
  server-derived `total_cost = effort_quantity * rate`;
- quantize money to KES 0.01 using decimal round-half-even and reject an unrounded result that
  exceeds field precision;
- treat Activity `cost` as an optional directly entered non-negative operational amount;
- make recorded purchase, labour, and activity cost facts immutable; correct mistakes by adding a
  replacement/compensating record in a later separately authorized correction flow; and
- do not aggregate these records into accounting, Inventory valuation, COGS, profit, or tax.

Confirm these equations and correction rules, or state that `total_cost` is independently entered
and define how disagreement with rate multiplication is handled.

### SP-05 — Mutation audit and retry identity

**Question:** Which audit and idempotency envelope applies to these staff form submissions?

The directive asks to preserve existing conventions where mutations require them, but it does not
say whether simple internal HTML form submissions are externally retryable commands or whether
records may be edited/deleted.

**Recommended decision:** route every create and lifecycle/quantity mutation through an atomic
service requiring actor, reason where state/quantity changes, correlation UUID, idempotency UUID,
and request fingerprint. Identical retries return the original result; reuse with changed input is
rejected. Operational records are append-only after creation; Batch planning notes and expected date
may be edited until `CLOSED`, with an immutable event appended for every change. No Production
business record may be deleted through the UI or admin.

Confirm this rule or define the smaller audit envelope and exactly which records/fields are mutable.

## Already resolved boundaries

The following do not require further decisions for this phase:

- Production is exclusively seedling-nursery operational record-keeping.
- Purchases do not receive Inventory and do not create suppliers, payables, or payments.
- Labour does not create payroll, HR, tax, attendance, or employment records.
- Activity types may share one controlled Activity model because they have the same operational
  semantics in this simple scope.
- No Production record changes `StockPosition`, posts an Inventory Movement, creates saleable
  availability, or affects Orders, Commitments, Reservations, Allocations, Payments, or Fulfillment.
- `READY` remains internal until a separate Production-to-Inventory contract is ratified.
- No customer-facing Production route, fixture, seed, or demo data is permitted.

## Ratification disposition

SP-01 through SP-05 were approved exactly as recommended. An additive Production app migration may
be generated, inspected on a clean isolated database, applied to the protected local SQLite
database, and verified with the required focused and regression suites.
