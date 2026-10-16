# Product image upload guidance

Recommendation: **960 × 768 px, 5:4**. This is the existing main detail template's declared image size, not a new upload requirement or a fixed rendered size. Layout widths remain responsive. The validator accepts other dimensions; no new minimum, maximum, or aspect-ratio rule was introduced. Existing Pillow integrity and decompression-bomb checks remain in effect.

## Inspected public presentation

| Placement | Template dimensions | CSS frame | Image fitting |
| --- | --- | --- | --- |
| Shop/category Product cards | 640 × 512 | 5:4 | `cover`, edges may crop |
| Search results (shared catalog layout and card) | 640 × 512 | 5:4 | `cover`, edges may crop |
| Main Product detail | 960 × 768 | 5:4 | `contain`, whole photo visible with possible empty space |
| Additional detail images | 480 × 360 | 4:3 | `cover`, edges may crop |
| Homepage featured Products | 640 × 512 | 4:3 | `cover`, edges may crop |

Sources inspected: `templates/products/components/product-card.html`, `templates/products/components/catalog-layout.html`, `templates/products/search.html`, `templates/products/product_detail.html`, `templates/core/partials/featured-products.html`, `static/css/catalog.css`, and `static/css/home.css`. The later `.product-gallery img` rule overrides the earlier shared `cover` rule with `contain`.

Also inspected commerce CSS: wishlist uses 5:4 cover; mini-cart uses square cover; cart uses 5:3 cover on small screens and a layout-dependent frame on larger screens. No single aspect ratio eliminates cropping across all placements. A centred subject with space around it works across these frames. Existing `cover`/`contain` fitting preserves image proportions; it does not stretch photographs. The original uploaded file is stored without automatic resizing or cropping; cropping happens only in display frames.

## Staff UI and validation

Both Create Product and detail-page upload use shared guidance and preview templates. JPG/JPEG, PNG and WebP are recommended; GIF is also explicitly supported. Files must have valid image contents and a matching extension. The existing limit is **15 MiB (15,728,640 bytes)**, derived directly from `MAX_IMAGE_BYTES` for the UI. Existing supported formats, validator, storage, models and migrations are unchanged.

The preview uses local browser object URLs, shows filename, actual decoded width/height, MiB and byte size, and clears metadata when the file is cleared or the form resets. Nonrecommended dimensions are advisory, not rejection errors. A browser preview is not represented as proof of backend validity. No upload occurs until submission.

Changed files: `apps/products/forms.py`, `static/js/product-image-preview.js`, `templates/dashboard/products/form.html`, `templates/dashboard/products/images.html`, `templates/dashboard/products/detail.html`, new `image_guidance.html` and `image_preview.html` partials, `apps/products/test_image_browser.py`, and this report. No CSS changes were necessary; the existing contained staff preview style is reused.

## Verification

On 2026-09-29, the focused creation/image suites plus the opt-in Chrome workflow passed: **30 tests, OK**. The browser test was rerun after finalizing the MiB label with an explicit `15 MiB` assertion: **1 test, OK** (30.580 seconds). Browser assertions cover both upload previews, selected dimensions/filename, advisory wording, metadata clearing, and the existing detail/public upload/order/removal workflow. The creation screenshot was visually reviewed. `manage.py check` and `git diff --check` passed (Git reported existing line-ending warnings). The entire project suite was not rerun for this UI change.

Tests used isolated databases and temporary media. Real `db.sqlite3` SHA-256 remained `D088A26F266859602EE886F35DE380726716606E2B3BFA2ECEE605BCDFC5E99C` before and after the initial verification. No business records or real media were intentionally written, and no schema changes or migrations were made.
