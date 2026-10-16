# Product images implementation — 11 September 2026

Customer-facing photographs now belong to Product and are managed from the existing Product detail page. The public catalog uses the first ordered image as its main image and keeps the existing WT placeholder when no usable main-image file is available.

| Requested report item | Implemented result |
| --- | --- |
| 1. Model structure | `apps.products.ProductImage`: UUID `id`, `product`, `image`, optional `alt_text` (250 characters), nonnegative `sort_order` (default 0), and automatic `created_at`. |
| 2. Product relationship | One-to-many `ProductImage.product` foreign key with reverse relation `Product.images` and cascading record deletion. No Product field, primary-image foreign key, or separate public-site media domain was added. |
| 3. Storage | Django `ImageField` and the configured default storage. Files use `products/<product UUID>/<image UUID hex>.<extension>`. UUID filenames prevent upload-name collisions. Only the storage path and metadata are stored in the database; image bytes remain in media storage. |
| 4. Validation | Genuine JPEG, PNG, WebP and GIF files, at most 15 MiB. Pillow verifies and decodes image content; filename extensions must match the detected format. Invalid, damaged, oversized and decompression-bomb images are rejected. Staff forms and model saves enforce validation. Blank alt text falls back to the Product name; supplied text is trimmed. No descriptions are generated. |
| 5. Main-image ordering | Explicit ordering is `sort_order`, then `created_at`, then UUID `id`. The first record is the main image. Reordering or deleting it changes the next catalog projection immediately. There is no `is_primary`, separate primary reference, or cached ordering. |
| 6. Product Management | A Product Images section on existing staff Product detail provides previews, a Main image label, upload, alt-text editing, numeric display order, and removal. Active staff need `products.view_product` to view and `products.change_product` to mutate images. No new permission system or navigation entry. Product creation stays image-optional; existing editing, pricing and price history remain intact. |
| 7. Public catalog | `public_catalog_products()` prefetches ordered image records alongside existing selling data. Its `is_active=True, is_published=True` filter is unchanged. Homepage, shop and search cards show the main image. Product detail shows the main image and ordered additional images, whose links open the stored files. Missing files do not generate image elements with broken URLs; Products without images retain WT placeholders. |
| 8. Commerce JSON | The existing `commerce_catalog_projection()` adds only `main_image: {url, alt}` or `null`. Existing slug, name, description, product URL and sale-unit keys are preserved. Existing cart, mini-cart and wishlist rendering uses that thumbnail. Galleries are not serialized into commerce JSON. No order or payment API was changed. |
| 9. Media serving | Existing `MEDIA_ROOT = BASE_DIR / "media"` and `MEDIA_URL = "media/"` are reused. Root URLs append Django development media serving only under `DEBUG`. Security settings are unchanged. Local uploaded media is ignored by Git. |
| 10. Dependency | Added and installed `Pillow==12.3.0` through `requirements.txt`. Existing optional Playwright tooling was used for browser verification; no browser dependency was added to runtime requirements. |
| 11. Migration filename | `apps/products/migrations/0003_productimage.py`, dependent on `products.0002_product_category_and_sku_sequence`. Its only schema operation is `CreateModel(ProductImage)`. |
| 12. Migration status | Applied successfully to the local database after a backup and pre-existing-row snapshot. All migrations show applied; `migrate --check` succeeds and `migrate --plan` has no pending operations. |
| 13. Migration graph | No conflicts or unexpected migrations. Baseline and final `makemigrations --check --dry-run` report no changes. Before application, the plan contained only `products.0003_productimage`. Fresh isolated test databases successfully applied the complete migration graph during both automated and browser tests. |
| 14. Automated tests | Focused Product/core/cart/wishlist suite: **94 tests, OK, 2 skipped** (21.662 seconds). Full project suite: **458 tests, OK, 17 skipped** (139.885 seconds). The full run has 441 passing tests; skips cover PostgreSQL-specific tests and opt-in browser tests. New focused image coverage comprises 20 tests. Django system checks report no issues. |
| 15. Browser verification | Separate opt-in Chrome run: **1 test, OK** (28.777 seconds), using Django's isolated test database and a temporary media directory. Verified actual uploads and loaded previews, main ordering, homepage/shop/search cards, detail gallery, cart/mini-cart/wishlist thumbnails, reorder, successive deletion, single-image rendering and WT placeholders. No JavaScript page errors. Desktop and 390px mobile screenshots were inspected; mobile gallery had no horizontal overflow. |
| 16. Real database | Intentionally changed only by the approved image schema migration and Django bookkeeping: one migration row and one ProductImage content-type row. No test uploads were placed there. The new real `products_productimage` table contains **0 rows**. |
| 17. Existing business records | Compared **358 pre-existing rows across 56 tables** before and after migration. Every pre-existing row remained unchanged; business-table row counts stayed unchanged. Product configuration, selling units, prices/history, inventory, production, bookings, orders and payments were preserved. SQLite integrity check: `ok`; foreign-key violations: **0**. |
| 18. Legacy assets | All **12** legacy Product WebPs retain their original SHA-256 hashes. No file was imported, attached, renamed, deleted or modified. Existing legacy asset contract tests remain and pass. |
| 19. Production consideration | Production must provide persistent media storage and delivery independently of Django's development server: for example, a web-server media mapping for the configured local storage, or an explicitly configured storage backend. No cloud infrastructure or production serving choice was invented. |

