# Order lifecycle and customer tracking flow

> **Superseded for V1.** The active lifecycle is `PENDING -> CONFIRMED -> PROCESSING -> FULFILLED`, with authorized cancellation. See the [ratified V1 business contract](../architecture/v1-business-contract.md).

## Purpose and journey

Checkout acceptance → Order Confirmation → guest Track Order → customer activity timeline → Order Details → support.

Phase 2B is presentation only. Future services produce authoritative events and a customer-safe projection.

## Independent future state machines

### Order

`RECEIVED → PROCESSING → COMPLETED`, with `RECEIVED|PROCESSING → CANCELLED` under governed cancellation rules.

### Fulfillment

`AWAITING_ASSIGNMENT → PREPARING → READY_FOR_PICKUP → COLLECTED` for Farm Pickup, or `AWAITING_ASSIGNMENT → PREPARING → READY_FOR_DISPATCH → DELIVERED` for Home Delivery.

### Payment

`PENDING → CONFIRMED` or `PENDING → FAILED`. Governed reversals use `CONFIRMED → REFUND_PENDING → REFUNDED`. Refund is not a continuation of Failed Payment.

Each transition records previous/new state, reason code, actor/service, source channel, correlation/idempotency reference and timezone-aware timestamp. Transition permissions and invariants live in domain services, not views or JavaScript.

## Customer activity projection

The visible timeline selects public events from all three streams, orders them chronologically and maps them to completed/current/upcoming/problem presentation. It is not saved as a fourth status. Cash on Pickup can show Received → Preparing → Ready for Pickup → Payment Due at Pickup → Complete while `Payment.status` remains Pending until collection.

Cancelled, failed payment, refund pending and refunded events interrupt/annotate the projection without corrupting fulfillment history. Completed historical events remain visible for audit clarity.

## Guest tracking and states

Order Number + Phone → normalize → rate-limit → constant-shape lookup → customer-safe result or uniform Not Found. Expired token links return to credential entry. Offline blocks future lookup while preserving already rendered information. System Error does not imply an order problem.

## Permissions, data and support

Guests can view only the order matching both credentials or a valid capability. Account customers later use ownership. Customer data includes snapshots, public event descriptions and estimates. Branch assignment, staff, inventory, internal notes and routing are excluded at query/serializer level. Call/WhatsApp use `+254 724 853 914`; Email remains disabled until official configuration exists.

## Definition of Done

Independent lifecycle specification, customer projection rules, guest/privacy states, Cash on Pickup path, cancellation/refund behavior, audit metadata, support boundary and explicit exclusion of operational information.
