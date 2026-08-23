# Phase 1E-B Commitment and FIFO persistence implementation review

Status: **Complete within Phase 1E-B scope**
Reviewed: 20 August 2026

## Files

Added:

- `apps/commitments/__init__.py`
- `apps/commitments/apps.py`
- `apps/commitments/models.py`
- `apps/commitments/services.py`
- `apps/commitments/admin.py`
- `apps/commitments/tests.py`
- `apps/commitments/migrations/__init__.py`
- `apps/commitments/migrations/0001_initial.py`
- `docs/reviews/phase-1e-b-audit.md`

Changed:

- `config/settings.py`
- `apps/inventory/models.py`
- `apps/products/models.py`
- `docs/architecture/availability-commitment-contract.md`

No files were removed.

## Models and migration

`commitments.0001_initial` creates `Commitment` and `CommitmentEvent`. It depends on the
ratified Order, Inventory and staff User foundations.

`Commitment` has a unique UUID business identity and uses its database-generated
`BigAutoField` primary key as the immutable monotonic FIFO sequence. It protects its Order,
one-to-one Order Line and Inventory Item references. The Inventory Item freezes the compatible
supply pool while Product, Sale Unit and supply-mode history continue to come from the immutable
Order Line.

The migration adds the FIFO pool index `(inventory_item, confirmed_at, fifo_sequence)`, unique
Order Line and creation-idempotency identities, positive/non-negative quantity checks, exact
commercial/base conversion checks, both quantity equations and state/quantity consistency.

## Services and boundaries

`_create_commitment_for_confirmation` is deliberately internal. It:

- requires a caller-owned outer transaction;
- requires active staff with both `payments.verify` and `commitments.allocate`;
- consumes the immutable Order Line snapshots rather than current Catalog values;
- resolves and locks the compatible Inventory Item without changing Inventory;
- calculates the exact three-decimal total with no rounding;
- creates the Commitment and initial audit event atomically; and
- returns the same Commitment for an identical idempotent retry while rejecting changed reuse.

It is not exposed through a public function, view, URL, API or admin write action. It does not
confirm an Order or Payment and is intended only for the future atomic confirmation orchestrator.

`list_fifo_commitments` is an internal authorized projection requiring `commitments.view`. It
partitions by Inventory Item and supply mode, filters active Commitments and always orders by
`confirmed_at`, then `fifo_sequence`. Required date is never used as priority.

## Quantity invariants

- Commercial and base committed quantities are positive.
- Supplied, cancelled and outstanding quantities are non-negative.
- `committed = supplied + cancelled + outstanding` is database-enforced independently in both
  commercial and base units.
- Committed, supplied, cancelled and outstanding base quantities must each exactly equal their
  commercial quantity multiplied by the immutable base quantity per Sale Unit.
- A new Commitment is ACTIVE, wholly outstanding and has zero supplied/cancelled quantity.
- SATISFIED and CANCELLED state consistency is database-enforced.
- `Decimal(32,3)` values must be finite and exact; no rounding is performed.

No supply or cancellation mutation service is implemented in this phase.

## Immutability and history

Commitment UUID, FIFO sequence, Order/Order Line/Inventory Item relationships, committed
quantities, conversion snapshot, confirmation time, required date and creation identities cannot
change through model or queryset operations. Controlled future services may change only the
ratified mutable counters/state while database equations remain valid.

`CommitmentEvent` is append-only and records Commitment, previous/new state, positive commercial
and base quantities, protected actor, server timestamp, reason, source type/reference, correlation
ID and unique idempotency key. Phase 1E-B writes only the initial `null -> ACTIVE` event. Future
supply and cancellation history remains deferred to its authorized phase.

Product and Inventory Item base-unit meaning is now immutable after either Inventory Movement or
Commitment use. Current Product, Sale Unit and Price edits never rewrite Commitment or Order Line
snapshots.

## Permissions and admin

Native capabilities:

- `commitments.view`
- `commitments.allocate`

No FIFO override, confirmation, supply, cancellation, Production or Fulfillment permission was
introduced. Commitment and event admin pages require `commitments.view` and are fully read-only.
Services use native capabilities rather than role names.

## Tests and checks

- Commitment-focused suite: 23 passed.
- Product/Inventory/Order/Payment/Commitment regression suite: 107 passed.
- Full Django suite: 159 passed.
- Django system check: no issues.
- Migration drift check: no changes detected.
- `git diff --check`: passed; only existing line-ending conversion warnings were emitted.
- Clean isolated test databases applied `commitments.0001_initial` and the complete migration
  graph successfully.

Coverage includes persistence, protected relationships, PENDING boundaries, exact quantities,
database constraints, over-supply/over-cancellation rejection, FIFO ordering and pool partitioning,
required-date non-priority, immutability, Catalog history independence, permissions, read-only
admin, append-only audit, idempotent retry and absence of deferred-domain/demo fields.

## PostgreSQL, data and security status

The repository remains configured for SQLite. Functional transactions, rollback and constraints
were tested on SQLite, but PostgreSQL sequence/row-lock concurrency was not tested and is not
claimed. PostgreSQL competing-transaction verification remains mandatory before production use.

No seed migration, fixture, sample Commitment, sample Inventory, fabricated availability or
runtime mock dependency was added. The real development `db.sqlite3` was not migrated.

Commitment data is internal. No customer response, route or template exposes FIFO position,
Inventory Item, actor or audit source. Actor and historical domain references use `PROTECT`.
Deployment database roles must continue to restrict unrestricted SQL because application-level
immutability cannot protect a principal with arbitrary database write credentials.

## Deferred behavior, deviations and readiness

Intentionally deferred: Availability, Reservation, Source Allocation, supply/cancellation
mutation, Payment verification, Order confirmation, Production capacity/releases, Fulfillment,
Delivery/tracking, returns/refunds, discounts/promotions/taxes, Branch persistence/selection and a
generic UOM system.

There are no architectural deviations from AC01-AC28 and no new decision blocker was encountered.

Phase 1E-C READY Availability query persistence prerequisites are present: authoritative physical
Positions, stable Inventory Item mapping, Commitment identity, exact base-unit quantities and
deterministic FIFO ordering. Phase 1E-C may now implement only the aggregate READY Availability
query and customer-safe projection. PRE_ORDER remains explicitly unavailable, and Reservation and
Source Allocation remain deferred to Phase 1E-D.
