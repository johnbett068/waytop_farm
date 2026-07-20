# Product Detail specification

## 1. Purpose

Give growers enough trustworthy information to judge whether a seedling suits their farm and prepare for a later cart decision.

## 2. Target users

Public customers, commercial growers, institutions and staff assisting customer enquiries.

## 3. Business rules

- Price always includes its sales unit.
- Availability belongs to a branch and is a read projection, not a reservation.
- Planting guidance is general and must not replace site-specific professional advice.
- Product, variety and unit identities remain stable when referenced by later orders.
- Related products share a category in Phase 1B.
- Recently viewed data is explicitly mocked; future tracking requires privacy controls.
- Phase 1C enables device-local Wishlist and Cart actions. Review submission, Checkout and backend mutations remain excluded.

## 4. Displayed data

Name, slug, category, variety, long/short description, price, unit, image, overall stock status, planting period, growing duration, specification key/value pairs, ordered planting steps, three branch status rows, related products and recently viewed products.

## 5. User actions

Follow breadcrumbs, inspect specifications/guidance, select an eligible preferred branch, save to Wishlist or add to Cart, open related/recent products and return to the category. Adding to Cart remains a planning action with no reservation.

## 6. Page states

Available, low-stock, pre-order and unavailable; branch partial availability; related/recent collections; offline; branded 404 for an unknown product; global server error. Loading components are reusable for future dynamic availability. Permission denial is not applicable.

## 7. Reusable components

Breadcrumbs, stock badge, price/unit display, product card/rail, section heading, branch card and global states.

## 8. Future models

`Product`, `ProductVariant`, `Category`, `ProductImage`, `ProductSpecification`, `PlantingGuide`, `PlantingGuideStep`, `UnitOfMeasure`, `ProductPrice`, `Branch`, `BranchStock`, `RelatedProduct`/recommendation configuration and privacy-controlled recent-view storage.

## 9. Permissions

Public view. Catalog managers edit product copy/specifications; qualified content approvers publish planting guidance; pricing managers publish price; inventory roles affect availability only through stock services.

## 10. Backend contract

- View: `apps.products.views.product_detail`
- URL: `/products/<slug>/`, `products:product_detail`
- Method: `GET`; future branch selection may be query/session context
- Response: one published product read model, branch availability, related items and consent-aware recent items
- Validation: unknown/unpublished slug returns 404; only active prices/units and safe published guidance
- Services: future `ProductDetailService`, `BranchAvailabilityQueryService`, `RecommendationService`
- Side effects: none; optional recent-view event must be privacy controlled and cannot reserve stock

## 11. Future integrations

Inventory, branch selector, image gallery, recommendations, reviews display, SEO structured data and the later cart contract.

## 12. Acceptance criteria

Responsive summary, accessible image/status/landmarks, complete specifications and guidance, branch-specific states, related/recent sections, realistic data, no forbidden actions and documented backend boundary.
