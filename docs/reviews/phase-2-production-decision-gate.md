# Phase 2A Production Operations decision gate

Status: **SUPERSEDED FOR SIMPLE PHASE 2A — CROSS-DOMAIN GATES REMAIN DEFERRED**

Audit date: 29 August 2026

The owner ratified `phase-2a-simple-production-decision-gate.md` on 31 August 2026. That later
record authorizes the bounded Simple Production module only. This older gate continues to defer
Production-to-Inventory handoff, PRE_ORDER capacity, Production costing/valuation, quality release,
and other larger cross-domain behavior; it no longer blocks the ratified Simple Phase 2A scope.

## Outcome and proposed scope

Phase 2A cannot proceed to a Production model, service, projection, permission, or operational UI.
Current authority deliberately defers Production, Production capacity, and PRE_ORDER behavior, and
the repository contains no authoritative persisted Production state from which a real operations
workspace could be built.

The proposed scope before owner ratification is documentation only:

1. preserve the existing READY Order-to-Fulfillment lifecycle unchanged;
2. preserve PRE_ORDER as unavailable for confirmation, reservation, allocation, and physical supply;
3. preserve the staff-only truthful empty Production routes;
4. ratify a minimum Production contract through the questions in this gate; and
5. implement only the ratified contract in a later pass.

No Production runtime code, permission, migration, table, fixture, seed, or fabricated record is
authorized by this gate.

## Authority resolution

### Current authority

- `docs/document-authority.md` is the current classification index. It expressly classifies
  Production as deferred and states that `docs/contracts/production.md` and
  `docs/flows/production-lifecycle.md` do not authorize Production or PRE_ORDER implementation.
- `docs/architecture/v1-business-contract.md` is the cross-domain V1 authority. It establishes
  high-level ownership and boundaries: Production owns Batches, forecasts, attributable expenses,
  quality decisions, and Production Releases; multiple partial releases are contemplated; an
  Inventory-owned movement is required to create stock; and Production domains must not silently
  mutate other domains.
- `docs/architecture/order-customer-payment-contract.md` and
  `docs/architecture/availability-commitment-contract.md` authorize the completed READY lifecycle.
  They do not provide an implementation-ready Production lifecycle or capacity provider.
- `docs/reviews/phase-1e-e-decision-gate.md` and
  `docs/reviews/phase-1g-processing-decision-gate.md` are ratified only for READY allocation,
  supply, cancellation, processing, and fulfillment behavior.
- `docs/deployment-configuration.md` authorizes the non-empty local SQLite database as development
  data and requires PostgreSQL for production-oriented and concurrency verification. It authorizes
  no business behavior.

### Planning and historical inputs

- `docs/contracts/production.md`, `docs/flows/production-lifecycle.md`,
  `docs/flows/production-workspace.md`, and the Production frontend documents describe possible
  future aggregates, screens, and commands. Their own markers and the authority index make them
  non-authoritative planning inputs.
- `docs/reviews/phase-3c-production-workspace-audit.md` records a frontend-only prototype. It says
  no backend, model, migration, API, authentication, calculation, or Inventory behavior was added.
- `docs/architecture/permissions.md` contains a future capability catalogue. The authority index
  says only installed permissions required by ratified services are current runtime authority.
- Historical audits remain historical and are not reinterpreted by this gate.

The high-level V1 ownership rules and the newer explicit deferral are compatible: the former set
boundaries for a future contract; they do not define enough state, quantity, command, permission,
or concurrency semantics to implement that contract.

## Current Production implementation audit

1. **Production URL:** `/dashboard/production/`. Related configured URLs are
   `/dashboard/production/source-lots/`, `/dashboard/production/batches/`,
   `/dashboard/production/batches/<batch_number>/`, `/dashboard/production/tasks/`, and
   `/dashboard/production/exceptions/`.
2. **Production view:** `apps.dashboard.views.production`; it delegates to the shared `_empty()`
   view and returns the message `No production batches yet.` Related Production views use the same
   empty boundary.
