# POS Sales workspace layout ? 1 October 2026

The Sales page now uses a compact workstation layout. Desktop product and cart
columns use a 1.55:1 ratio (approximately 61/39), with inline heading/tabs and
location controls. Product cards include the existing first ordered ProductImage,
its safe display URL and alt text, or the existing WT placeholder. Image records
are prefetched; eligibility and price queries retain their existing rules.

The cart is sticky below the staff topbar. Only the cart-item list scrolls when
it exceeds eight rem, keeping totals and checkout controls accessible. On screens
at or below 1100px, panels stack Products then Cart/Payment; sticky positioning
and the cart-item scroll limit are removed. Totals are emphasized, controls are
compact, and unavailable products retain disabled Add to cart controls.

Cash hides the entire reference field without leaving an empty section. Sales
completion stays disabled when the server reports an invalid cart/location or
when the M-Pesa reference is blank. Server validation remains authoritative.
The existing payment select, anonymous customer default, branch switch/revalidation,
stock deduction, cart reset, failure handling, idempotency and separate Bookings
workflow remain unchanged. No domain service, model or migration was changed.

## Files changed

- templates/dashboard/pos/checkout_live.html ? workspace structure, cards/images, totals and checkout attributes.
- static/css/staff-pos-live.css ? Sales-scoped responsive layout and spacing.
- static/js/pos-payment.js ? required-reference button state.
- apps/dashboard/pos_views.py ? prefetch existing Product images only.
- apps/dashboard/test_pos_browser.py ? viewport checks and updated missing-reference assertions.
- apps/dashboard/test_pos_workspace.py ? existing image and missing-file placeholder coverage.
- docs/reviews/pos-sales-workspace-layout.md ? this report.

## Verification

The initial combined run exercised 50 tests: 49 passed, with the new layout test
failing during fixture setup because Playwright had already started its async
context. The fixture rename was moved before Playwright startup, and the layout
test then passed. The independent image/placeholder test also passed. Existing
business assertions were retained, including failure rollback and stock isolation.

Actual headless Chrome checks used Django isolated test databases. At 1366x768,
location, search, first product/Add to cart, cart heading, total, payment method
and Complete Sale were verified inside the viewport without scrolling, with an
empty cart and after adding the isolated Dany F1 fixture. Cash/M-Pesa visibility,
required-reference disabling, successful sale, branch stock deduction and empty
cart were checked. Existing browser tests also exercised Bookings and failures.
Mobile checks at 390x844 verified stacked panels and no horizontal overflow.
Desktop and mobile screenshots were visually inspected:

- .tmp/pos-verification/workspace-desktop.png
- .tmp/pos-verification/workspace-mobile.png

Migration checking ran with the runtime SQLite connection forced read-only:
`makemigrations --check --dry-run` returned **No changes detected**.
Targeted `git diff --check` passed.

## Database safety

All test records were created only in isolated Django test databases and image
files in temporary test storage. No runtime migration, seed, flush, reset or
business-record update was performed. The runtime database checksum changed
during the session; its cause was not established, so byte-for-byte preservation
cannot be certified. The runtime database was not restored or overwritten.

The final isolated Chrome rerun also passed the long-product-area scroll check: the cart stayed sticky and Complete Sale remained inside the viewport. Across the targeted runs, all 51 distinct tests passed after the fixture correction.
