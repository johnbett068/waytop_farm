# Product editing and customer-facing images

Implemented 2026-09-30, building on the existing uncommitted ProductImage implementation.

## Implementation

- `templates/dashboard/products/list.html`: an explicit Edit action for every Product that the authorized editor can see, regardless of active/publication/POS readiness. View-only staff retain View access.
- `templates/dashboard/products/edit.html`: Product information, immutable SKU display, stock unit, selling configuration, Price settings link and the existing image management section. Each section has its own save action, explicitly explained on the page.
- `apps/products/forms.py`: stock-unit editing with existing model validation; existing sale-unit editing; compact description widget. Omitted stock units from older callers retain their existing value.
- `apps/products/services.py`: Product edit retains identity and validates stock-unit immutability after Inventory use. Sale-unit editing validates the existing model and requires the existing `change_productsaleunit` permission. Historical prices remain unchanged.
- `apps/products/staff_views.py`: both Edit and Detail use one shared image form/action handler and the existing upload/update/delete services. Successful Edit actions return to Edit. Storage errors render a recoverable error.
- `templates/dashboard/products/images.html`: explains customer-facing publication and independent image saves.
- `static/css/staff-catalog.css`: preserves table-cell layout, styles selects consistently and aligns checkboxes.
- `apps/products/test_edit_images.py`: isolated regression tests for Edit, permissions, images, selling, publication and business-data safety.
- `apps/products/test_image_browser.py`: extends the existing isolated Chrome workflow to enter Edit directly from the list, save Product information, manage images, verify publication safety and capture desktop/mobile views.

No second image model, Product image field, primary flag, migration, pricing mechanism or commerce JSON contract was introduced. Images retain `(sort_order, created_at, id)` ordering, so the first image is main and deletion promotes the next. Existing guarded, on-commit file cleanup is reused. Blank alt text falls back to the Product name. Uploading never publishes a Product. Existing optional Create Product uploads and Detail image management remain supported.

## Image guidance and inspected placements

Recommendation remains **960 x 768 pixels (5:4)**. Dimensions are recommended, not mandatory. Supported formats remain JPEG/JPG, PNG, WebP and GIF. The required maximum is **15 MiB (15,728,640 bytes)**. Existing Pillow validation verifies genuine, decodable content, matching extensions, supported formats and the byte limit; decompression-bomb protection remains enabled. Files are stored without resizing or cropping.

| Placement | Inspected implementation | Display behavior |
| --- | --- | --- |
| Catalogue/search cards | `templates/products/components/product-card.html`, `static/css/catalog.css` | 5:4, `object-fit: cover`; edges can crop |
| Product detail main | `templates/products/product_detail.html`, `static/css/catalog.css` | 5:4 frame, `object-fit: contain`; whole photo visible |
| Additional detail images | Same detail template/CSS | 4:3, cover |
| Homepage featured Products | `templates/core/partials/featured-products.html`, `static/css/home.css` | 4:3, cover |
| Wishlist | Existing commerce rendering, `static/css/commerce.css` | 5:4, cover |
| Cart | Existing commerce rendering, `static/css/commerce.css` | 5:3 on small screens; stretches frame height on larger screens, image cover |
| Mini-cart | Existing commerce rendering, `static/css/commerce.css` | 5rem square, cover |

There is no universal placement ratio. The existing 5:4 recommendation matches catalogue/search, wishlist and the main detail frame. Staff guidance explains the other crops and recommends keeping the whole Product near the centre with space around it.

The shared browser preview uses object URLs without uploading before submission, updates when replaced, clears when deselected, and shows filename, dimensions and file size. Other valid dimensions produce a recommendation rather than rejection.

## Database and data safety

No migration required or created. `makemigrations --check`: no changes detected. `showmigrations`: all existing migrations applied, including existing `products/0003_productimage.py`. `migrate --plan`: no planned migration operations. `manage.py check`: no issues.

Real `db.sqlite3` SHA-256 before and after implementation:

`D088A26F266859602EE886F35DE380726716606E2B3BFA2ECEE605BCDFC5E99C`

All automated and browser fixtures use Django's isolated test database and temporary media storage. No real Products, ProductImages, business records or legacy static WebPs were modified or added. The real database was never reset, migrated, flushed or seeded. No legacy photos were attached. Static Product image files have no Git changes.

## Verification

- Focused Edit regression suite: `python manage.py test apps.products.test_edit_images --noinput` — **13 passed, 0 skipped**. Includes a Product with real test-fixture stock, orders, payment and production records, and verifies all those rows remain unchanged. Stock-unit changes after Inventory use are rejected.
- Existing Products suite before adding the new Edit tests: **89 passed, 2 skipped** (91 discovered).
- Final full repository suite: `python manage.py test --noinput` — **463 passed, 17 skipped, 0 failures** (480 discovered; 346.912 seconds). Skips are opt-in browser tests and PostgreSQL-only concurrency checks on SQLite. The Product image browser workflow was run separately and passed; the separate POS browser and PostgreSQL-specific checks were not run.
- Browser: `WAYTOP_IMAGE_BROWSER_TESTS=1 python manage.py test apps.products.test_image_browser --noinput` — **1 passed, 0 skipped**, using headless Chrome, Django's test database and temporary media. Final run: 41.962 seconds.
- Browser checked list Edit navigation; existing Product/selling fields; Product save; Create with and without an optional photo; preview replacement, clearing, dimensions, filename and bytes without a POST; Edit upload and alt text; reorder and public main-image changes; deletion and next-image promotion; homepage/catalogue/search/detail photos; cart/mini-cart/wishlist thumbnails; WT placeholders; unpublished Product upload remaining unpublished and returning public 404; desktop/mobile layout and no JavaScript errors. The 404 in its log is the expected publication-safety check.
- Visually reviewed `.tmp/product-image-verification/product-list-edit.png`, `management.png` and `edit-mobile.png`. Additional public gallery and creation-preview screenshots are in the same directory.
- Logs: `.tmp/product-edit-focused.log`, `.tmp/product-edit-browser.log`, `.tmp/product-edit-full-suite.log`.

## Production delivery

Existing local `MEDIA_ROOT` and `MEDIA_URL` remain in place. Django serves media through the development URL configuration only when DEBUG is enabled. Production must persist and serve that media through the deployment's web server or existing storage arrangement; production media delivery is not explicitly configured in this repository and was not deployed or verified in this task. No cloud infrastructure was added.
