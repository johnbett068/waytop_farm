# Phase 1E-D Reservation and Source Allocation implementation review

Status: **Complete within Phase 1E-D scope**
Reviewed: 20 August 2026

## Files

Added:

- `apps/inventory/migrations/0002_reservation_reservationevent_and_more.py`
- `apps/inventory/reservations.py`
- `apps/inventory/test_reservations.py`
- `docs/reviews/phase-1e-d-audit.md`

Changed:

- `apps/inventory/models.py`
- `apps/inventory/admin.py`
- `apps/inventory/availability.py`
- `apps/inventory/test_availability.py`
- `apps/commitments/tests.py`
- `docs/architecture/availability-commitment-contract.md`

No file was removed. Existing migrations were not changed.

## Reservation persistence and lifecycle

`Reservation` is the Inventory-owned aggregate physical partition for exactly one READY
`Commitment`, enforced by a protected one-to-one relation. It stores the matching Inventory Item,
exact `Decimal(32,3)` initial, consumed, released and remaining quantities, state, creation
correlation/idempotency identities, and server timestamps. Database checks enforce positive initial
quantity, non-negative counters, the reservation quantity equation, and state/counter consistency.

The ratified `ACTIVE`, `CONSUMED` and `RELEASED` states are represented for later composition. This
phase creates only fully remaining `ACTIVE` Reservations. It implements no consumption, release,
expiry, timeout, transfer or cancellation operation. Reservation identity, Commitment, Inventory
Item and initial quantity cannot be rewritten, and ordinary create/update/delete/bulk paths are
blocked. PENDING Orders, PRE_ORDER Commitments, non-new Commitments and insufficient supply are
rejected.

## Source Allocation and history

`SourceAllocation` remains separate from `Reservation`. Each line references the Reservation and a
`StockPosition`, whose existing keys provide the exact Inventory Item + Location + Lot grain. Lines
store exact base quantities and a quantity equation. A complete split may span Locations and Lots;
partial, excess, duplicate, ineligible and over-position splits are rejected.

The automatic source order is expiry date with null expiry last, then Lot creation time, Location
code and stable Position ID. `SourceAllocationOperation` records INITIAL/REALLOCATION approval and
idempotency context. Reallocation keeps the same Reservation and Commitment, closes the remaining
quantity on old lines with a releasing operation reference, and appends replacement lines. Initial
source identity and quantity remain immutable, so prior source facts are retained.

`ReservationEvent` and allocation operations retain actor, server time, quantity where applicable,
reason, source/reference, correlation ID and unique idempotency identity. Audit/operation records
are append-only and non-destructive.

## FIFO, atomicity and locking

The internal services require an existing outer `transaction.atomic()` block so a future
confirmation orchestrator can compose them without an intermediate commit. They do not create or
transition Orders, verify Payments or post Inventory Movements.

Initial reservation reuses the existing READY Commitment pool ordered by `confirmed_at`, then
database-generated `fifo_sequence`. An unreserved earlier eligible Commitment blocks a later one;
there is no priority or override field. The service locks the Inventory Item before its stable-ID
ordered eligible Stock Positions, then existing Reservations and Allocations, and recalculates the
pool under those locks. Complete unallocated Position capacity and aggregate active Reservation
capacity are both checked before writes. Any failure rolls the operation back.

PostgreSQL is the authoritative concurrency database, but no PostgreSQL environment is configured.
The SQLite service tests validate ordinary atomic rollback and invariants only; they do not prove
competing-transaction safety.

## Availability, permissions and boundaries

READY availability now uses the shared eligibility query and subtracts active Reservation remaining
base quantity, never Commitments or Allocations. It rejects an invariant breach rather than clamping
negative availability, floors exact base quantity to whole current Sale Units, and retains the same
aggregate projection: sale-unit count, calculation time and reservation coverage only.

Operational services require an authenticated active staff actor with `commitments.allocate`; no
role label is consulted. Reservation, event, operation and allocation admin views require
`commitments.view` and are read-only with create, edit and delete disabled. No public endpoint,
customer field, Branch, customer-selected source or internal allocation projection was added.

PRE_ORDER capacity and physical reservation remain unavailable. No Production, supply,
fulfillment, Order cancellation, Reservation release, Payment verification or Order confirmation
workflow was implemented. Creating a Reservation does not change Stock Position on-hand quantity or
post an Inventory Movement.

## Tests and verification

- Reservation/Allocation-focused suite: 20 passed.
- Combined Reservation/Availability suite: 36 passed.
- Requested domain regression suite (Accounts, Customers, Products, Inventory, Commitments, Orders,
  Payments): 179 passed.
- Full Django suite: 195 passed.
- Django system check: no issues (0 silenced).
- Migration drift: no changes detected.
- `git diff --check`: passed; existing line-ending conversion warnings only.
- Development `db.sqlite3`: 0 bytes.
- Migration inspection: schema operations only; no `RunPython` or `RunSQL` data operation.

Coverage includes one exact Reservation per READY Commitment; PENDING/PRE_ORDER rejection;
insufficient-stock rollback; immutable/non-transferable quantity and identity; exact allocation
totals and grain; Location/Lot splitting; deterministic selection; ineligible, duplicate, partial
and excess split rejection; per-Position double-allocation prevention; FIFO ordering and bypass
rejection; idempotent retry and changed-input rejection; append-preserving reallocation; permission
and read-only admin controls; aggregate Reservation-aware availability; Commitment non-deduction;
negative-invariant rejection; no on-hand/Movement/Order/Payment mutation; customer-safe fields; and
absence of runtime demo records.

## Data, deviations and next phase

No seed, fixture, fake stock, Order, Reservation or Allocation was added for runtime use. Tests use
isolated test databases, and the development database remained untouched.

There are no architectural deviations from the ratified Phase 1E-D contract. PostgreSQL concurrency
verification remains the only environment-dependent verification gap and is explicitly unclaimed.
There is no implementation blocker within this phase.

The exact next phase is **Phase 1E-E: post-confirmation supply foundation**: Commitment Supply Events
and atomic Inventory issue plus Reservation/Allocation consumption, without Fulfillment UI,
completion, cancellation, Production capacity, Payment verification or Order confirmation.