3. **Production template:** runtime uses `templates/dashboard/empty.html`, not the prototype
   Production templates.
4. **URL configuration:** `config/urls.py` mounts `apps.dashboard.urls` at `/dashboard/`; the six
   Production patterns are in `apps/dashboard/urls.py`.
5. **Navigation entry:** the shared staff navigation links to `dashboard:production` as
   `Production`. It contains no count and grants no authority.
6. **Existing Production models:** none. There is no Production Django app in `INSTALLED_APPS` and
   no `ProductionBatch`, `ProductionTask`, `ProductionRelease`, production event, capacity, or work
   order model.
7. **Existing Production services:** none. No Production command, mutation, or query service exists.
8. **Existing permissions:** none are installed under a `production` app label. The Production
   placeholder currently enforces login plus active staff status through `_empty()`. It does not
   check a Production capability. Active staff superusers pass through normal Django staff and
   authentication semantics; inactive staff are rejected.
9. **Existing tests:** `apps/dashboard/tests.py` covers authentication, staff status, the truthful
   empty Production routes, absence of fabricated values, navigation, and disconnection of mock
   templates. Other domain tests prove that PRE_ORDER availability is unavailable and that READY
   reservation/supply paths reject PRE_ORDER. There are no Production lifecycle, quantity,
   mutation, idempotency, history, or concurrency tests because no such behavior exists.
10. **Existing domain references:** Orders and Commitments retain a `PRE_ORDER` supply-mode
    vocabulary, but confirmation has no Production-capacity provider. Inventory availability raises
    `PRE_ORDER_CAPACITY_UNAVAILABLE`; physical Reservations and READY supply reject PRE_ORDER.
    Current Order models deliberately contain no Production relationship. Inventory has a generic,
    authoritative movement service and source-reference envelope, but no ratified Production
    consumption or receipt command. Fulfillment supports completely supplied READY Orders only.
11. **Existing database tables/migrations:** there are no Production tables and no Production
    migrations. All 37 currently configured migrations are applied to the local development
    database; none is a Production migration.
12. **Existing UI components:** disconnected prototype templates exist for a dashboard, source lots,
    batches, batch detail, tasks, exceptions, and their components, plus
    `static/css/staff-production.css` and `static/js/staff-production.js`. They contain static mock
    data and disabled controls. Runtime Production routes intentionally do not render them.

### Capability summary

| Capability | Current state |
|---|---|
| Domain model | Absent |
| Authoritative operational state | Absent |
| Read-only dashboard | Truthful empty placeholder only |
| Mutation services | Absent |
| Capacity concepts | Planning prose only; runtime provider absent |
| Batch/work-order concepts | Disconnected mock/prototype only |
| Production events | Absent |
| Staff actions | None; prototype controls are disabled |

## Business-gap classification

### A. Already-authorized behavior

The following are boundary rules, not an implementation-ready Production lifecycle:

- Production and Inventory facts remain separately owned.
- Production must not bypass Payment, Commitment, Reservation, Allocation, Inventory movement,
  permission, audit, or Order/Fulfillment rules.
- A Production Release does not itself create stock. A separately authorized Inventory-owned
  receipt is required, with Production provenance retained.
- A forecast is not physical stock and must not rewrite historical release facts.
- Multiple partial releases are contemplated, and cumulative released quantity may not exceed the
  legitimately releasable quantity.
- Production-derived and external/manual Inventory must remain distinguishable by provenance.
- PRE_ORDER capacity must not be fabricated or exposed through READY availability.

### B. Clearly required operational behavior

A real Production workspace necessarily needs persisted aggregate identity, authoritative lifecycle
state, exact quantity meanings and units, permission-scoped reads, explicit commands, transaction
and lock roots, idempotency rules, append-only history, and an independently governed Inventory
handoff. These are structurally necessary to operate Production but are not currently defined well
enough to implement.

