# WayTop Farm V1 Order, Customer and Payment Contract

Status: **Ratified**
Effective: Phase 1D
Scope: Order, Customer snapshot, Payment and the minimum completion boundary
Authority: Once ratified, this document refines the [V1 business contract](v1-business-contract.md) for implementation. The V1 business contract continues to prevail outside this document's scope.

The rules inherited from the ratified V1 contract and the Phase 1D ratification gate are binding. This document is the implementation authority for the PENDING Order and Payment persistence foundation.

## 1. Purpose and scope

This contract defines one implementation-ready commercial foundation for Ecommerce and Point of Sale. It preserves historical customer, product, unit and price facts while keeping Payment, Inventory, Production, Commitment and Fulfillment ownership distinct.

This contract does not authorize implementation. Phase 1D contract finalization creates documentation only.

## 2. Customer contract

`customers.Customer` is a mutable business profile. It remains separate from `accounts.User`, which is a staff authentication identity.

- `display_name` is required.
- `phone` and `email` are optional and non-unique.
- A Customer can be active or inactive. New Orders must not attach an inactive Customer, but deactivation never alters historical Orders.
- Order-to-Customer deletion behavior is `PROTECT`. Ordinary administration must deactivate Customers instead of deleting them.
- Customer has no direct relationship to User, Branch, Product, Inventory, Production, Payment or Fulfillment.
- Anonymous POS walk-ins use a null Customer reference. The system must not create a placeholder Customer.

### Ratified V1 normalization and matching policy

1. When present, `Customer.phone` is stored in canonical E.164 form. V1 accepts Kenyan numbers only and uses a maintained phone-number library with Kenya as the explicit default region. Invalid or ambiguous numbers are rejected rather than guessed.
2. When present, `Customer.email` is trimmed and lowercased after structural validation. It remains non-unique.
3. Phone and email are contact attributes, not identity or authorization credentials by themselves.
4. Duplicate Customers are never automatically merged. Exact normalized phone/email matches may produce staff search candidates; an authorized staff user must select the intended Customer. Multiple matches remain multiple candidates.
5. POS staff with `customers.view` may search and select an active Customer. Creating or editing one requires `customers.manage`.
6. V1 Ecommerce is guest-capable. Checkout neither creates a Customer automatically nor attaches one by matching phone or email. A future authenticated customer capability may add explicit ownership without changing Order snapshots.
7. Ecommerce requires display name and valid Kenyan E.164 phone; email is optional.
8. POS collection of a READY-only Order may be anonymous. POS PRE_ORDER or HOME_DELIVERY Orders require display name and valid Kenyan E.164 phone. Email remains optional.

These policies require the existing Customer validation/tests to be aligned before Order implementation. Existing stored data, if any, must be audited; a migration must not guess how to normalize invalid values.

## 3. Customer and address snapshot contract

Every Order owns exactly one immutable `OrderContactSnapshot`. It contains only:

- `display_name` — blank only for an anonymous, READY-only POS collection;
- `phone_e164` — blank only where the channel rules above permit anonymous contact;
- `email` — optional, normalized lowercase.

`Order.customer` is a nullable `PROTECT` reference. The contact snapshot is copied from the selected active Customer or from validated guest input at Order creation. Later Customer changes never update it. Tracking and historical displays read the snapshot, not the current Customer.

Order has a customer-facing `fulfillment_method` of `HOME_DELIVERY` or `CUSTOMER_COLLECTION`. This is not an internal Branch selection or a detailed Delivery workflow.

A HOME_DELIVERY Order owns exactly one immutable `OrderAddressSnapshot` containing:

- `county`;
- `town_or_area`;
- `address_line`;
- optional `delivery_instructions`.

These values are copied from a selected active `CustomerAddress` or validated checkout input. The snapshot does not copy `label`, `is_default`, `is_active`, a Branch, or a source-address foreign key. CUSTOMER_COLLECTION Orders must not have an address snapshot. The collection arrangement must not expose an internal Branch through the customer Order.

Snapshots are append-never/edit-never facts. Corrections require an explicit audited business operation defined by a later contract; direct CRUD is prohibited.

## 4. Order contract

One `Order` aggregate serves both channels. Its minimum persistent facts are:

