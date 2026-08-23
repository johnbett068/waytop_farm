# Checkout workflow

> **Superseded for V1.** See the [ratified V1 business contract](../architecture/v1-business-contract.md).

## Primary flow

Populated Cart → Contact → Fulfillment → Payment → Review → mock submit → Confirmation.

1. Checkout loads the device-local Cart and authoritative catalog mock projection.
2. Customer continues as guest or sees non-functional returning/create-account explanations.
3. Customer supplies name, Kenyan phone and email.
4. Customer chooses Home Delivery or Farm Pickup. No operational location is shown.
5. Home Delivery reveals and requires Bomet County, town/area and address. Farm Pickup removes these inputs from the payload.
6. M-Pesa is display-only for both methods. Cash on Pickup becomes eligible only for Farm Pickup.
7. Review shows contact, customer-facing fulfillment and payment choices plus the complete price projection.
8. Required acknowledgement permits mock submission. The browser carries only fulfillment/payment labels to the static confirmation.

## Alternate and state flows

- Empty Cart → block form → Shop.
- Loading → announce progress.
- Invalid step → remain on step → show/focus error summary → inline messages.
- Offline → preserve preview data; future real submission waits for connectivity and server validation.
- System error → preserve local Cart → Retry.
- Permission restriction → reusable denial surface → Cart.
- Delivery → Pickup → hide/disable address → disable no longer applicable requirements → enable Cash on Pickup.
- Pickup → Delivery while Cash selected → automatically return payment selection to M-Pesa.

## Internal fulfillment flow (future, not Phase 2A)

Customer submits fulfillment method only → server accepts/revalidates order → unassigned fulfillment queue → manager or governed assignment service evaluates branch inventory, customer proximity, workload and business constraints → internal branch assignment is recorded with audit metadata → customer receives pickup/delivery readiness information without choosing the branch.

Operational assignment must not be inferred from a client field. Inventory reservation/deduction, order creation, notifications and payment initiation remain absent from this frontend milestone.