### C. New business decisions

The Production aggregate, lifecycle states and transitions, quantity ledger, eligibility and release
rules, loss/correction behavior, source-material consumption, finished-goods receipt, permissions,
idempotency identity, cancellation/closure semantics, scheduling, deterministic attention rules,
PRE_ORDER capacity, and partial-release costing all require owner ratification. Category C is not
implemented.

## Relationship to the existing lifecycle

The only implemented path remains:

`READY Order -> verified Payment -> Commitment -> Reservation -> Allocation -> Supply/Inventory ISSUE -> PROCESSING -> Fulfillment`

A future Production path may create Production-owned WIP and release evidence, followed by an
independent Inventory-owned receipt. It must not make an Order confirmed, reserve physical stock,
allocate sources, issue Inventory, start processing, or complete fulfillment by implication.

No current authority defines a lawful Production-to-PRE_ORDER path. In particular, creating a
Production Batch must not create promiseable capacity merely because PRE_ORDER demand exists.
`get_ready_availability()` remains unchanged and Production WIP remains excluded from READY stock.

## Decisions required before implementation

### P2A-01 — Production aggregate and lifecycle

1. **Question:** What is the minimum authoritative Production aggregate, and what exact states and
   transitions does it own?
2. **Current repository behavior:** no Production aggregate or state exists. Prototype prose mentions
   batches, tasks, activities, stages, holds, reviews, and releases, but is deferred.
3. **Authoritative evidence:** V1 assigns Batches, quality decisions, and Releases to Production and
   requires cross-domain separation. It does not enumerate implementation-ready states or commands.
4. **Possible interpretations:** start with a Batch aggregate and append-only stage events; start
   with independent production runs; or ratify a larger workspace containing Tasks and other child
   records. These alternatives produce materially different schemas and commands.
5. **Recommended option:** ratify the smallest Batch-and-event aggregate that can record actual WIP
   and an independently approved release; defer Tasks, scheduling, expenses, treatments, attachments,
   analytics, and PRE_ORDER capacity unless separately necessary and ratified.
6. **Exact business rule required:** identify the aggregate root and identifier; enumerate initial,
   active, terminal, hold, and release states; enumerate every legal transition, prerequisite,
   actor/reason requirement, retry result, correction rule, and lock root; state whether partial
   release closes or leaves a Batch active.
7. **Why implementation must stop:** without these rules, any model status or command would invent
   the business lifecycle.

### P2A-02 — Quantities, units, loss, and release eligibility

1. **Question:** What do planned, started, observed, lost, accepted, rejected, held, produced,
   released, and remaining quantities mean, and which are authoritative?
2. **Current repository behavior:** none of these Production quantities exists. Prototype quantities
   are static fixtures. Inventory quantities use positive decimals in an item base unit; Order
   quantities are whole sale-unit counts. Those semantics cannot be copied into Production without
   a rule.
3. **Authoritative evidence:** cumulative release may not exceed legitimately releasable quantity;
   corrections must not rewrite historical releases. The definition of `legitimately releasable`
   is absent.
4. **Possible interpretations:** maintain an append-only quantity ledger; store current counters with
   event evidence; or derive selected balances from immutable observations. Unit conversion and
   rounding differ across these options.
5. **Recommended option:** ratify an append-oriented quantity contract with one canonical unit per
   Batch product and explicit server-validated equations; treat corrections as compensating events.
6. **Exact business rule required:** define each quantity, unit compatibility and precision; whether
   fractional values are allowed; non-negative and conservation equations; loss/cull and correction
   semantics; release eligibility; partial-release bounds; and concurrency behavior.
7. **Why implementation must stop:** neither database constraints nor exact arithmetic tests can be
   correct without the equations and units.

### P2A-03 — Inventory consumption and finished-goods receipt

1. **Question:** Which Production facts authorize Inventory input ISSUE and finished-goods RECEIPT,
   and who may post each movement?
