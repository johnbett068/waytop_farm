# Delivery & Fulfillment frontend contract

## Ownership

Delivery belongs to Fulfillment, which belongs to an Order. It tracks the customer handover process and references immutable Order/Fulfillment lines. It does not own Order acceptance/completion, Payment, Inventory, transport resources, customer master data or Accounting.

## Future projections

- Delivery dashboard: authorized scope, `as_of`, queue counts and recent public/operational events.
- Delivery job: delivery number, Fulfillment and Order references, method, customer/contact/address snapshots, expected date/window, status, notes and transport notes.
- Lines: Fulfillment line references, Order item references, quantity/unit and display snapshots.
- Evidence: contact/confirmation, informational checklist, dispatch, received-by, failed/reschedule and collection events.
- Allowed commands: capability and independently versioned aggregate hints.

Personal data is field/scope protected. Inventory/Sales views receive fulfillment progress only, not broader customer or internal transport notes without separate permission.

## Canonical capabilities

Phase 3C.5 defines `fulfillment.view`, `fulfillment.assign`, `fulfillment.dispatch` and `fulfillment.record_delivery`. The UI uses only these strings and capability arrays. Role labels never determine access. Backend authorization remains mandatory.

## Future commands

Possible governed commands are `RecordCustomerContact`, `RecordCustomerConfirmation`, `DispatchFulfillment`, `RecordDeliveryFailure`, `RescheduleDelivery`, `RecordDelivery`, and `RecordCollection`. Each carries actor/active assignment, capability, scope, Fulfillment/Delivery version, reason/evidence, idempotency key and correlation ID.

Commands append immutable Fulfillment/Delivery events. They cannot directly change Order, Payment, Inventory or Accounting state. `EvaluateOrderCompletion` remains an Order-owned reaction to accepted Fulfillment evidence.

## Invariants

1. Home delivery follows confirmation before dispatch; dispatch requires explicit readiness evidence.
2. Pickup follows Ready for Collection to Collected. “Completed” is an Order/Fulfillment projection, not a second Delivery mutation.
3. Failed delivery preserves prior events and may create a new reschedule event.
4. The checklist is informational and never posts quality or stock facts.
5. Delivery never reserves/deducts stock; Inventory alone posts movements.
6. Delivery never confirms payment or creates Accounting entries.
7. Transport notes are free operational context, not managed driver, vehicle, GPS, route, fuel or cost records.
