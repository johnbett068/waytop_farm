# Product discovery flow

## Objective

Describe how a public visitor moves from awareness to an informed product choice. Phase 1C extends the flow into a device-local Wishlist and Cart without reservation, order or sale.

```text
Homepage → Shop → Category → Product Detail → Search → Filter → Prepare for Cart
```

## Actors and preconditions

- Public visitor; authentication is not required.
- Published mock catalog is available.
- Connectivity is required for initial page delivery; the global offline state handles later connection loss.

## Main flow

1. **Homepage:** visitor selects Explore Seedlings, a featured category or a featured product.
2. **Shop:** visitor scans the complete product range and sees price with unit and stock status.
3. **Category:** visitor narrows intent to vegetables, fruit, trees or another published crop group.
4. **Product Detail:** visitor reviews variety, description, price/unit, specifications, planting period, growing duration, planting guide and branch availability.
5. **Search:** visitor searches by crop or variety when navigation is insufficient.
6. **Filter:** visitor combines category, stock status and maximum price; then sorts and pages through matching products.
7. **Prepare for Cart:** visitor reaches an informed choice, selects an eligible branch and may save the product or add it to the Phase 1C local Cart.

## Alternate flows

- A query with no matches shows a constructive empty result and suggests removing filters or changing terms.
- A valid empty category explains seasonal catalog changes.
- Pre-order, low-stock and unavailable products remain visible with explicit status.
- Branches can disagree on availability without changing the product's catalog identity.
- Loading uses product skeletons; a result failure uses the shared error state.
- Unknown product/category slugs return the branded 404 page.
- Offline status appears globally without claiming cached inventory accuracy.

## Business integrity boundary

- Discovery requests are read-only.
- Stock display is a future branch projection; it never deducts, reserves or guarantees stock.
- Prices are Decimal-compatible and always paired with a unit.
- Planting guidance requires content approval and context disclaimers.
- Recently viewed behavior requires privacy controls before persistence.
- Cart consumes stable mock product, price, unit and branch identifiers in Phase 1C; the future backend must revalidate price and availability.

## Future backend services

`CatalogSearchService`, `CategoryCatalogService`, `ProductDetailService`, `BranchAvailabilityQueryService`, `RecommendationService` and a consent-aware recent-view service.

## Completion point

The Phase 1C extension permits local quantity and branch selection. No reservation, authentication, Checkout, payment, order or inventory movement occurs.
