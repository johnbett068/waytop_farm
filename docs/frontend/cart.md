# Cart specification

## Purpose and users

The Cart lets guest and future authenticated customers assemble a seedling estimate, adjust quantities, review pricing and continue to Checkout without creating an order or reserving inventory.

## Displayed data and actions

Each line shows product identity, image, category, price, unit, quantity, stock label and line total. The summary shows item count, subtotal, unpriced fulfillment and estimated total. Customers may change quantity, remove/undo, clear/undo, continue shopping and proceed to Checkout.

Operational branches are internal entities. Cart and Checkout do not expose a branch name, branch selector or `branch_id` input. Internal fulfillment assignment occurs only after submission.

## States and validation

Loading, empty, populated success, simulated system error, offline/local fallback, unavailable product and storage failure are represented. Quantity is an integer from 1–99. The future server must revalidate ProductVariant identity, active Decimal price, quantity and sellability.

## Permissions and future models

Guests manage only the Cart identified by an opaque session token. Authenticated customers manage only their active Cart. Future models are `Customer`, `Cart`, `CartItem`, `ProductVariant`, `UnitOfMeasure`, `ProductPrice`, `Branch` and `BranchStock`; branch models are not customer inputs.

## Backend contract and rules

- Current view: `GET /cart/`, template plus device-local state only.
- Future `CartService` owns line validation and ownership.
- Future `CartPricingService` returns projections; totals are not financial records.
- Cart writes never move or reserve inventory, create an Order or initiate Payment.
- Checkout captures only fulfillment method. Future staff/system logic assigns the operational branch after submission.

## Definition of Done

Responsive Cart and mini-cart, keyboard-managed drawer, quantity validation, correct arithmetic, empty/loading/error/offline states, accessible controls, explicit non-reservation language, Checkout link and no customer-visible branch selection.
