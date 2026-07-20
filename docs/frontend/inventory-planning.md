# Phase 3D Inventory frontend planning

## Recommendation

Use a workflow-oriented Inventory workspace, not a single editable stock table. The persistent shell should show current branch/location scope, projection freshness, active exceptions and simulated/future permission context. Balances are read-only projections; every change begins a named transaction workflow.

## Proposed navigation

| Module | Primary purpose | Key UX |
|---|---|---|
| Dashboard | Operational health and exception queues | On-hand/availability summaries, receiving backlog, low/reorder, expiry/holds, transfer/count variance; never ambiguous “total stock.” |
| Stock Items | Item/lot/location discovery | Search/filter, category tree, handling/tracking badges, on-hand vs available/reserved/in-transit, item ledger link. |
| Movements | Canonical transaction ledger | Chronological filters, source/destination, reason, state, actor, correlation and reversal chain. No inline balance editing. |
| Receiving | Supplier, Production and return receipts | Evidence-led inspection, lot/expiry/condition/location, partial acceptance and quarantine. |
| Transfers | Branch/location custody workflow | Draft/approval/dispatch/transit/receipt timeline, line discrepancies and two-person custody. |
| Counts | Cycle/full count execution | Scope planning, accessible count entry, blind-count mode, recount and variance investigation. |
| Adjustments | Exceptional correction queue | Reason/evidence, approval threshold, self-approval prevention and reversal—not a generic quantity editor. |
| Reports | Inventory-owned operational projections | Current stock, consumption, movements, loss/waste/shrinkage, expiry and reorder; valuation clearly sourced from costing policy. |
| Activity Log | Append-only domain/audit projection | Actor, action, transaction, time, branch/location, approval and correlation. |

“Movements” is the unifying ledger; Receiving, Transfers, Counts and Adjustments are focused workflows that produce governed movements. This avoids duplicating business rules across screens.

## Item detail recommendation

Use a stable header (item identity/category/type/unit/tracking/active state) with tabs for Overview, Lots, Locations, Movements, Reservations/Allocations (future), Expiry/Quality, Related Production/Procurement, and Activity. Show on-hand, available, reserved, allocated and in-transit separately with `as_of` time. Never show one unlabeled “stock” number.

## Interaction rules

- Transaction actions use explicit verbs: Receive, Issue to Production, Start Transfer, Record Count, Request Adjustment, Return to Supplier.
- Source/destination and lot selection come from authoritative allowed choices.
- Quantity inputs always show unit and conversion; destructive ambiguity is rejected.
- Approval/reason/evidence obligations appear before submission.
- Posted records are read-only; correction starts a linked reversal flow.
- Stale/offline/permission/conflict states cannot submit and preserve safe draft input where possible.
- Direct URLs use the documented 403/404 disclosure policy and scope-filter all counts/search/export.

## Responsive and accessibility requirements

Desktop uses split queues/details and dense tables with sticky identifiers where useful. Tablet collapses secondary panels. Mobile uses record cards or deliberate horizontal tables for comparison-heavy ledger lines; it never drops lot, unit, state or location.

All workflows require semantic headings, labelled fields, error summary plus field errors, keyboard operation, visible focus, text-plus-color statuses, announced async outcomes, focus-managed dialogs and accessible confirmation copy naming item/quantity/source/destination. Count entry must support rapid keyboard operation without auto-submitting or exposing expected quantity in blind mode.

## Mandatory UI states

Each module specifies loading, empty, permission, offline-stale, validation, concurrency conflict, partial success, system error and success. Empty is distinct from zero balance and from unauthorized data. Projection freshness and branch/location scope remain visible during decisions.

## Phase 3D design gate

Before screens are implemented, approve item/location taxonomy, units/conversions, transaction reason catalogue, negative-stock policy, lot/expiry/chemical rules, reservation semantics, transfer/count thresholds, adjustment approval, valuation display ownership and sensitive export policy.
