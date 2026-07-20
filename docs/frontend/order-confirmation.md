# Order confirmation frontend specification

## Purpose

Order Confirmation gives guest and future account customers a durable customer-facing summary immediately after successful future order placement. Phase 2B renders realistic mock data only: no Order, Payment, receipt, notification, stock reservation or inventory movement exists.

## Displayed data

The page displays a thank-you message, mock order number `WTF-260716-1042`, order date/time, customer name, Home Delivery, M-Pesa, Payment Confirmed, estimated preparation/delivery guidance, Anna F1 Tomato and Hass Avocado lines, subtotal, mock delivery fee and estimated total. It never receives or renders operational branch, assigned staff, inventory, internal notes or routing.

## User actions

Track Order, Continue Shopping and call WayTop are active navigation/contact actions. Download Receipt is a disabled Coming Soon placeholder. Call and WhatsApp use the configured official number `+254 724 853 914`. Email remains disabled with “Official email coming soon”; a verified business email is required configuration before production. Enquiry messaging is also a disabled future action.

## States

Primary success is represented. Shared loading, offline, system-error and permission surfaces are reusable from the Order Tracking feature; confirmation should be recoverable through a future protected confirmation token. Receipt-unavailable is conveyed by a disabled action.

## Permissions

Future guest confirmation access requires an opaque, short-lived confirmation capability tied to the just-created Order. Authenticated customers require object ownership. An order number alone is not authorization. Staff-only fulfillment information is excluded from customer response serializers and context, not merely hidden with CSS.

## Future models and backend contract

Future models: `Order`, `OrderItem`, immutable `OrderContactSnapshot`, optional `DeliveryAddressSnapshot`, `OrderStatusEvent`, `Fulfillment`, `FulfillmentStatusEvent`, `Payment`, `PaymentStatusEvent`, `Receipt` and `Customer`. Operational `FulfillmentAssignment` relates internally to the fulfillment but is excluded from this customer projection.

Future `OrderConfirmationView` reads a server-authored projection after idempotent placement. Context includes customer-safe order identity/date, contact display, fulfillment method/window, payment method/status, item and price snapshots, totals and allowed customer actions. It must not include `branch_id`, branch name, assigned staff, inventory, internal notes or routing.

## Business rules

- Confirmation data comes from immutable accepted-order snapshots, never the mutable catalog/cart.
- Money uses Decimal and server-calculated totals.
- Customer-facing estimates are promises/windows with timezone-aware timestamps.
- Receipt becomes available only after governed accounting/payment rules permit it.
- Verified support email is a required business configuration before enabling Email.

## Definition of Done

Premium responsive confirmation, accessible headings/actions, complete customer-safe mock data, enabled Track/Shop/Call actions, disabled future receipt/email/enquiry actions, official phone only, no operational leakage, documented backend boundary and no backend mutations.
