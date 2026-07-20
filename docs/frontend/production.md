# Production batch operational workspace

## Purpose and boundary

The Production Batch detail page is the parent operational workspace for commercial nursery work. It composes independently governed Tasks, Labour, Inputs, Expenses, Quality, Photos and Activity without turning them into fields on one oversized record.

This milestone is frontend-only. All values are realistic fixtures. Controls are inert and no browser code calculates cost, quantity, survival, loss, release readiness or stock. No backend, API, model, authentication, procurement, accounting or Inventory behavior is introduced.

## Information architecture

The persistent header identifies the batch, production area, current stage, supervisor, expected release, status and mock progress. Eight tabs progressively disclose operational detail:

| Tab | Purpose | Explicit exclusion |
|---|---|---|
| Overview | Stable identity, stage, health, dates, lifecycle and quick record counts. | Does not derive authoritative totals or advance stage. |
| Tasks | Planned and completed work with assignment, priority, dates, status and notes. | Does not record labour cost or consume an input. |
| Labour | Worker/time/rate evidence, optionally linked to a task; many entries per task. | Does not replace staff assignment or perform payroll/costing. |
| Inputs | Material-usage evidence with quantity/unit, estimated valuation and task/batch links. | Does not deduct Inventory, receive Procurement or value stock. |
| Expenses | Non-inventory operating spend such as utilities, hire, transport and repairs. | Does not create payables, payments or ledger entries. |
| Quality | Quantity observations, condition classes, notes, inspections, holds and release readiness. | Does not calculate metrics or release stock. |
| Photos | Chronological visual evidence for production milestones. | Contains placeholders; no upload/storage exists. |
| Activity log | Append-only chronological actor/time/action/comment projection. | Is not editable and does not infer domain events from UI clicks. |

Tabs are preferable to a single long task-oriented page because desktop nursery operators need fast context switching across dense record sets while retaining batch identity. Horizontal scrolling preserves every labelled tab on narrow screens without replacing semantics with an ambiguous menu.

## Interaction and accessibility

The tab list uses the ARIA tabs pattern. Click selects a tab; Left/Right arrows move between adjacent tabs; Home/End select the first/last tab. Only the selected tab is in the sequential focus order. Panels remain labelled and programmatically focusable. The initial URL fragment may select a valid section, enabling reproducible review.

Tables scroll horizontally rather than clipping fields. Status and priority use text in addition to color. Dates use readable copy and semantic `time` where chronological evidence is presented. Disabled preview controls remain visibly disabled, and nearby copy explains the frontend-only boundary. Visible focus comes from the shared staff foundation.

At tablet widths, summary and detail grids reduce columns. At phone widths they become single-column, actions become full-width where appropriate, tab labels remain horizontally scrollable, timelines narrow, and photo evidence stacks above its description.

## Future permissions and states

Future server projections filter every tab with canonical capabilities and scope. Viewing Production does not imply permission to record activity, labour, input usage, expense evidence, quality review, photos, costs or release. Release preserves the approved separation-of-duty policy.

Loading, empty, offline-stale, permission and error states continue to use the shared Production state components. Future tab-specific empty and denial states should not disclose counts from unauthorized sections.

## Definition of Done

Done means all eight sections are present, keyboard and responsive behavior is testable, the batch remains the parent context, independent records retain their own semantics, Inventory/Procurement/Costing/Finance boundaries are explicit, and no backend or calculation behavior exists.
