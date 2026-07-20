# Master product catalog validation review

Status: **passed for frontend specification — production content approvals outstanding**  
Date: 15 July 2026

## Source-of-truth architecture

- [x] `docs/catalog/master-product-catalog.md` governs product identity and conventions.
- [x] `apps/products/mock_data.py` declares itself the executable mirror.
- [x] Homepage imports governed catalog objects instead of defining products.
- [x] Shop, Category, Search and Product Detail use the same records.
- [x] Stable unique SKU, slug and catalog version exist for every record.
- [x] Automated tests detect missing documented names/images, duplicate identities and category-count drift.

## Authenticity corrections

- [x] Replaced “Fordhook Giant Spinach” with botanically accurate “Fordhook Giant Swiss Chard.”
- [x] Replaced ambiguous “Gloria F1” with supported cultivar “Gloria Star F1.”
- [x] Standardized “Improved Sukuma Wiki” with `Thousand Headed` as its separate variety field.
- [x] Standardized `KPF 12 Passion Fruit`, `Red Oratia Tree Tomato` and species-level tree names.
- [x] Moved grafted Hass Avocado to Tree seedlings.
- [x] Merchandised watermelon under Fruit seedlings while documenting its cucurbit crop identity.
- [x] Separated grafted cultivar, vine, plug, bundle, tray and seed-propagated tree product types.

## Image policy

- [x] Every product references one unique existing WebP filename.
- [x] Django's static-file finder resolves every governed image path.
- [x] No product sprite remains.
- [x] Cards and Product Detail render the governed image filename.
- [x] Generated mock images are marked Replace Before Production.
- [x] Exact production replacement shots and provenance requirements are documented.

## Data completeness

Every executable product has name, variety, category, price, unit, stock status, branches, individual image, planting guide, growing guide, description, recommended regions, SKU and catalog version.

## Verification

- Django system check: passed.
- Project test suite: 15 tests passed.
- Individual product images: 12 unique files, all WebP.
- Declared category counts match executable products.
- Removed inaccurate names do not occur in the catalog data.

## Production blockers

- WayTop management must confirm the actual products it stocks and sells.
- Mock price ranges and current mock amounts require commercial approval.
- Branch availability and nursery batch cadence require operational approval.
- Generated images require replacement with verified WayTop product photography.
- Growing regions, maturity guidance and planting instructions require qualified agronomic approval.

These blockers prevent treating mock values as live business data, but do not block the frontend catalog specification.
