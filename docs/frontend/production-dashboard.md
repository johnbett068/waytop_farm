# Production Dashboard

## Purpose
The staff-only dashboard is an exception-first projection of plant production work-in-progress (WIP). It supports seed, graft, rootstock, cutting, tree, herb, ornamental and future propagation methods. It is not an inventory dashboard.

## Displayed data and actions
It displays active and stage counts, quality/release queues, exception and resource alerts, upcoming tasks, batch identifiers, locations and responsible roles. Staff can navigate to batches, source lots, tasks and exceptions. Creation/export buttons remain disabled in Phase 3C.

## States, permissions and accessibility
Loading, empty, validation/error, offline, permission and success states are reproducible with `?state=`. Future permissions separate view, plan, record, quality-hold and release-approval capabilities. Semantic headings, labelled controls, visible focus, keyboard links and state-heading focus management are required.

## Backend contract and business rules
Future read projections combine `ProductionBatch`, `BatchStageEvent`, `ProductionTask`, `ProductionException`, `ResourceRequirement`, `QualityReview` and `ReleaseApproval`. Counts and thresholds are backend-computed; the browser never derives production truth. Completing work, acknowledging an alert or approving release are distinct commands. Release does not create inventory.

## Definition of Done
Responsive dashboard, method-neutral mock data, exception-first alerts, all page states, token-only styling, documented permissions/contracts and no writes, calculations, inventory mutations or scheduling engine.