2. **Current repository behavior:** Inventory is changed only through
   `post_inventory_movement()`. It supports generic RECEIPT and ISSUE types with source identity,
   but there is no Production source contract or service. Production never changes stock today.
3. **Authoritative evidence:** Production must not mutate Inventory directly; release and Inventory
   receipt are separate facts; Inventory derived from Production retains Batch/Release provenance.
4. **Possible interpretations:** an Inventory actor explicitly posts against an approved Production
   request/release; an application service coordinates both domains atomically; or an asynchronous
   consumer posts later. Failure, retry, and separation-of-duty behavior differ.
5. **Recommended option:** keep Production recording and Inventory posting as distinct authorized
   commands, with an immutable Production reference accepted exactly once by the Inventory service.
6. **Exact business rule required:** define input eligibility; lot/location selection authority;
   release-to-receipt source type/reference; quantity/unit mapping; permission and actor; duplicate
   prevention; transaction or eventual-consistency boundary; rejection/reconciliation behavior; and
   whether any input issue is mandatory for a Batch.
7. **Why implementation must stop:** reusing the generic movement service without this contract would
   invent source semantics and could corrupt provenance or quantities.

### P2A-04 — Quality, release approval, and separation of duty

1. **Question:** What evidence makes quantity releasable, and who may review and approve it?
2. **Current repository behavior:** no quality record, hold, review, approval, or release exists.
3. **Authoritative evidence:** Production owns quality decisions and Releases; broad planning prose
   suggests independent approval, but its capability names and rules are not current authority.
4. **Possible interpretations:** one authorized release command; separate review and approval; or a
   configurable separation-of-duty workflow.
5. **Recommended option:** ratify review evidence and release approval as separate facts, including
   an explicit decision on whether the same actor may perform both.
6. **Exact business rule required:** required evidence, hold behavior, accepted/rejected quantity,
   eligible transitions, approver capability, same-actor rule, reason and audit fields, partial
   release behavior, and retry/concurrency result.
7. **Why implementation must stop:** release state and permission checks cannot be inferred from a
   prototype role matrix.

### P2A-05 — Permission model and read projection

1. **Question:** Which installed capabilities govern Production visibility and each authorized
   command?
2. **Current repository behavior:** no Production permission exists. The placeholder route accepts
   any authenticated active staff user. The future catalogue names several provisional Production
   capabilities but is expressly non-authoritative for uninstalled behavior.
3. **Authoritative evidence:** authorization is capability-based, requires authenticated active
   staff, preserves normal Django superuser semantics, and never depends on role names.
4. **Possible interpretations:** one view plus command-specific permissions; separate permissions
   for child records; or a minimal first-release view/release set.
5. **Recommended option:** ratify `production.view` plus only the command capabilities required by
   the chosen minimum aggregate; do not install unused future catalogue permissions.
6. **Exact business rule required:** canonical codenames; which projection fields/counts each grants;
   command-to-permission mapping; superuser and inactive-user behavior; privacy redactions; and
   whether the existing staff-only placeholder becomes capability-gated before data exists.
7. **Why implementation must stop:** adding a permission or exposing a persisted projection would
   itself be a new authorization decision.

### P2A-06 — Idempotency, history, correction, and closure

1. **Question:** What command identity, event envelope, retry behavior, and correction/closure rules
   govern Production?
2. **Current repository behavior:** there are no Production commands or events. Phase 1 services use
   explicit idempotency keys, correlations, actors, reasons, transaction locks, and append-only
   events, but their aggregate-specific rules do not automatically define Production.
3. **Authoritative evidence:** cross-domain facts must be auditable and historical releases must not
   be rewritten.
4. **Possible interpretations:** one global command-key namespace; aggregate-scoped keys; immutable
   event commands with compensations; or selected mutable planning facts plus immutable execution
   facts.
5. **Recommended option:** use immutable execution/history events with correlation and idempotency
   identity, and explicitly separate mutable planning metadata from immutable operational facts.
