# Canonical Business State Machines

> **Superseded for V1.** The active V1 states are defined by the [ratified V1 business contract](v1-business-contract.md).

This is the future backend reference. Each aggregate owns its transitions, audit log and permissions. A composed screen may display multiple states but cannot mutate another domain. Commands are atomic, authorised, version-checked and auditable; domain events inform other services without cross-domain status writes.

## Approved commercial lifecycles

| Owner | States and allowed forward transitions | Alternate / terminal rules |
|---|---|---|
| Order | New → Under Review → Accepted → Processing → Completed | Any permitted non-terminal state → Cancelled under cancellation policy. Returns/refunds are never Order states. |
| Fulfillment | Awaiting Feasibility Check → Ready for Assignment → Assigned → Picking / Preparing → Fulfillment Quality Check → Ready for Pickup **or** Ready for Dispatch → Collected **or** Delivered | Feasibility reads released inventory, forecasts and incoming batches; it never changes Production. Partial fulfilments and multiple deliveries use separate fulfillment units/consignments. |
| Payment | Pending → Confirmed **or** Failed | Split payments are separate attempts/allocations. Payment never advances Fulfillment. |
| Refund | Requested → Refund Pending → Refunded | Independent records reference payment/return context and amounts. They do not rewrite the original financial record or Order state. |
| Return | Requested → Authorised → Received → Inspected → Resolved | Partial returns use return lines and dispositions; the original Order and financial records remain intact. |

## Production aggregate flow

The canonical operational flow is `Material Receipt → Source Lot → Production Batch → Propagation Activity → Establishment → Growing → Hardening → Quality Review → Released for Sale → Inventory Movement`. It spans owners:

- Receipt owns Draft → Received → Accepted, with Rejected/Quarantined outcomes configured by policy.
- Source Lot owns Available → Depleted/Closed, with On Hold as a governed restriction. Usage is an append-only relationship, not a lifecycle shortcut.
- Production Batch owns Planned → Propagation Activity → Establishment → Growing → Hardening → Quality Review → Released for Sale. Cancelled/Terminated requires reason, disposition and audit; a quality hold is an orthogonal blocking record, not a stage.
- Release Approval owns Pending → Approved or Rejected. Approval records released grade/quantity and publishes a release event.
- Inventory Movement is Inventory-owned: Draft → Posted or Cancelled. Posting references an approved release and alone changes stock.

Production methods determine required activities and measurements, not a different database shape. Stage skipping or rollback is prohibited by default; exceptional correction uses an authorised compensating event and never erases history.

## Supporting operational machines

These are canonical contract states for implementation, subordinate to their owning domain:

| Owner | Allowed transitions |
|---|---|
| Production Task | Upcoming → Ready → In Progress → Completed; any permitted open state → Cancelled; due-date policy derives Overdue as a projection, not stored terminal state. |
| Production Exception | Open → Acknowledged → Resolved; Resolved → Reopened when new evidence is audited. |
| Quality Hold | Active → Released or Rejected/Closed; hold blocks configured transitions but does not replace batch stage. |
| POS Sale | Draft → Tender Pending → Completed or Voided; completed sales create their own payment and Inventory movement commands. |

## Cross-domain invariants
Orders consume nothing. Production releases approved plant quantities. Inventory movements alone alter stock. Fulfillment consumes/reserves inventory through Inventory-owned records. Production, Order, Fulfillment, Payment, Refund and Return never directly change one another’s lifecycle. Every partial fulfillment, delivery, payment, refund and return is line/quantity aware and independently auditable.

## Implementation rule
Future Django models use explicit transition services/commands and append-only transition/audit events. Views and APIs return allowed actions but do not contain transition policy. Reports consume projections/events and do not infer state by editing source records.
