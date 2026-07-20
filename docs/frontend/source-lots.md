# Source Lots

## Purpose and displayed data
Source lots preserve the Production traceability and fitness context of propagation material before batch use. The UI displays lot reference, material type, supplier or internal origin, linked Inventory receipt/issue quantity and unit, acceptance date, cost placeholder, quality notes and traceability references. Seed, rootstock, scion and stem-cutting examples prevent seed-only assumptions.

## Actions, states and permissions
Phase 3C permits viewing/filtering only; material acceptance is a disabled preview. Inventory alone receives/issues physical stock. Future Production permissions distinguish inspect, accept fitness, correct traceability metadata, hold and approve. Loading, empty, validation/error, offline, permission and success use the shared production state pattern.

## Backend contract
Future `PropagationMaterialAcceptance` references an Inventory receipt/issue lot and has one or more `SourceLot` traceability records. A source lot has a material type, origin party/internal source, supplier lot reference, linked quantity/unit, acceptance condition, dates, traceability and immutable audit events. `BatchMaterialUsage` links lots to batches; no Inventory quantity mutation is implied by the page.

## Business rules and Definition of Done
Material may be external or internally propagated. Cost is confidential and optional; no value is invented or calculated. Corrections preserve history. Done means method-neutral data, traceable origin/condition, accessible responsive presentation, documented validation and no Inventory receipt, issue or consumption write.
