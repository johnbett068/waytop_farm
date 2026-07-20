# Delivery workflow

## Home delivery

`Awaiting Customer Confirmation → Customer Confirmed → Ready for Dispatch (Fulfillment projection) → Out for Delivery → Delivered`

`Out for Delivery → Delivery Failed → Rescheduled → Customer Confirmed/Ready for Dispatch`

1. Operations records customer-contact and confirmation evidence, preferred time and instructions.
2. Fulfillment readiness composes Order lines, Inventory issue evidence and the informational checklist without changing those records.
3. Operations records dispatch date, expected date and free-form transport notes. No transport resource is assigned.
4. Operations records delivered date/time, receiver and notes, or a governed failure reason and reschedule date.
5. Order independently evaluates completion from accepted Fulfillment results.

## Customer pickup

`Ready for Collection → Collected → Completed projection`

Operations records collector, collection time and notes. Inventory issue and Payment outcomes remain independently owned. Collection does not itself receive payment or post stock.

## Integration

- Order supplies the customer commitment and item snapshots.
- Fulfillment owns preparation, readiness and customer handover progress.
- Inventory independently supplies availability/issue status and alone posts quantity movements.
- Payment status is read independently and cannot be inferred from delivery/collection.
- Future Accounting consumes immutable commercial, payment and Inventory evidence; Delivery creates no ledger event.

Every future event uses correlation and idempotency references. Partial failure remains explicit: delivered does not imply paid, Inventory-posted or accounted, and those outcomes never rewrite delivery history.