6. **Exact business rule required:** initial-event enforcement; event fields; global or scoped key
   identity; identical retry result; changed-input collision result; same/different-key concurrency;
   correction mechanism; Batch cancel/abandon/close rules; and whether released Batches can change.
7. **Why implementation must stop:** service and database enforcement depend on these decisions.

### P2A-07 — PRE_ORDER capacity and Order integration

1. **Question:** Is Phase 2A strictly Production WIP, or must it also create lockable PRE_ORDER
   capacity and supply?
2. **Current repository behavior:** PRE_ORDER appears as Order/Commitment vocabulary, but availability
   intentionally fails, physical reservation and READY supply reject it, and fulfillment is
   READY-only.
3. **Authoritative evidence:** open decision P1C-01 requires a capacity, eligibility, reservation,
   release, and shortfall contract. Current authority forbids fabricated capacity.
4. **Possible interpretations:** keep Production independent and defer PRE_ORDER; expose read-only
   non-promiseable forecasts; or ratify a full capacity/commitment provider. The latter changes
   confirmation, FIFO, cancellation, shortage, and fulfillment behavior.
5. **Recommended option:** keep the first Production Operations contract independent of Orders and
   PRE_ORDER. Ratify P1C-01 in a separate phase after real WIP and release semantics exist.
6. **Exact business rule required if PRE_ORDER is included:** capacity identity and unit; eligibility
   by product/date/stage; lock root; reservation and FIFO; partial release/supply; shortfall and
   cancellation; forecast edits; confirmation transaction integration; customer projection; and
   fulfillment handoff.
7. **Why implementation must stop:** any capacity value or Order link would create promiseable supply
   without a ratified conservation and concurrency contract.

### P2A-08 — Production costing

1. **Question:** Is costing in scope, and how are Batch-attributable expenses allocated across
   multiple partial releases?
2. **Current repository behavior:** no Production expense or costing persistence exists; prototype
   values are placeholders.
3. **Authoritative evidence:** V1 selects lot-specific costing direction but explicitly rejects the
   single-release formula as authority for multiple partial releases. P1C-02 remains open.
4. **Possible interpretations:** defer costing; allocate expenses at each release under a ratified
   policy; or close and value a Batch before releasing. Each changes financial truth.
5. **Recommended option:** exclude costing from the first operational Production contract and resolve
   P1C-02 separately before any cost fields or calculations are persisted or displayed.
6. **Exact business rule required if included:** attributable expense definition, effective-dated
   allocation policy, partial-release valuation, later-expense/correction handling, rounding,
   Inventory lot-cost handoff, and audit treatment.
7. **Why implementation must stop:** any unit-cost calculation would invent the unresolved formula.

## Ratification packet required

Implementation may resume only after an owner-approved decision record supplies:

1. the chosen aggregate and exact lifecycle transition table;
2. the quantity/unit definitions and conservation equations;
3. quality and release eligibility/approval rules;
4. Inventory ISSUE/RECEIPT handoff rules;
5. canonical installed permissions and field redactions;
6. idempotency, locking, event, correction, and closure rules;
7. an explicit `deferred` or `included with full contract` decision for PRE_ORDER; and
8. an explicit `deferred` or ratified allocation formula decision for costing.

Until then, the only truthful Production UI is the existing empty staff projection. The disconnected
mock templates must not be reconnected to runtime data or presented as operational truth.

## Database and migration safety

The audit used the configured local SQLite development database at
`F:\important_projects\waytop_farm\db.sqlite3`. At the audit baseline it was 815,104 bytes with
SHA-256 `CDD6257D3B3FE7D39F577180736AFE102AFCDEF87EF4D412ED3E25F33749F914`.
It contained no Production table or installed Production permission. No migration is required or
authorized by this gate, and `migrate` must not be run for Phase 2A until a later ratified schema is
reviewed under the migration-safety procedure.