- internal UUID primary key;
- unique public `order_number`;
- nullable `customer` reference;
- immutable contact snapshot and conditional address snapshot;
- `channel`;
- `fulfillment_method`;
- nullable `required_date`, required when any line is PRE_ORDER;
- lifecycle `status`;
- `currency`, fixed to KES in V1;
- immutable calculated `total_amount`;
- a unique creation idempotency key;
- timezone-aware created and updated timestamps.

An Order is created only through an idempotent service and starts `PENDING`. Creation does not create stock, a commitment, an allocation or a confirmed payment. Order lines and their commercial snapshots are immutable after creation. A changed request is a new Order; V1 does not introduce a hidden generic status mutation or a pending-cancellation path.

Direct deletion of Orders is prohibited. Direct editing of lifecycle, snapshots, totals and confirmation quantities is prohibited in models, admin, views and APIs.

## 5. Order line contract

An Order has one or more ordered `OrderLine` records. Each line contains:

- UUID identity and positive line number unique within the Order;
- `Product` reference with `PROTECT` deletion behavior;
- `ProductSaleUnit` reference with `PROTECT` deletion behavior;
- source `ProductPrice` reference with `PROTECT` deletion behavior;
- immutable SKU and product-name snapshots;
- immutable sale-unit name and `base_quantity` snapshots;
- positive integer `quantity`, representing a count of sale units;
- KES `unit_price` snapshot;
- immutable calculated `line_total`;
- `supply_mode`: `READY` or `PRE_ORDER`;
- non-negative integer `confirmed_quantity`;
- non-negative integer `outstanding_quantity`.

V1 does not allow fractional counts of sale units or fractional seedlings on an Order Line. A tray remains one sale unit whose snapshotted `base_quantity` describes how many base inventory units it represents.

The quantity invariant is:

`0 <= outstanding_quantity <= confirmed_quantity <= quantity`

While an Order is PENDING, both confirmation quantities are zero. In the successful atomic confirmation operation, the entire requested quantity is confirmed and both become `quantity`. V1 has no partial Order confirmation. Later fulfillment reduces outstanding quantity only through the Commitment/Fulfillment boundary; shortages never silently reduce confirmed quantity.

## 6. Order channel contract

`Order.channel` has exactly:

- `ECOMMERCE`
- `POS`

Channel records origin only. It does not select a different Order model, lifecycle, payment gate, availability rule, commitment rule or fulfillment workflow.

## 7. READY and PRE_ORDER contract

A single Order may mix READY and PRE_ORDER lines.

- READY identifies demand intended for current saleable physical stock.
- PRE_ORDER identifies demand intended for future Production capacity.
- Neither mode creates availability, allocation or commitment when the PENDING Order is created.
- PRE_ORDER never creates negative physical Inventory.
- A PRE_ORDER line requires the Order's `required_date`.
- Internal location allocation is neither stored on public Order fields nor exposed to customers.

Availability and commitment models are prerequisites for confirmation and belong to later implementation.

## 8. Payment contract

V1 uses one full Payment aggregate per Order, with multiple evidence submissions and verification attempts retained as history. Split, partial and multiple confirmed payments are outside V1.

The Payment contains:

- UUID identity;
- one-to-one Order relationship;
- immutable expected `amount`, equal to the Order total;
- `currency`, fixed to KES;
- `method`, fixed to `MPESA` for both current channels;
- `state`: `PENDING` or `CONFIRMED`;
- nullable canonical provider reference, populated only on successful confirmation;
- nullable `verified_by` reference to an active staff User, with `PROTECT` deletion behavior;
- nullable timezone-aware `verified_at`;
- created and updated timestamps.

Payment is created PENDING with the Order. Selecting M-Pesa or submitting evidence is not confirmation. `verified_by`, `verified_at` and provider reference must all be null while PENDING and all be present while CONFIRMED.

The canonical provider reference is trimmed and uppercased. A database uniqueness constraint on `(method, provider_reference)` when the reference is present prevents a confirmed M-Pesa reference from being reused across Orders.

## 9. Payment evidence contract

`PaymentEvidence` is append-only and belongs to one Payment. It contains:

- UUID identity;
- optional customer-submitted reference claim;
- optional customer-submitted M-Pesa message;
- submission source (`ECOMMERCE`, `POS` or authorized staff entry);
- server-generated submission timestamp.

At least one of reference claim or message is required. Evidence is untrusted input, is never interpreted as confirmation, and cannot be edited into a different submission. V1 does not store an M-Pesa PIN or request one.

