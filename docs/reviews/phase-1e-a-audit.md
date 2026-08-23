# Phase 1E-A Inventory persistence implementation review

Status: **Complete within Phase 1E-A scope**
Reviewed: 20 August 2026

## Files

Added:

- `apps/inventory/__init__.py`
- `apps/inventory/apps.py`
- `apps/inventory/models.py`
- `apps/inventory/services.py`
- `apps/inventory/admin.py`
- `apps/inventory/tests.py`
- `apps/inventory/migrations/__init__.py`
- `apps/inventory/migrations/0001_initial.py`
- `docs/reviews/phase-1e-a-audit.md`

Changed:

- `config/settings.py`
- `apps/products/models.py`
- `docs/architecture/availability-commitment-contract.md`
- `docs/reviews/phase-1e-decision-gate.md`

No files were removed.

## Models and migration

`inventory.0001_initial` creates `InventoryItem`, `InventoryLocation`, `StockLot`, `StockPosition`, `InventoryMovement` and `InventoryMovementLine`. It depends only on Product persistence and the swappable staff User for movement actors.

The migration creates one-to-one Product/Inventory Item identity, protected historical relationships, unique Location and lot identities, positive movement quantities, non-negative Position balances, source-reference/idempotency uniqueness, movement endpoint checks, reversal-reference consistency and unique `(item, location, lot)` Positions.

The development `db.sqlite3` was not migrated and remains zero bytes. Clean test databases applied the complete migration graph successfully.

## Service boundary

`post_inventory_movement` is the only Phase 1E-A balance-write boundary. It:

- requires active staff and the movement-specific native permission;
- validates exact positive `Decimal(32,3)` base quantities;
- locks Inventory Items in stable order and locks Lots, Locations and Positions;
- validates item/lot/location consistency and active configuration;
- validates source stock before applying destination credits, so circular transfer lines cannot
  use stock received by the same Movement;
- rejects a transaction that would make any Position negative;
- appends immutable Movement/Line history and updates Positions atomically;
- increments Position versions;
- rechecks idempotency after the shared Inventory Item lock so concurrent identical retries return
  the first committed result;
- includes the audit actor and caller-supplied correlation identity in the request fingerprint;
- returns the existing result for an identical idempotent retry; and
- rejects idempotency-key reuse with different input.

Normal model, queryset, bulk and admin writes cannot create or mutate Movements, Lines or
Positions. Read-only admin projections require `inventory.view`.

## Invariants implemented

- One saleable Inventory Item per Product and matching base-unit snapshot.
- Product and Inventory Item base-unit changes are blocked after movement history exists.
- Internal flat Locations have stable codes and no Customer, Order or Branch relationship.
- Lots belong to one Item and use the ratified conditions.
- Direct lot-condition mutation is blocked until the audited condition command exists.
- Movement quantities are positive, finite, exact to three decimals and within `Decimal(32,3)`.
- Physical balances cannot become negative at either service or database level.
- Every service balance change and immutable movement history commit together.
- No opening/demo stock or fabricated Position is created.

## Permissions

Native Inventory capabilities are attached to the Inventory Item content type:

- `inventory.view`
- `inventory.receive`
- `inventory.release`
- `inventory.adjust`
- `inventory.approve_adjustment`
- `inventory.transfer`

Receipt, issue and transfer posting are implemented. Adjustment and reversal types exist in the schema, but posting remains deliberately unavailable because the ratified contract defers approval thresholds/workflow. No role names are embedded in services.

## Tests and checks

- Inventory-focused suite: 25 passed.
- Product plus Inventory regression suite: 54 passed.
- Accounts/Customer/Product/Inventory/Order/Payment suite: 120 passed.
- Full Django suite: 136 passed.
- Django system check: no issues.
- Migration drift check: no changes detected.
- Fresh isolated test databases applied `inventory.0001_initial` and the complete migration graph.

## Limitations and PostgreSQL status

The current database configuration is SQLite. SQLite tests prove ordinary transactions,
database constraints and rollback behavior, but do not prove PostgreSQL row-lock behavior.
PostgreSQL competing receipt/issue tests remain required before a production concurrency claim;
confirmation concurrency belongs to the later confirmation phase after its persistence exists.

Append-only history and direct-balance protection are enforced at the application model, queryset,
service, permission and admin boundaries. Database checks independently enforce non-negative
Positions and positive Movement Line quantities. As with the rest of the Django application, a
principal holding unrestricted database credentials is outside these application boundaries and
must be controlled through deployment database roles.

No Availability calculation, Commitment, Reservation, Source Allocation, FIFO, Order/Payment confirmation, Production, Fulfillment or customer-facing Inventory behavior was introduced.

## Deviations and next phase

There are no architectural deviations from AC01-AC28. Audited lot-condition changes and adjustment/reversal approval workflows remain unavailable rather than being invented.

The exact next phase is Phase 1E-B: Commitment and deterministic FIFO persistence. It must not implement Reservation, Source Allocation, Availability calculation or Order/Payment confirmation.
