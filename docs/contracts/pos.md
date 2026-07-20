# POS frontend contract

## Projection inputs

Future POS reads must be projections, not shared mutable domain objects:

- `catalog_projection`: product code, display name, image, unit and authoritative sale-price projection.
- `availability_projection`: Inventory item/location, available-to-sell quantity, condition, freshness timestamp and version.
- `customer_projection`: customer reference, display details and future loyalty summary.
- `register_projection`: register/session reference, cashier reference, status and summarized tender state.
- `transaction_projection`: reference, customer, cashier, status, payment-method display, total and correlation identifier.

Stale or unavailable projections must produce an explicit offline/error state. The client must never infer stock from Production WIP, Procurement deliveries or a locally cached cart.

## Future command boundaries

Phase 4A emits no command. A later approved backend may define separately authorized commands such as:

- open/close register;
- create or park a sale;
- validate price and availability;
- record tender outcome;
- complete/void/return a sale;
- request/approve exceptional action;
- request an Inventory issue;
- project a receipt.

Every command needs an actor, capability, branch/register scope, correlation ID, idempotency key, expected version and immutable outcome. Partial failure must remain visible and retryable; one domain must not impersonate another.

## Capabilities

The UI recognizes canonical capability strings including `pos.view`, `pos.open_register`, `pos.process_sale`, `pos.close_register`, `pos.request_refund`, `pos.approve_refund`, `pos.issue_refund`, `pos.request_void`, `pos.approve_void`, `pos.void_sale` and `pos.view_reconciliation`.

Cashier and Operations examples are expressed only as capability arrays. Administrator configuration does not imply POS access. Backend authorization remains mandatory; hiding a control is not enforcement.

## Invariants

1. Inventory alone owns quantities, reservations and movements.
2. POS never writes an Inventory balance or treats a parked cart as reserved stock.
3. Payment/provider confirmation is independently owned; a selected display method is not payment.
4. Accounting alone creates ledger events and financial truth.
5. Receipt is a projection of accepted outcomes, not proof that every downstream operation succeeded.
6. Order/sale, payment, Inventory and Accounting statuses remain independent.
7. Audit history is append-only and correlation-driven.
