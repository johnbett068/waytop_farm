# Phase 1G — READY lifecycle completion and production-readiness audit

Status: **Historical Phase 1G audit; PROCESSING gate resolved by Phase 1G-Final**

Completed: 20 August 2026

## 1. Exact phase status and scope

Phase 1G implements READY Order cancellation, cancellation-scoped Reservation/Allocation release,
Order Line outstanding synchronization during physical supply, and the ratified minimal
FulfillmentCompletion boundary. It hardens Order and Payment append-only/controlled-write models
against bulk ORM mutation and reconciles current canonical documentation with Phase 1F decision
F02.

At completion of this phase, `CONFIRMED -> PROCESSING` was intentionally left behind the separate
`phase-1g-processing-decision-gate.md`. Phase 1G-Final subsequently ratified and implemented that
gate; the remaining sections preserve the Phase 1G verification record as it stood on 20 August.

PRE_ORDER/Production, Delivery, tracking, Branch, refunds, returns and every other explicit
non-goal remain absent.

## 2. Files

Added:

- `apps/fulfillment/__init__.py`
- `apps/fulfillment/apps.py`
- `apps/fulfillment/models.py`
- `apps/fulfillment/services.py`
- `apps/fulfillment/admin.py`
- `apps/fulfillment/migrations/__init__.py`
- `apps/fulfillment/migrations/0001_initial.py`
- `apps/inventory/releases.py`
- `apps/orders/lifecycle.py`
- `apps/orders/test_lifecycle.py`
- `apps/orders/test_postgresql_concurrency.py`
- `docs/reviews/phase-1g-processing-decision-gate.md`
- `docs/reviews/phase-1g-audit.md`

Changed:

- `config/settings.py`
- `apps/orders/models.py`
- `apps/orders/services.py`
- `apps/inventory/models.py`
- `apps/inventory/migrations/0004_alter_sourceallocationoperation_kind.py`
- `apps/commitments/supply.py`
- `apps/commitments/test_supply.py`
- `apps/payments/models.py`
- `apps/payments/tests.py`
- `apps/payments/test_confirmation.py`
- `docs/architecture/order-customer-payment-contract.md`
- `docs/architecture/availability-commitment-contract.md`

Files removed: none.

## 3. Models and migrations

`FulfillmentCompletion` is the separately owned, immutable, one-to-one completion fact approved by
the ratified Order/Customer/Payment contract. It records Order, completing actor, server timestamp,
optional note/reference, correlation ID, unique idempotency key and request fingerprint. It has no
Delivery, route, driver, Branch or Inventory fields. Its only custom permission is
`fulfillment.complete`; Django add/change/delete defaults are disabled.

`SourceAllocationOperation.Kind.RELEASE` provides append-only actor/reason/source/correlation and
idempotency history for cancellation release. Existing Allocation lines retain their source and
initial/consumed/released equations and point to the release operation; they are not replaced or
deleted.

Order, Order Line and Order status models now distinguish confirmation, cancellation, supply and
fulfillment controlled writes and validate their exact allowed transitions/counter direction.
Order and Payment aggregates, snapshots and history use protected QuerySets, closing direct
`update`, `delete`, `bulk_create` and `bulk_update` bypasses that remained after Phase 1F.

Migrations:

- `fulfillment.0001_initial` creates `FulfillmentCompletion` and `fulfillment.complete`.
- `inventory.0004_alter_sourceallocationoperation_kind` adds the RELEASE choice.

No data migration, seed, fixture or historical migration rewrite was added.

## 4. Services and business rules

### READY cancellation

`cancel_ready_order()` requires an authenticated active staff actor with `orders.cancel`, a
non-empty reason, correlation ID and idempotency key. It accepts only CONFIRMED or PROCESSING
READY-only Orders whose Payment remains CONFIRMED. PENDING cancellation is rejected.

For every remaining Commitment it atomically:

