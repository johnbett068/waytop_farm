# Wishlist specification

## 1. Purpose

The Wishlist lets a public visitor retain a device-local shortlist of WayTop products, compare availability and move eligible products into the Cart. It supports planning without requiring an account.

## 2. Target users

- Public and returning visitors
- Farmers, institutions, landscapers and home growers
- Guest customers; authentication is not part of Phase 1C

## 3. Business rules

- A product appears at most once in a Wishlist.
- Any catalog product, including an unavailable product, may be saved.
- An unavailable product cannot be moved to Cart.
- Moving an item to Cart removes it from Wishlist only after the local Cart update succeeds.
- Clearing or removing is reversible through the time-limited Undo action.
- Phase 1C state belongs to one browser profile and is not synchronized to a customer account.
- Wishlist actions never reserve stock, change inventory or create an order.

## 4. Displayed data

Product slug/SKU, name, variety, category, image, price in KES, unit of sale, stock label, primary branch summary and product-detail URL. The counter is the number of unique saved products.

## 5. User actions

- Save/remove from homepage products, catalog cards, related/recent cards and Product Detail.
- Open Wishlist from desktop or mobile navigation.
- View Product Detail.
- Move an available item to Cart.
- Clear Wishlist and Undo removal/clear.
- Retry a simulated loading error or continue browsing from an empty state.

## 6. Page states

- Loading skeleton (`?state=loading` keeps the specification state visible)
- Empty Wishlist with catalog recovery action
- Success with responsive product cards
- Simulated server/error contract (`?state=error`)
- Offline notice while local actions remain available
- Unavailable product retained with Move to Cart disabled
- Storage unavailable: in-memory session fallback and notification
- Permission denied is not applicable to a public device-local Wishlist; the global 403 remains available for the future account-backed route

## 7. Reusable components

Global product heart, animated counter, toast/Undo, product identity, commerce state service, error/loading/empty surfaces, navbar and mini-cart.

## 8. Future models

`Customer`, `Wishlist`, `WishlistItem`, `Product`, `ProductVariant`, `Branch`, `BranchStock`. `WishlistItem` requires a uniqueness constraint on Wishlist and ProductVariant and immutable created timestamps.

## 9. Permissions

Anyone may use the local Wishlist. In the future, authenticated customers may view and modify only their own Wishlist. Staff do not edit customer wishlists. Catalog and stock permissions remain separate.

## 10. Backend contract

- Phase 1C view: `apps.wishlist.views.wishlist`, `GET /wishlist/`, template only, no mutation.
- Future reads: `GET /api/customer/wishlist/`.
- Future mutations: idempotent add and delete commands using stable variant identifiers.
- Validation: product is active/web-visible; duplicate additions are idempotent; ownership is enforced server-side.
- Future `WishlistService` owns persistence. It has no inventory side effects.

## 11. Future integrations

Authentication, cross-device synchronization, customer recommendations, stock alerts, analytics with consent and Cart hand-off.

## 12. Acceptance criteria

Responsive, keyboard accessible, screen-reader-labelled, token-based, realistic catalog data, save/remove everywhere, animated counter, Move to Cart, clear/Undo and all applicable states. No API, model, authentication or inventory mutation exists in Phase 1C.
