# Optional image upload during Product creation

## Reverification on 2026-09-29

The requested implementation and tests were already present when this request was inspected. No application code, models, migrations, or business data needed changing in this pass; this report was updated and isolated browser screenshots were regenerated.

- Full relevant suite: `manage.py test apps.products --noinput --verbosity 1` ran 91 tests in 77.580 seconds, **OK (2 skipped)**. This includes the creation and image regression tests. The skips are the opt-in browser test and PostgreSQL concurrency test.
- Focused suite: `manage.py test apps.products.test_create_images apps.products.test_images --noinput --verbosity 1` ran 29 tests in 3.223 seconds, **OK**.
- Browser: `WAYTOP_IMAGE_BROWSER_TESTS=1 manage.py test apps.products.test_image_browser --noinput --verbosity 1` ran 1 test in 57.447 seconds, **OK**. Verified creation with/without an image, preview selection/replacement/clearing before submission, saved main image, detail navigation, public images, placeholders, additional upload, alt text, ordering and removal. The refreshed creation screenshot was visually inspected.
- `makemigrations --check`: **No changes detected**. `showmigrations`: all listed migrations applied. `migrate --plan`: **No planned migration operations**. No migrations were created or applied. Django test system checks reported no issues.
- Real `db.sqlite3` SHA-256 before and after these checks: `77E2BAF8692046641AA31F9EAD4A64FF5EB4AFF2345730C3A389D64767655735`. No existing business records were changed or fake records inserted into that database. Tests used isolated databases and temporary media; no real media files were created.
- The entire cross-application project suite was not rerun in this pass. Results below describe the earlier implementation verification, not this pass.

## Earlier implementation report

The staff Create Product page at `/dashboard/products/new/` now includes **Product image** after the existing selling fields. Staff with the existing Product image edit permission can select one optional image, see a local preview, enter optional alt text, and press **Save Product**. Saving opens the new Product's detail page at `/dashboard/products/<UUID>/`, where additional uploads, ordering, alt text and removal remain available.

The preview uses a browser object URL. Selecting, clearing or replacing the file does not upload it. Old object URLs are released when the preview changes, the form resets, or the page is left. Upload works without JavaScript. If validation fails, normal Django form values and errors are retained; the file must be selected again, as with normal browser file inputs.

The audit identified `product_create`, `StaffProductCreateForm`, and the transactional `create_seedling_product` service as the existing creation path. `ProductImageUploadForm` already supplied the required image validator and alt text. `ProductImage` already supplied the relationship, UUID path, storage, and deterministic ordering, so no model or schema changes were needed.

| Changed file | Purpose |
| --- | --- |
| `apps/products/forms.py` | `ProductFirstImageForm` specializes the existing upload form: image optional, inherited alt text/validation, no editable order for the first image. |
| `apps/products/images.py` | Reuses existing Product creation through a small optional-image orchestration function. Extracts the existing transaction/file-cleanup boundary for use by both creation and detail upload. |
| `apps/products/staff_views.py` | Binds POST/files to both forms, validates both before saving, uses the shared service, and displays storage errors without leaving a partially created Product. |
| `templates/dashboard/products/form.html` | Multipart form, optional Product image section, file selection, preview, alt text, and existing Save Product/Cancel actions. |
| `static/js/product-image-preview.js` | Local-only preview with clearing/replacement/reset and object-URL cleanup. |
| `static/css/staff-catalog.css` | Bounds the preview using existing spacing/style conventions. |
| `apps/products/test_create_images.py` | Nine focused creation/validation/transaction/preservation/permission regression tests. |
| `apps/products/test_image_browser.py` | Exercises actual creation with and without an image through staff navigation, followed by existing detail/public/commerce image workflows. |
| `docs/reviews/create-product-image-upload.md` | This implementation and verification report. |

The existing model, migration, upload validator, storage and filename function are unchanged. Supported JPEG/PNG/WebP/GIF content and the existing 15 MiB limit are preserved. A first image uses `sort_order=0`; the existing ordering determines the main image. No primary flag, Product image field, new storage mechanism, or publication rule was introduced. Blank alt text retains the Product-name fallback. Existing `products.change_product` image permissions are enforced, including on forged POSTs; staff without that permission can still create a Product without an image.

Both forms validate before persistence. With an image, the existing catalog creation transaction runs inside the shared upload transaction, and ProductImage is saved only after its Product exists. Failure rolls back Product, sale unit, optional price, SKU sequence update, and image record; a file already stored by a failed image save is cleaned up through the existing storage API. No operational records are created by this workflow.

Verification performed on isolated test databases and temporary media:

- `manage.py test apps.products.test_create_images apps.products.test_images --noinput --verbosity 1`: **29 tests, OK** (23.962 seconds).
- `WAYTOP_IMAGE_BROWSER_TESTS=1 manage.py test apps.products.test_image_browser --noinput --verbosity 1`: **1 test, OK** (114.129 seconds).
- `manage.py test --noinput --verbosity 1`: **467 tests, OK (17 skipped)** (487.060 seconds). That is 450 passing tests; skips are existing PostgreSQL-specific tests and opt-in browser tests. The image browser test passed separately as recorded above.
- `makemigrations --check --dry-run`: **No changes detected**.
- `showmigrations`: all existing migrations applied, including the unchanged `products.0003_productimage`.
- `migrate --plan`: **No planned migration operations**.
- `manage.py check`: **No issues**.
- No migrations were created, edited or applied for this enhancement.

Browser verification covered Products → Create Product, creation without an image, creation with an image, preview display/replacement/clearing before POST, saved main image on detail, navigation back through the Product-name link, the public image for the active/published Product, homepage/shop/search cards, additional upload, alt text, reorder, removal, cart/mini-cart/wishlist thumbnails and no-image placeholders. No JavaScript page errors occurred. The inspected screenshot is `.tmp/product-image-verification/create-image-preview.png`; the colored image is an isolated test asset.

Data safety: real `db.sqlite3` retained SHA-256 `e0f211efa9ffd1f2fecce3ab9e08223adb0be4949cf96d07951f46554cd4c1a7` before and after verification. No real Product/ProductImage or other business records were modified, and no fake records or test images were inserted into the real database/media. All 12 legacy WebP hashes match the earlier baseline. Tests also verify that creating a second Product leaves an existing Product, its image metadata, and its stored image bytes unchanged.