Deletion uses Django's storage API after the database transaction commits. A rollback retains the file. Cleanup is restricted to the image's own Product/UUID path and checks that no surviving image record references it. Failed upload persistence cleans up its stored file. Files cannot be attached by supplying a stored path, moved between Products, or replaced through metadata editing; staff can upload a replacement and remove the old image. The upload service owns its transaction so it can clean up a failed upload. Storage deletion errors are logged rather than undoing a committed database operation.

Tests cover relationship/path, all four supported formats, invalid/spoofed/truncated/oversized input, deterministic ties, main-image promotion, reorder and alt changes, rollback and failed-upload cleanup, forbidden path attachment or Product reassignment, public cards/gallery/placeholders, inactive and unpublished exclusion, projection/query behavior, successful staff actions, read-only/anonymous/nonstaff/inactive denial, cross-Product action rejection, form errors, and DEBUG-only media delivery. Existing tests cover image-optional Product creation, prior pricing workflows and legacy assets.

Verification commands used the project virtual environment:

```powershell
.\.venv\Scripts\python.exe manage.py test apps.products apps.core apps.cart apps.wishlist --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py test --noinput --verbosity 1
$env:WAYTOP_IMAGE_BROWSER_TESTS='1'
.\.venv\Scripts\python.exe manage.py test apps.products.test_image_browser --noinput --verbosity 1
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py check
```

Local verification artifacts are under `.tmp/product-image-verification/` (ignored by Git):

- Backup: `db-before-images-20260911T052509Z.sqlite3`.
- Baseline hashes: `baseline.json`; migration comparison: `database-preservation.json`.
- Before database SHA-256: `2dc20417ab670dfd4b1a3c95db55cbfc774bac34d2072c988ed2cb124988b043`.
- After database SHA-256: `e0f211efa9ffd1f2fecce3ab9e08223adb0be4949cf96d07951f46554cd4c1a7`.
- Inspected screenshots: `management.png`, `gallery-desktop.png`, `gallery-mobile.png`. The colored test images exist only in isolated verification storage, which is cleaned up after the test.

Pre-existing working-tree changes for POS and other operations were preserved. This implementation adds catalog image capability and the small existing customer-commerce thumbnail integration only.

## Staff navigation follow-up

The targeted audit confirmed that `/dashboard/products/` uses `dashboard/products/list.html`, whose Product-name links resolve to `/dashboard/products/<product UUID>/` (`dashboard:catalog_product_detail`). That view renders `dashboard/products/detail.html`, which includes `dashboard/products/images.html` with upload and image-row context. The upload form was present on this actual route, with no CSS hiding it. Its controls require `products.change_product`; staff without that permission previously saw no explanation. Product creation previously redirected to the list, whose guidance highlighted only pricing.

The integration now redirects successful Product creation to Product detail, explains the Product-name link on the list, and adds a visible **Add Image** link beside the Product Images heading. That link jumps to the existing upload form; staff choose a file and press **Upload image**. Read-only staff see an explanation of the required Product edit permission. Permissions, the create form, image model and migration remain unchanged.

Verification: Product suite **82 tests, OK (2 skipped)**; separate Chrome test **1 test, OK**, now entering through the staff sidebar **Products → Product name → Product Images → Add Image → Upload image** before exercising upload, public rendering, reorder and removal in isolated storage/database. Migration drift and system checks pass. The real database retains SHA-256 `e0f211efa9ffd1f2fecce3ab9e08223adb0be4949cf96d07951f46554cd4c1a7`; no business data or real images changed.
