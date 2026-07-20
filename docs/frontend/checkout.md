# Checkout frontend specification

## Purpose

Phase 2A specifies the final customer-facing Checkout without authentication, database writes, APIs, payment processing, inventory deduction/reservation, order creation or backend validation. It converts a saved Cart into a reviewable mock request and demonstrates confirmation.

## User journey

Cart → Checkout → Customer information → Fulfillment → Payment → Review → Mock confirmation.

The four input/review steps use one accessible form; confirmation is a separate page. Desktop uses a horizontal progress indicator and sticky summary. Small screens use an overflow-safe stepper and collapsed summary.

## Displayed data

- Contact: checkout mode, full name, Kenyan phone number and email.
- Fulfillment: Home Delivery or Farm Pickup. Home Delivery reveals county, town/area and address. Both methods accept optional order notes.
- Payment: M-Pesa display-only; Cash on Pickup only when Farm Pickup is selected.
- Summary: catalog products, quantity, unit, line total, subtotal, mock fulfillment charge, payment selection, estimated savings (`KES 0` until promotion rules exist), estimated total and notes.
- Confirmation: mock number `WTF-260716-1042`, estimated fulfillment, fulfillment method, mock payment status and internal-assignment explanation.

No branch identifier or branch name is displayed or submitted. `assigned_branch` is an internal outcome determined later by authorized staff or fulfillment logic.

## User actions and validation

Customers may select guest, returning-customer or create-account modes. The latter two are explanatory UI placeholders and do not authenticate. Customers navigate forward/back, change fulfillment/payment, expand the mobile summary, review the request and submit a mock preview.

- Full name: required, minimum two characters.
- Phone: required Kenyan international format; accepted presentation follows `+254 724 853 914`.
- Email: required and structurally valid.
- Home Delivery: county, town/area and address required; Phase 2A county mock is Bomet County.
- Farm Pickup: delivery address controls are hidden, disabled and excluded from the future payload.
- Notes: optional, maximum 500 characters; warn against payment PINs or financial information.
- Review acknowledgement: required before mock submission.
- Validation appears inline and in a focusable error summary. Step headings receive focus after navigation.

## Page states

- Loading: saved Cart and projection preparation.
- Empty: blocks Checkout and links to Shop.
- Validation error: preserves entered data and focuses the error summary.
- Offline: global network banner applies; local preview may be reviewed, but a real submission would be blocked until authoritative validation is available.
- System error: retry without losing device-local Cart.
- Permission denied: reusable component/state for future channel or account restrictions; not applied to public guest Checkout today.
- Success: populated multi-step form and separate mock confirmation. `?state=success` supplies a non-persistent visual-review fixture only when the local Cart is empty.

## Permissions

Guest Checkout is public and scoped to an opaque Cart/session token. Returning/create-account controls grant no permissions in Phase 2A. Future customers may read and submit only their owned active Checkout. Staff-only branch assignment is never writable through the customer contract.

## Reusable components

`CheckoutStepper`, `CheckoutField`, `FulfillmentSelector`, `PaymentSelector`, `CheckoutOrderSummary`, `ValidationSummary`, `CheckoutState`, `ReviewCard` and `SuccessCard` are represented by template structure, data contracts and checkout-specific styling.

## Future models and relationships

- `Customer` 1—many `Address`; `Address` belongs to a County reference and stores delivery instructions separately.
- `Cart` 1—many `CartItem`; each item references `ProductVariant` and an authoritative `ProductPrice` projection.
- `CheckoutSession` references one Cart, customer/guest identity, chosen `FulfillmentMethod`, delivery-address snapshot where applicable and payment-method intent.
- `Order` is created only by an idempotent application service after server validation; `Order` has immutable customer/contact/address snapshots and many `OrderItem` snapshots.
- `FulfillmentAssignment` belongs to an Order and later references an internal `Branch`; it records assignment source, reason/audit metadata and timestamps.
- `PaymentIntent`/`Payment` belongs to an Order. M-Pesa integration is future work and must never accept a PIN in WayTop forms.

No models are implemented in Phase 2A.

## Future views, context and API

- Django views: `CheckoutStartView` (`GET`), `CheckoutValidateView` or form POST, and `OrderConfirmationView` after idempotent creation.
- Initial context: `checkout_session_id`, sanitized cart projection, contact defaults, allowed fulfillment methods, fulfillment quote, allowed payment methods, validation constraints and CSRF token. It must not expose internal branch candidates.
- Future API/form payload: `cart_token`, `checkout_version`, contact object, `fulfillment_method`, optional delivery-address object, `payment_method`, notes and an idempotency key.
- Forbidden customer payload keys: `branch`, `branch_id`, `assigned_branch`, price totals, payment status and inventory status. Server-owned projections ignore/reject these values.
- Response: canonical re-priced summary, validation errors or order reference after successful authoritative submission.

## Side effects and business rules

Phase 2A has no backend side effects. The mock submission writes only the selected fulfillment/payment labels to `sessionStorage` for confirmation rendering.

In production, submission must atomically revalidate ownership, variants, quantities, prices, fulfillment eligibility and payment eligibility. Home Delivery currently allows M-Pesa; Farm Pickup allows M-Pesa or Cash on Pickup. A customer cannot select an operational branch. After order acceptance, an authorized manager or `FulfillmentAssignmentService` assigns a branch using inventory, proximity, workload and governed business rules, with audit history. Assignment changes must not silently change customer price or promise.

## Definition of Done

Responsive four-step Checkout and mock confirmation; sticky/collapsible summary; realistic catalog data and Kenyan contact/address examples; all required states; keyboard navigation and focus management; readable validation; token-only colors; internal-only branch contract; documentation and automated checks; no backend functionality.
