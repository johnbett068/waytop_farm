# POS sale flow

> **Superseded for V1.** POS is an Order-entry channel, not a separate commercial lifecycle. See the [ratified V1 business contract](../architecture/v1-business-contract.md).

## Phase 4A preview flow

1. Cashier views an open-register projection.
2. Cashier searches projected Catalog products and sees timestamped Inventory availability.
3. Cashier changes an in-memory mock cart.
4. Cashier selects walk-in/existing customer and a payment-method display.
5. Complete, park, register and receipt actions show frontend-only feedback.
6. No record, reservation, payment, movement, ledger event or receipt is created.

## Future governed flow

1. Authorize `pos.process_sale` within the active register and branch scope.
2. Create a draft sale with an idempotency key and immutable correlation ID.
3. Revalidate server-owned prices and Inventory availability; expose conflicts rather than silently substituting.
4. Record the independently confirmed tender outcome. Selecting Cash, M-Pesa or Card is not confirmation.
5. Accept the sale/order outcome.
6. Request an idempotent Inventory issue. Inventory posts its own movement or returns an explicit failure.
7. Publish the accepted commercial facts for Accounting to create its own future entries.
8. Build a receipt projection that reports sale, tender, Inventory and Accounting outcomes independently.
9. Append audit evidence for every request, approval, retry and outcome.

## Failure and retry

- Payment failure must not be labelled a completed payment.
- Inventory rejection must not be hidden by a completed sale banner.
- An Accounting delay must not rewrite sale or Inventory state.
- A retry reuses the idempotency key and correlation ID; it never duplicates a tender, issue or ledger event.
- Parked sales hold customer intent only and do not reserve Inventory.

Returns and exceptional refund/void workflows are intentionally deferred to Phase 4B.