Evidence may repeat a claim already submitted. Uniqueness applies to the canonical provider reference accepted on a confirmed Payment, not to unverified customer text.

## 10. Payment verification contract

Payment verification requires an authenticated active staff User with the ratified canonical capability `payments.verify`. Staff status, superuser convenience, role name and UI visibility are not substitutes for the capability decision.

Each attempt creates append-only verification audit data containing Payment, selected evidence, actor, server timestamp, outcome, reason and correlation/idempotency identity. A rejected or failed attempt leaves Payment and Order PENDING. An approved attempt may be committed only inside `VerifyPaymentAndConfirmOrder`; it cannot be saved as a standalone confirmation.

Successful verification creates a Payment status event from PENDING to CONFIRMED. Failed business commands are recorded by the audit boundary after the rolled-back domain transaction without fabricating a Payment status transition.

The `payments.verify` capability is part of the canonical permission catalogue and must be assigned through reviewed role/group configuration before this service is enabled.

## 11. Order lifecycle

The only forward path is:

`PENDING -> CONFIRMED -> PROCESSING -> FULFILLED`

The only exception transitions are:

`CONFIRMED -> CANCELLED`
`PROCESSING -> CANCELLED`

There is no `PENDING -> CANCELLED` transition. There are no Received, New, Accepted, Completed or Delivered Order states. Payment, Commitment and Fulfillment states are not encoded as additional Order states.

Phase 1F decision F02 supersedes the earlier same-command transition described in the original
Phase 1D text: atomic confirmation appends `PENDING -> CONFIRMED` and ends at CONFIRMED.
`CONFIRMED -> PROCESSING` remains a separate later operation and no generic
`order.status = ...` command is exposed. Phase 1G-Final ratifies the explicit
`start_order_processing()` command for authenticated active staff with `orders.process`. It
requires a confirmed Payment and structurally valid READY-only Commitment, Reservation and
Allocation facts; it changes only Order status and appends its immutable lifecycle event.

## 12. Cancellation rules

Cancellation requires `orders.cancel`, an authenticated active staff actor and a non-empty reason. It is permitted only from CONFIRMED or PROCESSING.

The cancellation operation must atomically release every remaining READY/PRE_ORDER commitment according to the Commitment domain, move the Order to CANCELLED and append its status/audit event. It must not rewrite ordered, confirmed or historically fulfilled quantities. Because Commitment does not yet exist, cancellation must not be implemented in the Order foundation phase.

Payment remains a truthful confirmed receipt after Order cancellation. Refund processing and refund states are outside V1 and must not be simulated.

## 13. Fulfillment rules

V1 does not model drivers, routes, dispatch, courier tracking or detailed Delivery jobs.

A minimal `FulfillmentCompletion` records one Order, the completing staff User, server timestamp and optional note/reference. Creating it and moving PROCESSING to FULFILLED is one authorized transaction and proves that outstanding quantity is zero. The record is immutable and one-to-one with Order.

The minimum completion capability is `fulfillment.complete`. It is listed in the canonical
permission catalogue and must be assigned through reviewed role/group configuration. Phase 1G
implements the minimal completion model/service; reaching PROCESSING uses the separately
authorized command described above.

## 14. POS rules

- POS creates the same Order and Payment aggregates as Ecommerce.
- POS may create READY, PRE_ORDER or mixed Orders.
- Anonymous READY-only collection uses null Customer and blank contact snapshot fields; the UI may display “Walk-in customer” as presentation text but must not persist that phrase as an identity.
- PRE_ORDER and HOME_DELIVERY require the contact/address facts defined above.
- POS may search and attach an active Customer only through authorized Customer search.
- V1 does not define cash, card, register settlement, parked sales, separate POS transactions or a POS-specific state machine.
- An M-Pesa POS Order crosses the same atomic confirmation boundary as Ecommerce.

## 15. Ecommerce rules

- Guest Ecommerce ordering is allowed and does not automatically create or match a Customer.
- Checkout requires display name, valid Kenyan E.164 phone, fulfillment method and the conditional address; email is optional.
- Client-supplied prices, totals, availability, payment state, Customer identity and Branch/location values are rejected or ignored.
- Server-side Order creation reselects the effective ProductPrice and copies all snapshots in one idempotent transaction.
- Checkout creates only a PENDING Order, its lines and PENDING Payment. It may then accept append-only M-Pesa evidence.
- Customer tracking authorization is a later security contract. If phone is used, comparison is against the Order snapshot and requires rate limiting and non-enumerable responses; an order number alone is never authorization.

