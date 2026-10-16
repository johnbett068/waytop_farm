# POS Sales UX cleanup — 1 October 2026

Sales checkout now uses **Complete Sale** for Cash and M-Pesa. Cash hides,
disables and removes the requirement from the M-Pesa reference input; its hint
contains no M-Pesa instructions. M-Pesa keeps the existing required reference,
normalization, length limit and duplicate-reference checks. There is no second
verification screen or newly introduced verification record.

Successful Sales checkout displays “Sale completed successfully.” and resets
the cart after the service transaction commits. Anonymous walk-in remains the
default and the selected branch remains selected for the next sale. Product
availability now includes the sale-unit name and selected branch. Existing
eligibility, disabled unavailable products, pricing and branch revalidation
remain intact. Bookings keep their existing confirmation and capacity behavior.

## Inventory behavior

Inspection found that the previous checkout reserved stock without issuing it.
Sales checkout now calls the existing `supply_ready_commitment` service for
each line inside the same atomic transaction as order/payment confirmation.
This posts authoritative ISSUE movements and consumes existing reservations
and allocations at the selected location. No balance is written directly.
Stable per-line idempotency keys prevent duplicate issues on replay. A failure
after an issue rolls back order, payment and inventory writes together, and the
view retains the cart. The existing `inventory.release` permission is enforced;
cashiers need it alongside existing checkout permissions. No roles were changed.

The Order remains CONFIRMED; this change does not redefine the separate
fulfillment lifecycle or change legacy pending-order confirmation workflows.

## Files changed

- `templates/dashboard/pos/checkout_live.html`: payment copy, button and branch/unit availability.
- `static/js/pos-payment.js`: method-specific Sales instructions.
- `apps/dashboard/pos_views.py`: Sales success message.
- `apps/payments/pos.py`: atomic Sales inventory issue orchestration.
- `apps/dashboard/test_pos.py`: retain legacy confirmation/supply coverage separately from checkout.
- `apps/dashboard/test_pos_bookings.py`: Sales issue and success expectations; booking regressions.
- `apps/dashboard/test_pos_sales_cleanup.py`: new Sales failure, replay, permission and inventory coverage.
- `apps/dashboard/test_pos_browser.py`: actual Chrome Sales and booking checks.
- This report.

## Executed verification

- `manage.py test apps.dashboard.test_pos apps.dashboard.test_pos_bookings --noinput`: 40 passed.
- `WAYTOP_BROWSER_TESTS=1 manage.py test apps.dashboard.test_pos_sales_cleanup apps.dashboard.test_pos_browser --noinput`: 7 passed at that point (5 cleanup tests and 2 Chrome tests).
- After adding recovery and permission checks: `manage.py test apps.dashboard.test_pos_sales_cleanup apps.payments apps.commitments.test_supply --noinput`: 49 passed, including all 7 cleanup tests.
- Chrome checked Cash/M-Pesa visibility, required reference, success/cart reset,
  location-specific physical stock deduction, duplicate-reference failure,
  branch switching, insufficient-stock cart revalidation and mobile overflow.
  The browser used the existing isolated POS Tomato fixture rather than a live
  Dany F1 product. Both Sales and Bookings were exercised.
- Desktop and 390px mobile Sales screenshots were inspected in
  `.tmp/pos-verification/sales-cleanup-desktop.png` and `sales-cleanup-mobile.png`.
- `makemigrations --check --dry-run`, with the runtime SQLite connection forced
  read-only: **No changes detected**. No schema changes or migrations created.
- `git diff --check`: passed (existing Windows line-ending warnings only).

## Database safety

All fixture creation and browser writes used Django's isolated test databases,
which the test runner destroyed afterward. No runtime migrations, seed commands,
resets, historical record edits or runtime business writes were performed.

The runtime SQLite SHA-256 changed during this session, so byte-for-byte
preservation cannot be certified. A read-only check found no isolated POS test
product fixtures in that database. The cause of the checksum change was not
established; no attempt was made to restore or overwrite the runtime database.