1. releases all remaining Allocation quantities through one append-only RELEASE operation;
2. moves Reservation remaining quantity to released and appends a RELEASED event;
3. moves Commitment outstanding commercial/base quantity to cancelled without changing committed
   or supplied history and appends a cancellation event;
4. reduces the owning Order Line outstanding quantity to zero without changing ordered or
   confirmed quantity; and
5. moves the Order to CANCELLED and appends its required status event.

Already supplied stock is not returned. A fully supplied Commitment remains SATISFIED/CONSUMED;
there is no fabricated zero-quantity cancellation event. Payment remains a truthful CONFIRMED
receipt and no refund state or record is created.

Reservation/allocation release is deliberately private to the cancellation composition boundary.
The contracts ratify cancellation release but do not authorize a general standalone release,
expiry, transfer or abandonment command.

### Physical supply consistency

`supply_ready_commitment()` now locks and validates the owning Order Line and reduces its
outstanding whole-sale-unit counter by the same supplied quantity used for Commitment,
Reservation, Allocation and ISSUE updates. The existing atomic Inventory and audit behavior is
unchanged. This closes the prior cross-domain mismatch where Commitment outstanding decreased but
the Order-owned projection did not.

### Minimal fulfillment completion

`complete_order_fulfillment()` requires authenticated active staff with `fulfillment.complete`.
It accepts only a PROCESSING READY Order with CONFIRMED Payment, exactly one Commitment and
Reservation per line, every Order Line/Commitment outstanding quantity at zero, SATISFIED
Commitments, CONSUMED Reservations and no remaining Allocation quantity.

It creates the immutable completion fact, transitions PROCESSING to FULFILLED and appends the Order
status event in one transaction. It does not post Inventory, create Delivery/logistics data, expose
sources, or change Payment.

### Explicitly deferred rules

- `CONFIRMED -> PROCESSING`: deferred here; subsequently implemented by Phase 1G-Final.
- PRE_ORDER and mixed lifecycle behavior: blocked by the missing Production-capacity contract.
- standalone Reservation release, automatic expiry and transfer: not ratified.
- returns/restocking and refunds: separate future domains.
- Delivery, dispatch, driver, route, tracking and Branch behavior: excluded.

## 5. Permissions

- confirmation: `payments.verify` plus `commitments.allocate` (existing Phase 1F boundary);
- source reallocation: `commitments.allocate`;
- physical supply/Inventory ISSUE: `inventory.release`;
- READY Order cancellation and its internal release: `orders.cancel`;
- minimal completion: `fulfillment.complete`;
- read-only Order, Commitment and Inventory admin boundaries retain their existing permissions.

All mutation services require authenticated active staff and use normal Django `has_perm()` and
superuser semantics. There are no role-name checks and no permission is silently substituted for
the unresolved PROCESSING authority.

## 6. Transactions, locks and races

Cancellation owns one transaction and locks Order, Inventory Items in stable UUID order,
Commitments in Order Line order, Order Lines, Stock Positions in stable primary-key order, then
Reservations and Allocations. The internal release service preserves Inventory Item -> Position ->
Reservation -> Allocation ordering. This aligns with supply's Inventory Item -> Commitment ->
Order Line -> Position -> Reservation/Allocation order after the Order-level eligibility lock.

Fulfillment completion locks Order, Commitments in line order, Order Lines and Reservations before
proving zero outstanding. Cancellation and completion serialize on Order. Supply and cancellation
serialize on Inventory Item/Commitment and revalidate all remaining equations after locks.
Confirmation and cancellation cannot both act on the same initial state; their Order lock ensures
the later command sees the committed lifecycle state.

No `select_related()` row-lock expansion is used on Payment in the cancellation/completion Order
lock, avoiding an implicit lock order contrary to Phase 1F's Payment -> Order sequence.

PostgreSQL-only `TransactionTestCase` infrastructure covers two confirmations competing for one
physical supply pool and supply racing cancellation. Both tests are skipped under SQLite rather
than presented as concurrency proof. PostgreSQL is not configured, so confirmation-versus-release,
confirmation-versus-cancellation, concurrent completion and repeated-request races remain
identified but not runtime-verified.

