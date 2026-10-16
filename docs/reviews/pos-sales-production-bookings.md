# POS Sales and Production Bookings

Implemented against the owner's ratified September 2026 rules, including the explicit definition of `ProductionBatch.current_quantity` as current expected usable production. This report supersedes earlier POS-only READY/M-Pesa restrictions for the POS paths described here. Ecommerce and the existing administrative READY verification command retain their established boundaries.

## Audit and architecture

Audited Product, ProductSaleUnit, ProductPrice, canonical PRODUCT InventoryItem, InventoryLocation, StockLot, StockPosition, ProductionBatch and its audited services, Order and OrderLine snapshots, Payment and evidence/history, Commitment, Reservation, SourceAllocation, processing, supply, cancellation, idempotency, existing migrations and tests.

Reused the existing Order, Customer, Payment, Commitment and inventory architecture. No Booking, CashPayment, duplicate stock, production branch, or expected-usable-quantity model/field was created.

- `production.services.update_batch()` locks the batch, rejects quantity increases, and records the previous/current quantities with actor, reason, correlation and idempotency identity. Those decrease rules remain intact.
- `production.capacity` is an explicit future-capacity path. The existing READY availability service still rejects PRE_ORDER; it is not bypassed or weakened.
- OrderLine identifies its production batch and snapshots expected readiness. The immutable Order location supplies the booking branch. Existing PRE_ORDER Commitment counters and history represent future demand.
- Existing confirmation permissions remain `pos.process_sale`, `payments.verify` and `commitments.allocate` for POS checkout. Existing `orders.process`, `orders.cancel` and Production permissions retain their meanings; no capabilities or user grants were invented.

## Capacity, location and readiness

For each eligible batch, capacity is `max(0, current_quantity - active outstanding booking base quantities)`. `quantity_started` is never used in this calculation. An audited decrease affects the next authoritative capacity read, including when remaining capacity reaches zero because existing commitments exceed a revised forecast. Existing commitments are not silently cancelled or rewritten after losses.

Only `IN_PRODUCTION` batches with positive current quantity, an expected readiness date, an active saleable matching location and a safely representable published active product/Sale Unit are offered. A canonical active compatible PRODUCT InventoryItem is required by the reused Commitment architecture, but no on-hand stock is required. Current valid positive prices are resolved by the existing quote service.

Outstanding quantities are counted once from ACTIVE Commitments linked through OrderLine to the batch. Cancellation uses the existing CANCELLED state/counters and append-only Commitment/Order events. Cancelled or satisfied commitments are not counted. Cancelling a booking releases future demand and leaves the payment recorded; it does not perform a refund or any stock operation.

Whole sale units are calculated with Decimal division and floor. All lines against a batch are checked together, including mixed Sale Units. Exact Decimal values are summed in Python to avoid SQLite floating-point SUM behavior. Each checkout locks the batch before reading capacity and keeps that lock until confirmation commits. Audited decreases use the same batch lock. PostgreSQL uses the existing advisory idempotency and row locks; SQLite contending writes fail atomically and can retry the complete command.

Every checkout carries an explicit location. The unique eligible Bomet remains the default; absence/ambiguity requires selection. Neither inventory nor future capacity is combined across branches. Historical unassigned batches remain unbookable. Production staff can assign their actual location through the audited update form. A batch already referenced by booking lines cannot change location and invalidate historical booking identity.

The POS shows batch, bookable Sale Units, location, current price and **Expected readiness**, without promising delivery. Each line snapshots its expected readiness; the order's existing required-date field receives the latest batch estimate at creation when no date is supplied. Future production schedule changes do not rewrite commercial snapshots.

## Sales, payments and carts

Sales is the default tab. Bookings has a separate tab and `pos_booking_cart` session; Sales retains `pos_cart`. Server-side validation enforces the transaction type and forbids mixed READY/PRE_ORDER checkout.

Both methods use `payments.pos.checkout_pos()` and finish at Payment CONFIRMED / Order CONFIRMED:

- Cash: the authorized cashier confirms receipt. No reference, M-Pesa evidence, or verification attempt is created.
- M-Pesa: the cashier enters the existing supported reference, which is required, normalized and checked for reuse. One confirmation action records evidence and an internal accepted attempt plus payment/order history. This is cashier acceptance, not a fabricated external-provider check.

The POS no longer accepts separate `evidence` or `verify` actions or renders evidence selection/verification-reason forms. Existing pending POS orders expose a single confirmation action. The administrative `verify_payment_and_confirm_order()` service and historical records remain available.

The shared confirmation implementation creates READY Commitments, Reservations and Allocations for sales. It creates only PRE_ORDER Commitments for bookings. Neither path physically consumes inventory or automatically starts processing. Sales retain explicit CONFIRMED -> PROCESSING -> supply/ISSUE -> fulfillment. Bookings remain future commitments; the existing prohibition on directly supplying or processing PRE_ORDER stock remains intact. This change does not introduce a Production-to-Inventory handoff or automatic future fulfillment.

