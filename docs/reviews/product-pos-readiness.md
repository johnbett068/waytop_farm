# Product POS readiness and configuration diagnostics

Implemented 9 September 2026.

## Architecture and readiness

The existing dashboard had Product listing/creation, with maintenance available in
Django admin. ProductSaleUnit stores the sale conversion; ProductPrice stores
versioned Decimal KES prices, active state and effective periods. Publication
remains Product.is_published, labelled Show in public catalog. No models or stored
readiness flags were added.

Readiness is derived in apps/products/readiness.py. A Product is ready when active
and published, with an active canonical PRODUCT Inventory Item, no supply link,
matching Product/item base units, and at least one active Sale Unit with a positive
conversion and exactly one current, active, positive price. Price eligibility uses
the existing order pricing resolver. Every failing Sale Unit has its own reasons;
a Product with another fully configured Sale Unit can still be ready. Stock balance,
locations, lots and reservations are not inputs to this configuration status.

Diagnostics distinguish inactive/unpublished Products, missing active Sale Units,
missing/inactive/future/expired/zero/ambiguous prices, and missing or invalid inventory
configuration. Current prices shown in Product Management now use the order price
resolver rather than displaying an arbitrary active price outside its effective period.

## Staff workflows

- Product list shows publication, actual conversions, current price, inventory
  configuration, readiness and reasons. Existing Production eligibility remains.
- New Product detail at /dashboard/products/<id>/ shows configuration, selling
  units, current-price diagnostics and full price history.
- New edit screen at /dashboard/products/<id>/edit/ permits explicit name,
  description, category, active and publication changes. It requires the existing
  view/change Product permissions. Generated and legacy SKUs, slugs, base units,
  Sale Units and conversions are preserved. Category edits do not regenerate SKU.
- Detail includes explicit approved-price entry using existing ProductPrice.
  Requires view Product and add ProductPrice permissions. Staff chooses a Sale Unit
  belonging to that Product, Decimal amount, start/end and active status. Existing
  model validation and Sale Unit locking reject overlapping active periods. The
  workflow adds records only; it does not overwrite or close previous prices.
  An existing open-ended active price therefore blocks an overlapping new price.
- Sale Unit conversions remain read-only here, with explicit Counted as wording.
  Existing admin configuration functionality is retained. No conversion correction
  is inferred from the Sale Unit name.

## Inventory and POS

Product creation still creates no Inventory Item or stock. Acquire Stock still
accepts active unlinked Products and creates their canonical item atomically on a
legitimate receipt. Readiness computation creates nothing.

POS retains active/published/current-price eligibility and all branch checks. Its
empty message explains configuration and search requirements. Availability-provider
errors now display an inability-to-verify message, rather than falsely claiming
ordinary zero stock. Such entries remain disabled. Correctly configured zero-stock
products still display as out of stock at the selected branch. A priced published
Product missing its Inventory Item may remain visible but disabled; configuration
readiness correctly identifies it as not ready. No stock logic moved to Product
Management and no cross-location aggregation was introduced.

## Verification

Added 12 readiness/workflow tests and 2 POS diagnostic tests. They cover ready
configuration with no stock, publication/inactive states, missing/future/expired/
zero/invalid prices, inactive Sale Units, missing linkage, explicit publication,
identity and conversion preservation, price history/overlap protection, permissions,
and base-unit validation. POS tests cover unlinked priced Products remaining disabled
without creating inventory, and unpriced Products receiving configuration guidance.
Existing POS tests retain selected-branch and out-of-stock coverage.

Full regression: python manage.py test --noinput: 411 tests, 396 passed and 15
PostgreSQL-only tests skipped on SQLite. After final form improvements:
python manage.py test apps.products.test_readiness apps.dashboard.test_pos --noinput:
30 passed. Existing Product, Inventory, Order, Payment, availability, Supplier and
Location tests passed in the full run. Existing tests were not weakened.

Browser verification used a disposable separate SQLite database and headless Edge.
Verified Product list/detail/edit, publication and current price diagnostics, the
stored five-seedling conversion, explicit publication and price entry, readiness
without stock, unpublished exclusion, overlapping-price rejection with retained
Sale Unit selection, and branch availability of 5/20/0. Desktop and mobile layouts
were inspected; mobile retained the existing horizontally scrollable table without
page overflow. Temporary fixtures were never inserted in the real database.

## Database and remaining decisions

No schema changes or migrations. Migration checks passed before and after; the
existing migration graph and applied status were unchanged. makemigrations --check
--dry-run reports no changes.

Real db.sqlite3 SHA-256 before and after:
9FAA895EB5EA54B4D089B24D7BC3616767234B59B27F57D732F73F66748927BF

No business records, prices, publication states, conversions, inventory or stock
were changed in the real database. Dany F1 was not published or priced; Tomato
Seedling was not priced, given an Inventory Item, or converted from five to one.
The isolated browser database and script were removed after verification.

Staff must still deliberately decide publication and legitimate price amounts and
review Tomato Seedling's stored conversion. This implementation makes no such
business decisions. Replacing an open-ended current price without changing its
history is not provided by this append-only screen; it rejects overlap and retains
the existing administration workflow. No new price-replacement policy was invented.
