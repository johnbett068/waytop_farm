# Procurement lifecycle

## Primary lifecycle

`Department/Production need → Purchase Request → independent approval → quotation/sourcing decision → Purchase Order approval/issue → supplier delivery → Procurement inspection → Inventory receipt → future Accounting match`

Each arrow crosses explicit state or domain ownership. No UI click or upstream approval silently performs a downstream action.

## Purchase request

`Draft → Submitted → Supervisor/Operations approval or Rejection → Approved → Converted to PO`

Requester supplies department, branch, required date, priority, item/service lines, units, estimate and reason. Estimates are not supplier prices or Accounting facts. Requester cannot self-approve. Cancellation retains history.

## Sourcing and order

`Quotation requested/received → validated comparison → governed award → draft PO version → independent approval → issued supplier commitment`

Supplier preference and performance inform but do not automatically decide award. Conflicts and selection reason are explicit. Material amendments create a new PO version and approvals.

## Delivery and receiving

`Expected delivery → supplier arrives → record delivered quantities → inspect accepted/rejected/damaged/hold → publish inspection evidence → Inventory independently posts eligible receipt`

Partial delivery leaves remaining schedule open. Rejected/damaged/held quantities do not become available stock. Procurement receiving never selects an Inventory destination balance or posts movement directly.

## Documents

Quotation and PO support sourcing/commitment. Delivery note and inspection report support custody evidence. Invoice supports future matching. Inventory receipt is an Inventory reference. All attachments are versioned metadata and never replace transactional facts.

## Reporting and activity

Procurement publishes supplier, request, quotation, PO, delivery and inspection events. Reporting derives on-time rate, rejection, lead time, accuracy, quality and spend with declared grain. The activity log composes immutable actor/role/action/reference/reason/time/correlation events without owning them.

## Failure paths

Supplier delay creates an alert, not an automatic PO cancellation. Quality issue records rejected/hold evidence and follow-up. Inventory receipt denial leaves Procurement inspection intact and creates reconciliation work. Invoice mismatch belongs to future Accounting. Offline/permission/stale failures change no facts.
