# Production Lifecycle

> **DEFERRED.** Planning context only; not authority to implement Production, capacity, PRE_ORDER or
> Inventory behavior. See [Documentation Authority](../document-authority.md).

## Canonical flow
`Material Receipt → Source Lot → Production Batch → Propagation Activity → Establishment → Growing → Hardening → Quality Review → Released for Sale → Inventory Movement`

This is a cross-aggregate business flow, not one overloaded status field. Inventory owns physical material receipt; Production owns linked acceptance and source-lot traceability. A production batch owns plant WIP from its creation through release. Inventory Movement is an Inventory-owned downstream handoff.

## Method-neutral operation
A batch declares a propagation method and links whichever source lots are applicable: seed; rootstock and scion; cutting; division; tissue-culture material; or a future configured method. Germination applies only when relevant. Establishment and survival rules are method-aware. The canonical later stages remain common without forcing irrelevant observations.

## Stage decisions
Each transition is an explicit command with actor, time, reason, eligibility result and audit event. Propagation records the actual activity. Establishment and Growing collect observations and losses. Hardening records acclimatisation work. Quality Review records grades, accepted/rejected quantities, holds and evidence. Release requires approval and creates a release event; it does not mutate Inventory.

## Exceptions and partial quantities
Mortality, poor germination/establishment/growth, delay, shortage and quality conditions create exceptions, not automatic transitions. Loss/cull records are append-only and retain reasons/disposition. Quality may release only accepted grades/quantities while rejected or held quantities remain traceable.

## Treatment and safety records
Future fertilizer, chemical and biological application records require batch/location, product/input lot, purpose, rate and unit, applicator, start/time, conditions, safety/re-entry or withholding interval where applicable, evidence and audit identity. Permissions and server validation govern recording; this milestone performs no application or calculation.

## Completion criteria
The flow supports every approved propagation type, preserves source-to-release traceability, separates tasks from stage changes, keeps Production independent, and delegates stock creation solely to an Inventory movement.
