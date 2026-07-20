# Homepage discovery and enquiry flow

## Purpose

Describe how a public visitor discovers WayTop Farm, evaluates the nursery offering, saves featured products, opens Product Detail or starts a local Cart.

## Actors

- Visitor or prospective customer
- WayTop Farm nursery team (outside the application in Phase 1A)

## Preconditions

- None; the homepage is public.
- A device needs telephone capability to initiate a call directly.

## Main flow

1. Visitor opens `/`.
2. The page establishes the business identity, location and core value proposition.
3. Visitor reviews trust information, seedling categories and curated products.
4. Visitor reviews the product's unit, price and branch availability message.
5. Visitor opens a product detail page or uses a general telephone call-to-action.
6. Visitor contacts the nursery to confirm current quantity and the preferred branch or collection point.
7. Nursery staff coordinate collection or delivery outside the ecommerce checkout flow.

## Alternate and failure flows

- Empty category or product collections show contextual guidance rather than a blank section.
- Limited availability is shown on the affected product.
- If connectivity is lost, a global offline banner explains that some information or actions may be unavailable.
- An unknown URL shows the branded 404 page with a safe return action.
- A server failure shows a branded recovery state.
- A visitor without telephone support can read the displayed number and use another phone.

## Backend implications

- Homepage reads must be side-effect free.
- Future inventory availability is a branch-specific read projection, not a direct inventory mutation.
- Product-detail and telephone analytics must not imply an order or stock reservation.
- Certification, customer-volume and testimonial claims require an approval and evidence policy before production use. Unsupported mock social proof is not rendered.
- Category image fields will map to future media records with responsive derivatives and approved alternative text.

## Phase boundary

Phase 1C allows Wishlist and Cart planning from featured products. The flow still stops before Checkout: stock is not reserved and no order is created from the homepage.
