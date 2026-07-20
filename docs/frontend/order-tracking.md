# Guest order tracking frontend specification

## Purpose

Order Tracking lets a guest follow an accepted order with Order Number plus Phone Number. The same result components are reusable inside future Customer Accounts without changing the customer projection.

## Displayed data

Tracking displays customer-safe order header, status badge, composed activity timeline, customer/contact details, delivery address or pickup method, customer notes, product quantity/unit/price snapshots, subtotal, delivery fee, total, payment method/status and estimated completion/window. It excludes operational location, staff, inventory, routing and internal notes.

## User actions and validation

Customers enter both an order number matching `WTF-YYMMDD-NNNN` presentation and a Kenyan `+254` phone number. Validation is inline and summarized in a focusable error region. Mock lookup succeeds only for `WTF-260716-1042` with `+254 724 853 914`; this is frontend demonstration, not authorization logic. Customers may retry, call, open WhatsApp, or see disabled Email/enquiry actions.

## States

Loading, offline (global banner), empty/instructional, validation error, order not found, expired link, system error, reusable permission denial and success are implemented. Problem/refund/cancelled timeline and badge appearances are represented as reusable status variants.

## Permissions

Guest lookup requires the order reference and normalized phone match, plus production rate limiting and abuse protection. Responses should be non-enumerable and avoid revealing which credential failed. Future account access uses object ownership but consumes the same `CustomerOrderTrackingProjection`. Staff permissions and staff fields are outside this contract.

## Future models and backend contract

Models: `Order`, `OrderItem`, contact/address snapshots, `OrderStatusEvent`, `Fulfillment`, `FulfillmentStatusEvent`, `Payment`, `PaymentStatusEvent`, `CustomerCommunication` and optional `TrackingAccessGrant`. Relationships and lifecycle separation are detailed in the lifecycle/contract documents.

Future views: `GuestOrderTrackingView` GET form and POST lookup, tokenized `GuestTrackingLinkView`, and an account-owned tracking view reusing the result component. Context contains only the customer-safe projection, public timeline events, allowed actions and support configuration.

## Business rules

- Order, fulfillment and payment state machines remain independent.
- The visible activity timeline is a read projection, never a stored generic status.
- Phone values are normalized to E.164 before comparison and never logged in full.
- Tracking lookup is rate-limited, audited and returns uniform not-found behavior.
- Official email is required configuration before Email is enabled.

## Definition of Done

Guest form, all required states, composed timeline, details/totals/support, keyboard and focus behavior, responsive layouts, status variants, no operational fields, documented independent lifecycles and no backend implementation.