## 16. Customer-facing visibility rules

Customer projections may expose only public Order number, creation time, contact/address snapshots, fulfillment method, required date, product/unit/price snapshots, quantities, totals, Order status, safe Payment status, and approved public events.

They must not expose internal Branches, stock locations, allocations, Inventory records, Production details, staff identities, verification notes, internal audit reasons or provider evidence text.

## 17. Order number contract

The public format is `WTF-XXXX-XXXX-XXXX`, where each `X` is an uppercase character from an ambiguity-free Crockford Base32 alphabet. The 12 characters are generated with a cryptographically secure random generator independently of the UUID, date and database sequence.

The canonical value is uppercase, immutable and database-unique. Creation retries on the extremely unlikely uniqueness collision. The format is shared by Ecommerce and POS, does not encode channel or time, and is safe to display but is not an authorization secret.

## 18. Audit and event contract

`OrderStatusEvent` is append-only and records:

- Order;
- nullable previous state for the initial PENDING event;
- new state;
- nullable staff actor only for system/guest creation, otherwise required;
- server-generated timezone-aware timestamp;
- optional reason/note, required for cancellation;
- correlation and idempotency identity.

`PaymentStatusEvent` records the corresponding Payment transition. Payment evidence and verification-attempt records provide the remaining Payment history. Events cannot be edited or deleted through ordinary application or admin paths. Corrections append new governed evidence/events; they never rewrite history.

Timestamps are stored timezone-aware. Africa/Nairobi is the business display timezone, not a reason to store naive local time.

## 19. Transaction boundary

`VerifyPaymentAndConfirmOrder` is not implementable until Availability and Commitment persistence exist. When implemented, one database transaction must:

1. authorize `payments.verify` and validate the idempotency key;
2. lock Payment and Order;
3. ensure both remain PENDING and their amount/currency agree;
4. validate selected evidence and canonical provider reference uniqueness;
5. lock and revalidate READY availability and PRE_ORDER capacity;
6. create complete commitments and approved internal allocations;
7. set every line's confirmed and outstanding quantities to its ordered quantity;
8. confirm Payment and append its status/verification events;
9. move Order from PENDING to CONFIRMED and append that event (Phase 1F decision F02 supersedes the
   original same-command PROCESSING step);
10. commit all facts together.

Any failure rolls back every domain change. Availability failure leaves Payment and Order PENDING, line confirmation quantities at zero and no commitment. A separate failure-audit write may record the rejected command after rollback; it must not claim a domain transition occurred.

## 20. Cross-domain ownership

- Customer owns mutable profiles and reusable addresses.
- Catalog owns Product, ProductSaleUnit and ProductPrice; Order owns accepted snapshots.
- Order owns the commercial request, public number, lines, snapshots, required date and Order events.
- Payment owns evidence, verification attempts, provider reference, Payment state and Payment events.
- Inventory owns physical stock, location, movement and physical availability.
- Production owns forecasts and future production capacity facts.
- Order owns the customer's confirmed and outstanding quantities. The later Commitment boundary owns the READY/PRE_ORDER supply commitments, FIFO priority and release records that support those quantities; it may not silently rewrite the commercial commitment.
- Fulfillment owns the minimal completion fact; it does not create detailed Delivery logistics.
- Authorization decides capability; owning domain services still enforce business invariants.

No domain directly edits another domain's lifecycle or mutable internals.

## 21. Database-level requirements

The eventual schema must enforce wherever supported:

- UUID primary keys and unique public Order number;
- unique creation idempotency key;
- at least one Order Line and unique positive line number per Order (the count is enforced transactionally; line uniqueness is a database constraint);
- `PROTECT` for Customer, Product, ProductSaleUnit, ProductPrice and staff actor relationships that preserve history;
- positive integer ordered quantity;
- `0 <= outstanding <= confirmed <= ordered` checks;
- non-negative unit price/line/Order/Payment amounts and KES-only currency checks;
- calculated `line_total = quantity * unit_price` and `order total = sum(line totals)` revalidation in the write service;
- one Payment and one contact snapshot per Order;
- conditional address presence enforced by service and database constraints where the chosen table shape permits;
- required-date validation for PRE_ORDER through the aggregate service;
- all-or-none confirmed Payment metadata;
- conditional uniqueness of canonical `(method, provider_reference)`;
- at least one evidence input;
- immutable event/evidence records and deletion-disabled admin behavior.

