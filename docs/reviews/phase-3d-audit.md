# Phase 3D Inventory frontend audit

## Outcome

**Complete — frontend executable specification only.** Phase 3D introduces no backend, database, API, model, migration, Inventory mutation/calculation, procurement, accounting, report engine, authentication, barcode or QR behavior.

## Architecture

- Inventory remains the only stock authority. All displayed quantity changes are immutable mock movement projections.
- On-hand, available, reserved, hold and in-transit remain distinct.
- Production release is a request/source event; only Inventory would post finished-goods receipt.
- Orders, Fulfillment and POS never edit stock.
- Receiving, transfer, count and adjustment views are separate workflows that eventually produce canonical movements.
- Corrections display reversal/repost linkage; no balance editor exists.
- Lots preserve source, batch/supplier, condition, expiry and movement traceability.
- No duplicate capability or role-based business rules were added.

## UX, responsive and accessibility

- Premium staff-shell patterns, spacing, typography, cards, panels, badges and tables are reused.
- Dashboard is exception-first with eight metrics, seven alert categories, queues, activity and capability-filtered quick actions.
- Item detail uses accessible tabs; movements/activity/transfer stages use semantic chronological structures.
- Desktop, tablet and mobile breakpoints preserve all units, locations, states and references.
- Tables intentionally scroll rather than dropping critical columns.
- Simulator banner is persistent, labelled and announced; denial is focusable and explanatory.
- Text accompanies all color states and controls use visible labels.

## Permission simulation

- One evaluator maps fixture capability arrays to `data-capability`.
- Inventory Clerk can receive/release/request adjustment/transfer/count within simulated scope but not approve.
- Operations Manager sees independent approvals.
- Nursery Supervisor has Inventory view only.
- Administrator lacks automatic operational access and receives direct-page denial.
- No JavaScript business branch compares role names. Hidden UI is explicitly labelled non-security.

## Quality gate

- [x] Constitution and Phase 3C.7 architecture compliance.
- [x] Production, Orders, POS, Procurement and Reporting boundaries preserved.
- [x] Dashboard, Items/detail, Lots, Movements, Receiving, Transfers, Counts and Adjustments implemented.
- [x] Alerts, immutable activity and quick actions implemented.
- [x] Capability-based simulation and direct denial implemented.
- [x] Responsive desktop/mobile visual review completed.
- [x] Accessibility semantics and keyboard tabs reviewed.
- [x] Django system check passes.
- [x] Automated tests pass.
- [x] Inventory stylesheet contains no raw CSS color literals.
- [x] No backend behavior or Inventory calculation.

## Future backend readiness

The UI exposes the required projection grain, states, commands, actor/approval/audit references and error boundaries without prescribing storage. Procurement can supply expectations; POS and Fulfillment can request idempotent issues; Reporting can consume versioned read models; Accounting can consume receipt/valuation evidence. None receives permission to mutate Inventory facts.
