# Future order tracking backend contract

> **Superseded for V1.** Retained for historical UI context. See the [ratified V1 business contract](../architecture/v1-business-contract.md).

## Purpose

Define the future customer-safe confirmation and tracking read contract. Phase 2B implements no API, model, query or business transition.

## Future models and relationships

- `Order` has many immutable `OrderItem` snapshots and many `OrderStatusEvent` records.
- `Order` owns one contact snapshot and zero/one delivery-address snapshot.
- `Order` has one/many `Fulfillment` records; each has many `FulfillmentStatusEvent` records.
- `Order` has one/many `Payment` attempts; each has many `PaymentStatusEvent` records.
- Internal `FulfillmentAssignment` references a fulfillment, operational branch and possibly staff actor. It is never joined into the customer projection.
- `CustomerCommunication` records permitted notifications independently of state changes.
- Optional `TrackingAccessGrant` stores hashed, expiring capability metadata—not raw tokens.

## Views and future APIs

- `GET /orders/confirmation/<opaque-token>/`: customer-safe confirmation.
- `GET|POST /orders/track/`: guest form and credential lookup.
- `GET /orders/track/<opaque-token>/`: expiring link projection.
- Future account endpoint reuses the projection behind authenticated object ownership.

POST lookup request: `{order_number, phone_e164}` plus CSRF for server-rendered forms. Normalize phone to E.164. Never accept lifecycle status, branch, staff, totals or ownership claims from the client.

Success context/API projection: public order reference/date, customer display/contact, fulfillment method/public estimate, payment method/public status, product snapshots, Decimal totals, customer notes, public activity events, allowed actions and support configuration. Forbidden keys include `branch`, `branch_id`, `assigned_branch`, `assigned_staff`, stock/inventory records, internal notes and routing.

## Validation, permissions and privacy

Order references use a non-sequential public identifier. Both reference and phone must match. Apply IP/device/account-aware throttling, uniform error copy/status timing, monitoring and lockout escalation. Mask phone/email in logs and analytics. Account access requires ownership. Staff operational access uses separate serializers/views/permissions.

## Lifecycle and audit rules

Order, fulfillment and payment enums and event streams are independent. Domain services validate transitions transactionally and append immutable audit events. The customer timeline composer consumes only events marked public, maps copy through governed templates and never exposes actor/staff/branch metadata. Estimates are projections and changes create public update events when customer-relevant.

## Support configuration

Required production configuration includes canonical phone/E.164 WhatsApp number and verified official support email. Phase 2B has phone/WhatsApp `+254 724 853 914`; email is intentionally null and the UI stays disabled with Coming Soon. Deployment validation must prevent enabling Email without a verified address.

## States and errors

Contracts support loading client state, empty form, field/non-field validation, uniform not found, expired capability, rate-limited/permission denial, system error and success. Offline is client/network state. A tracking-system error must not change or imply Order status.

## Definition of Done

Models/relationships, views/APIs, customer projection allowlist, operational denylist, validation, permissions, throttling, privacy, independent lifecycle/audit requirements and support configuration are documented without backend implementation.
