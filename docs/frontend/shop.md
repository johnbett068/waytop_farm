# Shop page specification

## 1. Purpose

Provide a complete, trustworthy overview of WayTop's seedling catalog and help visitors narrow products by practical purchasing criteria.

## 2. Target users

Public visitors and prospective or returning customers. Authentication is not required.

## 3. Business rules

- Products belong to one public category and have a variety, price, sales unit and stock-status projection.
- Prices use Kenyan shillings and must always identify the unit.
- Branch stock is informational during discovery; viewing or filtering never reserves inventory.
- Unavailable and pre-order products remain discoverable.
- Phase 1C adds device-local Save and Add to Cart actions through the shared commerce service. These actions do not reserve stock or create an order.

## 4. Displayed data

Product name, slug, variety, category, short description, integer/Decimal-compatible price, display price, unit, stock status and featured-image reference. Catalog metadata includes category options and result count.

## 5. User actions

- Search by crop or variety through the Search page.
- Filter by category, availability and maximum unit price.
- Sort by featured order, name or price.
- Move between client-side result pages.
- Open Product Detail or Category Listing.
- Open/close mobile filters; clear filters.

Controls update the mock collection without a network request. No action changes business data.

## 6. Page states

Success, skeleton loading, no matching results, simulated result error (`?state=error`), offline global banner, limited/pre-order/unavailable stock, and branded HTTP errors. Permission denial is not applicable to this public read page.

## 7. Reusable components

Application shell, breadcrumbs, search form, product card, price, stock badge, filters, sort control, mobile drawer, pagination, skeleton grid and global page states.

## 8. Future models

`Category`, `Product`, `ProductVariant`, `ProductImage`, `UnitOfMeasure`, `PriceList`, `ProductPrice`, `Branch`, `BranchStock`, `CatalogVisibility` and merchandising/featured configuration.

## 9. Permissions

Anyone can view. Future catalog staff control product visibility and merchandising; pricing managers control published prices; inventory staff control stock through inventory services only.

## 10. Backend contract

- View: `apps.products.views.shop`
- URL: `/products/`, `products:shop`
- Method: `GET`; future query keys: `q`, `category`, `status`, `max_price`, `sort`, `page`, `branch`
- Response: paginated product read models plus filter facets and active filters
- Validation: allowlisted filter/sort values, positive page, published products/prices only
- Service: future `CatalogSearchService`
- Side effects: none

## 11. Future integrations

Database search, branch selector, inventory projections, product recommendations, analytics with consent, and later cart entry points.

## 12. Acceptance criteria

Responsive grid, sticky desktop filters, accessible mobile drawer/forms, keyboard controls, loading/empty/error states, stable shared product card, realistic data, design tokens, and Phase 1C Wishlist/Cart actions with unavailable products correctly blocked from Cart.
