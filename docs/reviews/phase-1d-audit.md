# Phase 1D Order and Payment persistence review

Status: **complete - PENDING persistence boundary only**
Reviewed: 15 August 2026

## Implemented

- One Order aggregate for Ecommerce and POS with UUID identity, random public number, global creation idempotency, channel, fulfillment method, required date, KES total and PENDING lifecycle.
- Protected optional Customer association and immutable one-to-one contact/address snapshots.
- Order Lines with protected Catalog references, immutable product/unit/price facts, integer Sale Unit quantities, READY/PRE_ORDER modes and zero confirmed/outstanding quantities while PENDING.
- One full PENDING M-Pesa Payment per Order with immutable evidence, rejected verification-attempt history and Payment status history.
- Explicit transactional Order creation, Payment evidence submission and rejected-verification services.
- Native `orders.view`, `orders.cancel`, `pos.process_sale` and `payments.verify` permissions without permanent role-name checks.
- Kenyan E.164 Customer phone normalization and lowercase email normalization; both remain optional and non-unique.
- Read-only admin projections. Raw M-Pesa messages are excluded from admin, searches, string representations, public routes and logs.
- Raw M-Pesa messages are encrypted before database persistence with Fernet. Development/test may derive a key from `SECRET_KEY`; production deployment checks require explicitly configured rotatable `PAYMENT_EVIDENCE_ENCRYPTION_KEYS`.

## Deliberately unavailable

Payment approval/confirmation, Order confirmation, entry into PROCESSING, cancellation, fulfillment, Availability, Commitment, Inventory, Production, delivery logistics, tracking, returns, refunds, discounts, taxes and promotions remain unavailable.

Only initial PENDING Order/Payment events and rejected Payment verification attempts can be created. Direct approved attempts, confirmed events, nonzero commitment quantities, mutable PENDING commercial facts and destructive admin actions are rejected.

## Privacy boundary

Payment-evidence retention duration remains deferred. No expiry or automatic deletion rule was invented. Production must configure explicit encryption keys and a later ratified retention policy before handling live evidence.

## Verification

- Focused Customer/Order/Payment tests: 48 passed.
- Accounts/Customer/Catalog/Order/Payment cross-domain tests: 94 passed.
- Full Django suite: 111 passed.
- Django system check: passed with no issues.
- Migration drift check: no changes detected.
- Fresh isolated test database applied all Accounts, Customer, Product, Order and Payment migrations successfully.
- The development `db.sqlite3` was not migrated.

## Next phase

Implement Availability and Commitment persistence and then the complete atomic `VerifyPaymentAndConfirmOrder` operation. Do not expose confirmation before that transaction can lock and update Payment, Order, supply commitments and allocations together.
