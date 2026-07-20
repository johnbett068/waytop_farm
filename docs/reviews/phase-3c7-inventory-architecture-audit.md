# Phase 3C.7 Inventory Domain Architecture audit

## Outcome

**Complete — architecture, contracts and UX planning only.** Inventory Phase 3D remains pending. No screen, backend, model, migration, API, calculation, stock movement/deduction, procurement, accounting, report or authentication behavior was created.

## Core decisions

- Inventory is the sole quantity-ledger authority for WayTop stock; all changes are posted immutable movements.
- Catalog identity, Production WIP, Procurement commitments, POS sales, Orders/Fulfillment, Accounting and Reporting remain independent owners.
- WIP is not simultaneously saleable/on-hand Inventory. Production consumption issue and finished-goods receipt are explicit handoffs.
- Inventory Item is a stock definition, not a balance. Lot/location/condition/availability projections derive from ledger facts.
- Categories are a versioned hierarchy; tracking, hazard, expiry, valuation and stock type are independent attributes.
- Real-world areas may be both Inventory Locations and Production Areas, but each classification and boundary remains explicit.
- Availability, condition, custody and lifecycle are orthogonal; no contradictory mega-status enum.
- Receipt, issue, Production consumption/release, transfer, sale/POS issue, return, damage/waste, count variance, adjustment and correction have governed semantics.
- Reservations/allocations affect availability only, not on-hand.
- Transfers use explicit in-transit custody and independent destination acceptance.
- Counts preserve observations and post only independently approved variance movements.
- Costing and Reporting derive from owned facts; neither becomes hidden movement logic.

## Quality gate

- [x] Constitution and existing business-domain/operations architecture reviewed.
- [x] Inventory item inclusion/exclusion and scalable category hierarchy documented.
- [x] Location versus Production Area classification documented.
- [x] Legal title, custody and domain ownership boundaries documented.
- [x] Transaction catalogue includes purpose, owner, endpoints and future implications.
- [x] Canonical ledger, opening/closing projection and immutable audit defined without calculation.
- [x] Production request/issue/use/release/receipt integration is compatible with Phase 3C.6.
- [x] Orders, Fulfillment and POS cannot mutate Inventory.
- [x] Cycle/full count, variance investigation/approval and audit are defined.
- [x] Two-sided branch transfer, transit, acceptance and variance are defined.
- [x] Status extensibility avoids duplicated/contradictory business rules.
- [x] Costing, Procurement, Reporting and future Accounting ownership are explicit.
- [x] Phase 3D UX modules and accessibility/responsive requirements recommended without implementation.
- [x] Canonical capabilities/scopes/separation of duties reused; role-name rules not duplicated.
- [x] Documentation-only file scope verified.

## Risks and required decisions before Phase 3D

Project governance must approve real item/category/location masters; base units and conversion precision; lot/serial/expiry and chemical controls; negative-stock policy; opening-balance cutover; reason/evidence catalogue; reservation/allocation semantics; transfer/count freeze and thresholds; adjustment/write-off approvals; purchase/return integration; valuation method/display; file retention; and export classification.

Phase 3C.7 completion is not authorization to implement Inventory. Phase 3D must begin through a separate approved scope and quality gate.