The cart is reset only after the atomic checkout service returns successfully. The selected branch remains; lines/customer are cleared and a new idempotency key is issued. Completed records remain persisted. Validation, reference reuse, insufficient stock/capacity, database contention and server errors preserve the cart. The atomic command rolls back partial Order, Payment, evidence, Commitment, Reservation and Allocation writes on failure.

Order creation identity includes line product/unit/quantity/mode/batch, customer, location and payment method. Payment confirmation records a unique key and fingerprint including order, method, normalized reference and actor. Identical service retries return the existing confirmed transaction, including after later lifecycle changes. Changed input is rejected. Submissions whose key no longer matches the current session are rejected without clearing its cart.

## Migrations

| App and migration | Schema change | Reason |
| --- | --- | --- |
| `production/0002_productionbatch_location_and_more.py` | Nullable protected batch location; previous/current location references on batch history | Establish future branch capacity without guessing historical locations; audit staff assignments |
| `orders/0006_orderline_expected_ready_date_and_more.py` | Protected nullable production batch, readiness snapshot and paired PRE_ORDER metadata constraint | Bind existing order/commitment architecture to actual production capacity |
| `payments/0004_remove_payment_payment_method_mpesa_and_more.py` | CASH choice, updated method/confirmation constraints, unique nullable POS confirmation key and fingerprint | Represent cash without fictitious M-Pesa references and retain safe confirmation retries |

No data deletion, resets, fake business records, RunPython or RunSQL were added. The previous M-Pesa-only constraints are replaced with method-specific constraints; historical payment facts are retained.

## Verification

- Full repository suite: `python manage.py test --noinput --verbosity 1` — **437 tests, OK, 16 skipped**, 338.250 seconds. This covers POS, Orders, Payments, Commitments, Reservations, Allocations, Inventory, Availability, Production, Fulfillment, Products and the other installed application suites.
- The 16 skips are 15 pre-existing PostgreSQL-only integration tests on the configured SQLite backend and the opt-in browser test. PostgreSQL execution was not claimed. The two new booking concurrency tests ran successfully on SQLite, covering competing quantities and concurrent same-key retries.
- Final focused POS run: `python manage.py test apps.dashboard.test_pos apps.dashboard.test_pos_bookings --noinput --verbosity 1` — **40 tests, OK**, 19.641 seconds. The 22 booking/payment tests include capacity boundaries, exact Decimal conversion, losses, branch separation, snapshots, cancellation, anonymous customers, method/reference validation, idempotency, permissions, both carts, and late transaction rollback with cart retention.
- Actual Chrome run: `WAYTOP_BROWSER_TESTS=1 python manage.py test apps.dashboard.test_pos_browser --noinput --verbosity 1` — **1 test, OK**, 38.968 seconds. All migrations and transaction fixtures were created in Django's isolated test database. Cash and M-Pesa were exercised for Sales and Bookings; all four confirmed and cleared their carts. The test checked Bomet/other-branch capacity isolation, expected readiness, hidden Cash reference input, no Verify Payment step, duplicate-reference rejection retaining the cart, unchanged inventory movements, and no automatic processing. Desktop/mobile screenshots were inspected; the 390px viewport has no horizontal overflow. No JavaScript errors were reported.
- Browser artifacts: [desktop](../../.tmp/pos-verification/bookings-desktop.png), [mobile](../../.tmp/pos-verification/bookings-mobile.png). Playwright was installed only in the local virtual environment for this optional verification; it is not a runtime application dependency.
- Baseline and final `makemigrations --check --dry-run`: **No changes detected**. Fresh database migration completed successfully during the isolated suites and browser test. The intended three migrations were subsequently applied to the working database; the final migration plan is empty and Django system checks pass.

## Working database preservation

`db.sqlite3` was unchanged throughout test/browser execution. Before applying the three reviewed migrations, a SQLite backup was created at `.tmp/pos-verification/db-before-pos-20260910T154501Z.sqlite3`.

The working database was then intentionally changed by schema migrations and Django migration bookkeeping. A before/after comparison of **every original column in 55 tables and 280 rows**, excluding the migration bookkeeping table, found **no changed original values**. No existing business records were manually edited and no fake transactions, production, customers or inventory were inserted. `PRAGMA integrity_check` returned `ok`; `foreign_key_check` found zero violations.

- Before SHA-256: `2ac728dd7d21de9a7a7afa3f828a5ac74bd80605a59fc682f2004f913206dc2d`
- After SHA-256: `637d0ae203380309d3ba6fd36754b59bd8155ec0205307c55e8c800952b0659c`
- Machine-readable evidence: [database-preservation.json](../../.tmp/pos-verification/database-preservation.json).

No business-rule blockers remain for Sales and paid production bookings. Unassigned historical production remains unavailable for booking until production staff record its actual location through the audited workflow. Automatic production handoff, PRE_ORDER physical supply and refunds have not been invented. PostgreSQL-specific concurrency behavior remains an explicitly unexecuted verification surface on this SQLite environment.