Unit price snapshots use `Decimal(12,2)`. Line totals, Order totals and Payment amounts use `Decimal(18,2)`. ProductSaleUnit base-quantity snapshots use `Decimal(12,3)`. All money is KES and quantized to `0.01` using `ROUND_HALF_UP`; floating point is forbidden.

V1 rejects zero-total Orders. The Catalog may retain a zero configured ProductPrice, but such a price is not orderable until a separately ratified free-order policy exists. Taxes, discounts, delivery fees and promotions are absent; Order total is exactly the sum of line totals.

## 22. Service-level invariants

Application services must:

- normalize/validate contact input before lookup or persistence;
- never auto-merge or auto-identify a Customer from shared contact data;
- select an active Product, Sale Unit and effective ProductPrice server-side;
- verify that each Sale Unit and ProductPrice belongs to the selected Product chain;
- calculate immutable snapshots and totals with Decimal arithmetic;
- create Order, lines, snapshots, initial events and Payment atomically and idempotently;
- reject direct lifecycle, total, price-snapshot and confirmation-quantity mutation;
- authorize commands by capability rather than role name;
- lock mutable aggregates and recheck state inside every consequential transaction;
- expose no confirmation, cancellation or fulfillment command before its prerequisites exist;
- return existing results for safe idempotent retries and reject key reuse with different input.

## 23. Explicitly out of scope

V1 excludes Pay on Delivery, Cash on Pickup, cash/card POS settlement, split/partial payments, automatic M-Pesa integration, refunds, returns, voids, detailed Delivery, drivers, routes, dispatch, customer Branch selection, Inventory or Production mutation from Order code, deep Procurement, tax/discount/promotion engines, customer accounts, automatic Customer creation/matching, and a generic event-sourcing framework.

No demo Order, Customer, Payment, stock, count, total or provider reference may enter normal runtime.

## 24. Ratification decisions and deferred retention policy

The Phase 1D ratification gate approved the following schema and validation decisions:

1. Kenyan E.164 phone storage and lowercase email storage in the existing Customer fields.
2. No automatic Customer creation, attachment, merge or match; guest Ecommerce remains allowed.
3. Exact channel contact requirements, including anonymous READY-only POS collection.
4. `HOME_DELIVERY | CUSTOMER_COLLECTION` as the minimal fulfillment-method enum and conditional address snapshot.
5. Integer sale-unit counts; the line's sale-unit base quantity preserves tray/seedling conversion.
6. One full M-Pesa Payment per Order with multiple immutable evidence/verification-history records; no split payments.
7. `payments.verify` and later `fulfillment.complete` as canonical capabilities.
8. Random public number format `WTF-XXXX-XXXX-XXXX`.
9. Decimal precision/rounding and rejection of zero-total Orders.

Payment-evidence retention duration remains deliberately deferred. Until a business retention policy is ratified, implementation must restrict evidence access, encrypt raw messages at rest, keep raw messages out of logs and public/customer responses, and avoid automatic deletion or an invented retention deadline.

The unresolved Production partial-release costing policy is unrelated and remains governed by the V1 business contract. Pending-Order expiry/abandonment remains an operational policy to define before production and does not introduce another Order lifecycle state in this phase.

## 25. Implementation prerequisites and exact next phase

This document authorizes **Phase 1D Order + Payment Persistence Foundation**:

1. align Customer normalization and tests;
2. add Order, OrderLine, contact/address snapshots and OrderStatusEvent;
3. add Payment, PaymentEvidence, verification-history and PaymentStatusEvent;
4. add database constraints, immutable admin surfaces and creation/evidence services;
5. keep Orders and Payments PENDING only;
6. do not implement payment confirmation, commitment, cancellation or fulfillment transitions;
7. preserve all existing honest empty runtime states;
8. verify fresh migrations, drift, system checks, focused tests and the full regression suite.

`VerifyPaymentAndConfirmOrder` belongs to the later Commitment + Availability implementation and must remain unavailable until its complete atomic transaction can be built.
