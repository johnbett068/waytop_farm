# Phase 3C Production Workspace redesign audit

## Outcome

**Complete — frontend and specification only.** The batch detail is now a commercial-nursery operational workspace. Phase 3D Inventory remains paused. No backend, model, migration, API, authentication, calculation, inventory mutation, procurement, accounting or POS behavior was introduced.

## Architecture review

- The Batch is a parent context, not a god object. Tasks, Labour, Inputs, Expenses, Quality, Photos and Audit retain independent record boundaries.
- Tasks describe work only. Multiple Labour/Input records may link to one task without becoming task fields.
- Input usage is Production evidence and never a stock deduction; Inventory owns authoritative movements and balances.
- Expenses are non-inventory evidence and create no payable, payment or ledger fact.
- Mock estimated values are labelled; no JavaScript or Django code computes costs, progress, survival, loss or release quantity.
- Quality review/release and Inventory receipt remain separate, authorised transitions.
- Activity is an append-only composition of future domain events.
- The capability catalogue remains authoritative; role-name checks were not added.

## UI/UX review

- Eight labelled tabs replace the long task-centric detail, retaining a persistent batch header and at-a-glance operational strip.
- Overview provides identity, lifecycle, health, status and boundary context without duplicating detailed records.
- Dense records use consistent tables; Quality uses an exception-first metric hierarchy; Photos and Activity use chronological timelines.
- Responsive rules reduce grids at 1100px, stack dense content at 760px and simplify actions/timelines at 480px.
- Horizontal tab/table scrolling preserves content rather than truncating required operational fields.

## Accessibility review

- Tabs use `tablist`, `tab`, `tabpanel`, `aria-selected`, `aria-controls`, roving `tabindex`, Arrow keys and Home/End.
- Each panel has a programmatic label and focus target. Status and priority always include text.
- Chronology uses ordered lists and semantic `time`; tables use header cells.
- Disabled controls are real buttons with nearby frontend-only explanation.
- Shared visible-focus and page-state behavior remains intact.
- Mobile layouts do not depend on hover, color or pointer precision.

## Compatibility review

| Future domain | Preparation provided |
|---|---|
| Inventory | Item/lot, quantity/unit, Batch/Task traceability and an explicit independent-movement boundary. |
| Procurement | Supplier is a reference placeholder; Production cannot create supplier receipt or purchasing facts. |
| Costing | Immutable Labour, Input and Expense evidence can later be valued under versioned policy without rewriting operational records. |
| Reporting | Stable independent record types support labour, input, loss, quality, expense and profitability projections by batch/crop/area/time. |
| POS | Only future Inventory saleable projections reach POS; mock release quantities are never availability. |

## Verification

- [x] Project constitution and canonical operations reviewed.
- [x] Required Overview, Tasks, Labour, Inputs, Expenses, Quality, Photos and Activity Log implemented.
- [x] Frontend-only/no-calculation and domain-boundary language visible.
- [x] Desktop, tablet and phone CSS behavior reviewed.
- [x] Keyboard/accessibility behavior reviewed.
- [x] Django system check passes.
- [x] Automated test suite passes.
- [x] No new models, migrations, APIs or persistence.

## Remaining future decisions

Before backend work, governance must approve refined capabilities for each child record, units and valuation policy, worker/rate privacy, supplier ownership, expense/accounting handoff, file retention/scanning, pagination limits and reporting classifications. None of these decisions authorize Phase 3D.
