# Canonical operational architecture

## Purpose

Define how WayTop operates across customer orders, propagation, quality, inventory, fulfillment, POS, finance and audit. This is the governing workflow standard for future frontend specifications and backend contracts.

## Canonical propagation lifecycle

`Propagation Material Receipt → Source Lot → Production Batch → Propagation Activity → Establishment → Growing → Hardening → Quality Review → Released for Sale → Inventory Movement`

1. **Propagation Material Receipt and Acceptance:** Inventory owns the physical stock receipt/movement. Production records the linked traceability and fitness acceptance for seed, rootstock, scion, cutting, mother-stock material or another approved source; it never creates on-hand quantity.
2. **Source Lot:** identifies a coherent traceable source. It may be seed, grafting material, cuttings or other propagation material. Seed-specific fields are optional extensions, never universal requirements.
3. **Production Batch:** plans target product/variant, propagation method, expected quantity, schedule, responsible staff and initial location. One source lot can feed multiple batches; a batch may consume multiple source/input lots through explicit usage records.
4. **Propagation Activity:** method-specific activity such as sowing, grafting, budding, cutting, division or transplanting. Extensible method configuration supports future propagation without redesigning the batch lifecycle.
5. **Establishment:** observes germination when applicable, graft take, rooting or survival. Expected/actual quantities and rejected/cull reasons reconcile batch flow.
6. **Growing:** records stage progress, growth percentage/observations, watering, fertilizer, chemical/biological treatments, labour, media/soil, seed, tray, pot/bag and grafting-material consumption.
7. **Hardening:** records planned/actual schedule and observations before sale or field establishment. Overdue hardening is an exception.
8. **Quality Review:** grades plants, records accepted/rejected/cull quantities, observations and holds. A hold blocks release without erasing prior work.
9. **Released for Sale:** an authorised approval records released quantity/grade. Approval is immutable; corrections use a governed reversal/superseding review.
10. **Inventory Movement:** release posts an authorised production-receipt movement into saleable inventory. Before this movement, the batch is WIP, not sellable stock.

### Production records and calculations

The architecture supports batch losses, culling/rejection, conditional germination percentage, survival percentage, growth percentage, grading, notes, observations, input consumption, labour, schedules/applications, production location history, batch movement history, staff responsibility, quality holds, releases and audit history. Percentages always declare numerator, denominator, observation time and applicability. They are calculated by future services, never entered as an untraceable replacement for quantities.

### Exception management

Dashboards prioritise high mortality, poor germination/establishment, delayed growth, overdue hardening, quality holds, low propagation material, input shortage, production bottleneck, ready-for-release and awaiting-review queues. Threshold policy is configurable, effective-dated and crop/method/stage-aware; the Phase 3A numbers are mock projections.

## Customer order, payment and fulfillment

`Order Received → independent Payment events + independent Fulfillment planning → inventory allocation/picking → Ready for Pickup/Dispatch → Collected/Delivered → Order completion`

Order, Payment and Fulfillment remain separate state machines. Cash on Pickup can remain Payment Pending while Fulfillment becomes Ready. Branch assignment is an internal Fulfillment decision using inventory, proximity, workload and policy. Production does not become a hidden sub-step of a customer order: unavailable stock may drive planning decisions, but customer fulfillment never mutates a production batch directly.

Canonical Order states are New → Under Review → Accepted → Processing → Completed, with Cancelled as the governed alternative. Canonical Fulfillment states are Awaiting Feasibility Check → Ready for Assignment → Assigned → Picking/Preparing → Fulfillment Quality Check → Ready for Pickup/Dispatch → Collected/Delivered. Returns use Requested → Authorised → Received → Inspected → Resolved. Refund and Return records never become replacement terminal Order statuses; partial operations are first-class.

## Inventory lifecycle

`Authorised Receipt → Stock Movement → Available Projection → Transfer/Allocation/Sale/Return/Count → Reversing or Variance Movement → Audit`

- Production release, supplier receipt, transfer receipt and customer return are distinct movement reasons.
- Transfers create linked dispatch and receipt events; in-transit quantity is explicit.
- Adjustments require reason, evidence, permission and audit. Users never type a replacement balance.
- Sale/fulfillment consumption posts movement lines from authoritative lots/locations.
- Returns do not restore saleable stock automatically; inspection determines quarantine, saleable return or disposal movement.
- Counts record observations; approved variance creates adjustment movements.

## POS and financial workflow

`Open authorised POS session → build sale → validate prices/availability → record tender/payment → complete sale → stock movement → receipt projection → close/reconcile session`

Payment and sale facts are immutable. Voids/refunds/returns create linked reversals. Cash movements require reason and role. POS uses the same Catalog, Inventory and Payment rules as other channels and cannot edit balances or provider confirmations.

## Operational handover and tasks

Exceptions and approved plans produce assigned tasks with owner, due time, priority and source record. Completing a task does not silently perform the underlying domain transition. Daily handover summarises unresolved exceptions, accountable owner and next decision, preserving audit continuity.

## Displayed information, actions and states

Staff projections display queues, exceptions, independent statuses, quantities/units, locations, responsible roles, timestamps and customer commitments. Future actions issue explicit commands such as Record Receipt, Record Observation, Place Hold, Approve Release or Prepare Movement. Loading, empty, offline-stale, validation, system-error, permission and success states are mandatory.

## Permissions, models and backend contracts

Future role capabilities separate production recording, quality approval, inventory posting, fulfillment assignment, payments/refunds, POS tendering and settings. A person should not approve their own sensitive correction where separation-of-duty policy applies. Models are owned by the domains in `business-domains.md`. Commands validate current state/version and append audit metadata; dashboards consume read-only cross-domain projections.

## Business rules

- Inventory is never edited directly; all changes are movements.
- Financial records are immutable; returns/refunds create reversing transactions.
- Payment, Fulfillment and Production are independent.
- Production WIP feeds Inventory only through approved release and movement.
- Inventory feeds sales/fulfillment through governed allocation/movement.
- Audit history is append-only and never lost.
- No universal seed, germination or tray assumption is permitted.

## Definition of Done

Propagation-neutral, order/payment/fulfillment, inventory, POS, return, task/handover and audit workflows are defined with states, permissions, future records, command/query boundaries, exceptions and operational invariants.
