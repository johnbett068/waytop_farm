# Wishlist to Cart workflow

## Objective

Let a public visitor move from product discovery to a considered Cart without authentication or backend mutation.

## Flow

Browse/Search/Product Detail → Save product → Wishlist counter updates → Open Wishlist → Review status → Move available item to Cart → Wishlist item is removed → Cart counter and mini-cart update → Review full Cart.

Unavailable products remain saved with a clear explanation and disabled Move action. Removing or clearing offers Undo. Offline mode preserves local actions but warns that availability cannot refresh.

## Future integrity boundary

The future backend must use stable ProductVariant identifiers, enforce Wishlist ownership, make duplicate saves idempotent, validate Cart sellability and never interpret a Wishlist/Cart action as inventory reservation.
