# POS location implementation report

Implemented 9 September 2026.

## Architecture and schema

The existing Order, Payment, Commitment, Reservation, SourceAllocation and Inventory
services remain authoritative. POS is a staff interface to these services, guarded
by `pos.process_sale`; payment verification and processing retain their separate
permissions. Anonymous collection uses `customer=None`; selecting an authorized,
active customer preserves the existing relationship and contact snapshot.

Order did not have a location field. The only schema change for this slice is
`Order.location`: ForeignKey to `inventory.InventoryLocation`, `PROTECT`,
`related_name="orders"`, nullable/blank for historical compatibility. New POS
creation requires it; subsequent location changes are rejected. No duplicate
location model or redundant OrderLine/Payment/Commitment foreign keys were added.
Their Order supplies the branch; physical allocations and movements already carry
StockPosition/location relationships.

Migration: `apps/orders/migrations/0005_order_location.py`, containing one AddField.
Dependencies: orders.0004_order_status_event_constraints and
inventory.0008_acquisition_supplier_batch_reference. Before: orders 0001-0004 and
inventory 0001-0008 applied; only orders 0005 pending. After: all applied. The
migration graph is consistent, `migrate --check` passes, and
`makemigrations --check --dry-run` reports no changes. No historical assignments,
data migration, destructive operation, migration rewrite/reset, RunPython or RunSQL.

## Checkout and stock scope

- Initial server-side session state selects the unique eligible location named
  Bomet, case-insensitively. IDs are never hard-coded. Missing or ambiguous Bomet
  leaves an explicit selection required; it does not select the first location.
- The visible dropdown and checkout form carry `location_id`. Both the view and
  authoritative creation service reject missing, null, malformed, unknown,
  inactive or non-saleable locations in development and production. Bomet is
  never a backend fallback. No staff-to-branch mapping was invented.
- Products must be active and published, with an active Sale Unit and one positive
  authoritative current price. Existing Catalog semantics were preserved.
- Shared availability accepts an optional location scope. POS always supplies it;
  existing unscoped callers retain aggregate behavior. Eligible stock still
  requires the matching Product base unit, active item/location, active SALEABLE
  lot, valid expiry and positive StockPosition quantity. Active Reservation shares
  are subtracted once via remaining SourceAllocations at the selected location.
  Exact Decimal base balances are converted to whole Sale Units.
- Add/update and checkout validate the full cart, including combined base quantity
  across multiple Sale Units of the same Product. Zero-stock products are shown
  unavailable with disabled controls; manually submitted overselling is rejected.
- Switching location retains the cart, recalculates availability and revalidates
  its lines. Invalid carts display an error and disable checkout. The service
  rechecks stock even if the page was valid earlier.
- Source allocation and reallocation use only StockPositions at Order.location.
  Eligible lots within the branch can supply multiple sources. FIFO retains
  confirmed_at/fifo_sequence priority for commitments competing for that scope,
  including unscoped commitments; it never sources another branch to fill a gap.
- Existing supply validates allocations against the same location scope before
  creating ISSUE movements. Processing itself creates no ISSUE. Cancellation and
  fulfillment retain their existing service boundaries.

## Payment, idempotency and concurrency

Cart and pending Order creation neither reserve nor consume stock. Existing M-Pesa
evidence/verification confirms payment and the Order, creates the existing READY
Reservations/Allocations, and ends at CONFIRMED. PROCESSING is an explicit staff
action. No cash, PRE_ORDER, discount, tax or new payment system was added.

Current catalog prices and immutable Order snapshots use Decimal arithmetic and
the existing rounding rules. Exact creation retries reuse the Order and Payment;
reusing the same key with another location is rejected. Identical browser evidence
retries reuse the existing evidence under the Payment lock. Confirmation uses the
existing idempotency, transactions, per-item locking and allocation protections.
Pending orders may compete for stock; confirmation rechecks availability and cannot
confirm both against the same remaining stock through a separate POS shortcut.

## Verification

Full suite: `python manage.py test --noinput`: **397 tests, 382 passed, 15 skipped**.
Skipped tests require PostgreSQL; SQLite does not establish PostgreSQL concurrency
evidence. After the final retry-validation/test adjustment:
`python manage.py test apps.dashboard.test_pos apps.orders.tests --noinput`:
**35 passed**. Django checks and migration drift checks passed.

Sixteen POS integration tests cover Bomet state/form defaults, search, optional
actual customer, anonymous sale, permissions, required location in both DEBUG
modes, invalid/ineligible locations, absent Bomet, visibility, quantities and
Decimal totals, no cart inventory mutation, empty-branch manual requests,
location switching, checkout/confirmation stock rechecks, multiple branch-local
lots, mixed Sale Units, PRE_ORDER rejection, cross-branch reallocation rejection,
consumption with unavailable branch, immutable location, and creation/payment
confirmation retries. Existing placeholder/architecture assertions were updated
for the live POS and approved Order.location field. Existing domain, availability,
Supplier and Location tests passed in the full suite. The existing database
constraint prevents inactive published Products; that protection is also tested.

Headless Edge/Playwright browser verification used a separate disposable SQLite
database with isolated fixtures. Bomet defaulted to 5 available units; two units at
KES 12.55 produced KES 25.10 and an Order displaying Bomet/PENDING with anonymous
customer. Switching to another branch displayed 20; switching to an empty branch
showed out-of-stock and disabled both add and checkout. Desktop and mobile layouts
were visually inspected; mobile had no horizontal overflow. No browser-created
transactions were written to the real database.

The real `db.sqlite3` was retained and received only the additive migration.
Comparing every original business/session row and original column against the
pre-POS snapshot found no changes. SQLite integrity was `ok`, with zero foreign-key
violations. No fake stock, locations, customers, orders, payments or other business
data were created in it. Temporary browser fixtures and comparison files were
removed after verification.

## Remaining limits

No unresolved business decision blocks this slice. Historical Order locations stay
unknown/null, as authorized. If Bomet is absent or its eligible name is ambiguous,
staff must choose a branch. PostgreSQL concurrency tests remain unexecuted in this
SQLite environment; existing locking infrastructure is reused rather than claiming
new concurrency evidence from SQLite. No deployment was performed.
