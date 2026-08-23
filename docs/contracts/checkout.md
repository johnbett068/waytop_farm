# Future Checkout backend contract

> **Superseded for V1.** Retained for historical UI context. See the [ratified V1 business contract](../architecture/v1-business-contract.md).

Status: documentation only; no endpoint, model or service is implemented.

## Customer request shape

```text
cart_token: opaque string
checkout_version: opaque concurrency token
contact: { full_name, phone_e164, email }
fulfillment_method: HOME_DELIVERY | FARM_PICKUP
delivery_address: { county_code, town, address_line, instructions } | null
payment_method: MPESA | CASH_ON_PICKUP
notes: string | null
idempotency_key: opaque string
```

The customer contract must reject or ignore `branch`, `branch_id`, `assigned_branch`, client totals, payment status and inventory claims. Internal branches are not discoverable or selectable through Checkout.

## Response/context projection

Return canonical Cart lines (`variant_id`, SKU, name, unit, quantity, Decimal unit/line price), subtotal, fulfillment quote, discounts, estimated total, allowed method enums, normalized contact/address and field/non-field validation errors. Internal branch candidates are omitted.

## Validation and permissions

Server authority covers Cart ownership, catalog status, quantity, price, sellability, fulfillment coverage and payment eligibility. Home Delivery requires an accepted delivery address and does not permit Cash on Pickup in the current rule set. Farm Pickup requires no delivery address. Guests use opaque session ownership; customers use object-level ownership. Only authorized operations staff/services assign branches.

## Services and side effects

Future `CheckoutPricingService` produces projections. An idempotent `PlaceOrderService` creates immutable Order/OrderItem/contact/address snapshots only after full validation. A later `FulfillmentAssignmentService` creates or changes `FulfillmentAssignment` using inventory, proximity, workload and governed rules, recording actor/source, reason and timestamps. Payment intent, stock reservation, notifications and audit events occur through explicit services and transaction/on-commit boundaries—never from the Phase 2A frontend.
