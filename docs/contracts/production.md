# Production Backend Contract (Future)

## Scope
Documentation only. Phase 3C supplies read-only mock projections and disabled commands. No Django models, API, persistence, calculations or inventory behavior exist.

## Future model graph
- `PropagationMaterialAcceptance 1—* SourceLot`; it references an Inventory receipt/issue lot and records Production traceability/fitness only. The legacy `PropagationMaterialReceipt` label must not be implemented as a second stock receipt.
- `ProductionBatch *—* SourceLot` through `BatchMaterialUsage`; batch also references product/variant, propagation method, current production stage and responsible role.
- A batch has many `PropagationActivity`, `BatchStageEvent`, `QuantityObservation`, `BatchLoss`, `QualityGrade`, `InputConsumption`, `LabourRecord`, `WateringRecord`, `TreatmentApplication`, `BatchLocationEvent`, `ProductionTask`, `Observation`, `Attachment`, `QualityHold`, `QualityReview`, `ReleaseApproval` and audit events.
- `ProductionRelease 1—* ReleasedQuantity` records product/grade/quantity/unit. Inventory references a release from an independently posted `InventoryMovement`; Production never posts it.
- Cost records eventually reference immutable resource/labour usages and valuation policy. They are not batch columns computed by the browser.

## Batch workspace record boundaries

`ProductionBatch` is the parent operational context, not a universal mutable record. Its child domains retain separate identifiers, permissions, validation and histories:

| Record | Owns | Does not own |
|---|---|---|
| `ProductionTask` | title, assignee/team, priority, planned/actual dates, work status and notes | Labour time/cost, material movement, stage transition |
| `LabourRecord` | worker, staff type, hours/days, rate reference, supervisor, notes and optional task link | Task completion, payroll, authoritative cost total |
| `InputUsage` | item/lot reference, quantity/unit, optional estimated valuation, supplier reference and optional task link | Inventory balance/movement, Procurement receipt or supplier master |
| `ProductionExpense` | category, description, amount evidence, date, recorder and optional task link | Material quantity, payable, payment or ledger posting |
| `QualityObservation/Review` | applicable quantity observations, condition/grade, notes, inspection history and hold/release evidence | Browser-derived metrics or Inventory availability |
| `Attachment` | file/evidence metadata, milestone label, capture time, actor and retention classification | Binary storage policy or upload scanning |
| `AuditEvent` projection | actor, time, action, comment/reference and correlation | Mutable business truth |

Task, Labour, Input and Expense independence prevents one task edit from rewriting historical resource or financial evidence. Multiple Labour and Input records may reference the same Task, and an Expense may omit a Task while remaining attributable to the Batch.

## Read contracts
List views require filters, pagination, stable sorting and permission-scoped fields. Detail context exposes identifiers, labels, timestamps, actor display names, stage/health projections, quantities with units, linked records, allowed-command hints and version/ETag. Dashboard counts, age, percentages, expected dates, thresholds, costs and exceptions are authoritative server projections.

The Batch Workspace projection composes separately paginated/limited Task, Labour, Input, Expense, Quality, Attachment and Audit summaries. Each child collection carries independent freshness, permission/field-redaction status and continuation metadata. A failure or denial in one collection must not fabricate an empty state for another or make the entire Batch unavailable.

## Command/API boundaries
Future endpoints are command-oriented: receive material, create lot/batch, plan/update/complete task, record activity/observation/loss/input/labour/expense/care/treatment/movement, transition stage, place/release hold, submit/decide review, approve release and attach evidence. Commands validate permission, current state, optimistic version, units, applicable method, required evidence and idempotency key. They return the affected projection and audit reference. Generic PATCH must not bypass state rules.

Completing a Task never synthesizes a LabourRecord, InputUsage, Expense, stage transition or Inventory movement. Recording Labour never calculates payroll. Recording Input usage never deducts stock. Recording an Expense never creates an accounting entry. These require distinct future commands in their owning domains.

## Validation and business rules
Identifiers are server generated. Quantities are positive decimals with configured units; corrections are compensating records. Source use must be traceable and method-compatible. Germination is nullable/not applicable outside relevant methods. Treatments require product, purpose, rate/unit, applicator, timing and applicable safety data. Quality release requires review, no active blocking hold, accepted quantity/grade and authorised approval. Task completion never implies another command.

## Permissions and side effects
Canonical capabilities are defined in `docs/architecture/permissions.md`. The catalogue must refine separate recording capabilities for tasks, labour, inputs, expenses and attachments before backend implementation; provisional names in older Phase 3 documents are aliases only. Every command appends audit history and may emit domain events/notifications. Only Inventory consumes `production.released`; Production never changes stock. No Procurement, Accounting, Order, Fulfillment, Payment or POS lifecycle is mutated.

## Page context
All pages receive `state_mode` and URL batch identifier only in this frontend milestone; the displayed workspace records remain static fixtures. Future views add paginated projections, filters, capabilities, freshness metadata and configuration (units, methods, locations, thresholds). No template receives secrets or unrestricted personal data.
