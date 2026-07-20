# Phase 1B milestone review

Status: **complete — passed 15 July 2026**

Scope reviewed: Shop, Category Listing/Detail, Search, frontend filters/sorting/pagination, Product Detail, related/recent products, specifications, planting guidance, branch availability and required states. Wishlist, Cart, Checkout, authentication, payment and backend APIs were not implemented.

## Architecture

- [x] One mock catalog contract powers every discovery page.
- [x] Product cards, filters, catalog layout, skeletons and breadcrumbs are shared components.
- [x] Catalog interactions are isolated in one frontend module with no business mutations.
- [x] Product Detail composes related, recent and branch read projections without inventory side effects.
- [x] Phase 1A was changed only for verified route integration and bug fixes.

## UI/UX consistency

- [x] Responsive card grid, clear price/unit display and consistent availability badges.
- [x] Sticky desktop filters and focused mobile filter drawer.
- [x] Search, filters, sorting and pagination compose over the same result set.
- [x] Product Detail provides decision-support information before any future Cart action.
- [x] Product-specific photography differentiates twelve catalog items.
- [x] Valid empty category and empty search experiences are constructive.

## Accessibility

- [x] Semantic landmarks, headings, breadcrumbs, forms, fieldset/legend and live result count.
- [x] Search and filter controls have programmatic labels.
- [x] Stock information appears as text, not color alone.
- [x] Mobile filter dialog supports focus entry, Tab containment, Escape, close controls and focus return.
- [x] Native hidden-state semantics and visible focus tokens are preserved.
- [x] Tablet navigation regression repaired by retaining the drawer until desktop width.

## Responsiveness

- [x] Browser review at 390 px, 768 px and 1440 px.
- [x] Shop, Categories, empty category and Product Detail reviewed.
- [x] Search empty/error states reviewed on mobile.
- [x] Product grids progress from one to two to three columns.

## Performance

- [x] Catalog stylesheet: approximately 16 KB uncompressed.
- [x] Catalog JavaScript: approximately 8 KB uncompressed.
- [x] Superseded by the master-catalog policy: twelve individually addressable WebP product images are now used; no sprite remains.
- [x] Temporary generated sheet sources were removed from the project after individual WebP exports.
- [x] No raw colors outside the design-token file.
- [x] No duplicated per-product card markup.

## Page states

- [x] Skeleton loading grid.
- [x] Empty search/filter results.
- [x] Valid category with no products.
- [x] Simulated catalog error state.
- [x] In-stock, low-stock, pre-order, unavailable and branch partial availability.
- [x] Offline global banner and branded HTTP errors.
- [x] CSS regression that kept hidden skeletons visible was found during review and fixed globally.

## Documentation

- [x] `docs/frontend/shop.md`
- [x] `docs/frontend/categories.md`
- [x] `docs/frontend/search.md`
- [x] `docs/frontend/product-detail.md`
- [x] `docs/flows/product-discovery.md`
- [x] Business rules, permissions, models, contracts and integrations documented per page.

## Verification

- Django system check: passed with no issues.
- Project test suite: 10 tests discovered and passed.
- Frontend DOM search: query `tomato` produced two matches and hid ten non-matches.
- Required route responses: Shop, categories, category, search and product detail returned HTTP 200; unknown slugs returned 404.
- Prohibited labels/actions: no Cart, Wishlist or Buy Now controls.
- Hardcoded absolute template links: none.

## Future-content controls

- Generated product photography is mock catalog media and must pass business/botanical approval before production publication.
- Branch quantities remain deliberately qualitative until the inventory backend exists.
- General planting guidance requires qualified content approval before production.
- Mock contact details and Phase 1A business claims still require verification.

All Phase 1B Definition of Done items pass. Wishlist and Cart must not begin until separately scoped and approved.