## 7. Idempotency and rollback

Cancellation uses the caller key for the Order event and deterministic UUIDv5 child keys for each
Commitment cancellation, Allocation release and Reservation release event. An identical completed
retry validates the complete released/cancelled result and returns the same Order. Changed reuse or
known cross-domain parent-key collision is rejected.

FulfillmentCompletion stores a SHA-256 fingerprint over Order, actor, correlation ID, note and
reference. Its Order-event key is deterministically derived. Identical retry returns the original
completion; changed reuse is rejected.

Injected failures after release and after completion-record creation prove transaction rollback.
No partial release, cancellation counter, completion record, state transition or duplicate event
survives. A failed cancellation can safely retry with the same key.

## 8. Audit, privacy and security

Cancellation preserves Commitment, Reservation, Allocation and Order history with actor, server
timestamps, positive exact quantities, reason, source/reference, correlation and idempotency.
Supply retains its ISSUE/SupplyEvent/consumption history and now synchronizes the Order Line
projection. Fulfillment history is immutable and actor/correlation-bearing.

No public route or customer UI was added. Customer projections remain unchanged and receive no
Inventory Item, Location, Lot, FIFO, Reservation, Allocation, staff, internal correlation or audit
detail. FulfillmentCompletion admin is read-only and permission protected. Raw Payment evidence
privacy remains unchanged.

## 9. Production-readiness findings

- Quantity arithmetic remains integer commercial units plus exact Decimal(32,3) base units.
- Commitment, Reservation and Allocation additive equations remain enforced.
- Cancellation never edits physical on-hand; only supply posts an ISSUE.
- Query ordering is explicit at each FIFO/source/lock boundary.
- Posted and audit records reject ordinary instance and bulk mutation.
- Canonical documentation now records the Phase 1F CONFIRMED endpoint and Phase 1G lifecycle
  implementation instead of retaining the superseded automatic PROCESSING claim.
- Legacy broad state-machine/operations documents were already marked superseded for V1 and were
  preserved.

At this audit date the complete forward lifecycle was not production-ready because PROCESSING entry
was unresolved and PostgreSQL concurrency had not executed. Phase 1G-Final resolved the business
decision; PostgreSQL execution remains an environmental verification gap.

## 10. Tests and verification

- Phase 1G focused lifecycle tests: 12 passed.
- PostgreSQL concurrency tests discovered: 2, skipped because the configured database is SQLite.
- Relevant Order/Payment/Commitment/Inventory regression suite: 153 passed.
- Full Django suite: 237 discovered, 235 passed, 2 PostgreSQL-only skipped.
- `python manage.py check`: passed with no issues.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: passed; only existing line-ending conversion warnings were emitted.
- Clean isolated migration application: passed through the complete graph during Django test setup.
- Development `db.sqlite3`: zero bytes.
- Runtime/demo data: none added.

Focused coverage includes CONFIRMED and PROCESSING cancellation, partial-supply preservation,
availability restoration, no on-hand mutation on release, exact Commitment/Reservation/Allocation
equations, release history, Payment preservation, Order Line synchronization, authorization,
inactive staff, PENDING rejection, idempotency, changed reuse, late rollback/retry, completion
preconditions, completion immutability/idempotency/rollback, privacy-safe schema and protected bulk
mutation boundaries, and normal Django superuser semantics.

## 11. Deviations, blockers and exact next phase

There is no architectural deviation from ratified READY cancellation, release, supply or minimal
completion semantics. The internal cancellation-only release service avoids inventing a broader
release authority. The new Fulfillment app is deliberately limited to the one approved completion
fact.

The business blocker recorded here was resolved by the Phase 1G-Final ratification and
implementation. PostgreSQL execution remains a separate environmental verification blocker for
production concurrency claims. Production capacity/PRE_ORDER and every strict non-goal remain
later, separately ratified work.
