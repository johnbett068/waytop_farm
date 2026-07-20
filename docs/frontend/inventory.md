# Inventory Management frontend

## Scope

Phase 3D implements a frontend-only executable specification for Inventory. All records and totals are fixed mock projections. There is no backend, persistence, API, model, migration, stock calculation/mutation, procurement, accounting, reporting engine, authentication, barcode or QR behavior.

## Modules

| Module | Frontend responsibility | Architectural guardrail |
|---|---|---|
| Dashboard | Eight stock/exception metrics, alert queue, pending work, recent activity and quick actions. | Mixed-unit values are labelled and never treated as valuation. |
| Stock Items | Search/filter/sort/paginate item/location projections. | Available, reserved, condition and lifecycle status remain separate. |
| Item Workspace | Overview plus Movements, Lots, Locations, Reservations, Transfers, Counts and Activity tabs. | Item definition is not a balance; tabs are independently pageable future projections. |
| Lots | Source/supplier/Production batch, receipt/expiry, condition, quantity and movement-history links. | Read-only traceability; no inline quantity editing. |
| Movements | Timeline ledger covering receipt, issue, transfer, Production, sale/POS, adjustment, damage/waste, return and correction semantics. | Posted history is immutable; correction links reversal/repost. |
| Receiving | Supplier, Production, transfer and customer-return evidence form/queue. | Preview only; receipt neither creates Procurement payable nor makes returns available automatically. |
| Transfers | Draft/approval/transit/receipt/variance/completion timeline and lines. | Source dispatch and destination acceptance are separate custody facts. |
| Counts | Cycle/full count queues, blind execution, variance approval and closed history. | Observations never overwrite balances; approver is independent. |
| Adjustments | Damage, spoilage, shrinkage, correction and quality-hold queues. | Hold restricts availability; quantity effect requires approved movement. |

## Capability simulation

Inventory pages include a development-only banner and fixture selector for Sarah Wanjiku, John Bett, Peter Kiptoo and Amina Noor. One JavaScript evaluator consumes each fixture’s capability array. Elements declare `data-capability`; no conditional compares role names.

The selected fixture persists in namespaced local storage. Inventory navigation is filtered with `inventory.view`; action visibility uses receive, transfer, count, adjustment and approval capabilities. Selecting a fixture without `inventory.view` simulates direct-page Permission Denied. The banner states that simulation is not security. Future backend authorization remains authoritative.

## Interaction and accessibility

- Item tabs use the ARIA tabs pattern, roving focus, Arrow Left/Right and Home/End.
- Status/condition/priority always use text plus color.
- Movement/activity/transfer sequences are ordered lists with readable dates and references.
- Tables retain explicit units, locations and conditions and scroll horizontally when comparison requires it.
- Forms have visible labels; actions name their intended transaction.
- Loading, empty, error, permission, offline and success states are exercisable by query-string fixture state.
- Focus moves to consequential simulated denial/error headings where appropriate.
- Mobile layouts stack cards/actions and preserve horizontally scrollable ledger/table information.

## Responsive design

The layout follows the existing staff system. At wide desktop it uses four-column metrics and main/aside operational queues. At tablet it reduces metrics and collapses split views. At mobile all summary grids become single column, while module navigation/tabs scroll without truncating labels. Transfer stages remain an intentional horizontal comparison.

## Definition of Done

Done means all nine modules/routes render consistent mock projections, capabilities filter actions centrally, every architecture boundary is visible, responsive/accessibility behavior is testable and no server-side Inventory behavior exists.
