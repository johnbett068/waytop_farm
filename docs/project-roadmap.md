# WayTop Farm Project Roadmap

> **HISTORICAL / SUPERSEDED STATUS SNAPSHOT.** This frontend-era roadmap is not current Phase 1
> implementation authority. See [Documentation Authority](document-authority.md).

## Current status

Phase 4B Delivery & Fulfillment frontend is complete as an executable specification. Delivery, POS, Inventory and Procurement persistence remain unimplemented.

| Phase | Milestone | Status |
|---|---|---|
| Phase 1A | Foundation milestone | Complete |
| Phase 1B | Foundation milestone | Complete |
| Phase 1C | Foundation milestone | Complete |
| Phase 1D | Foundation milestone | Complete |
| Phase 2A | Premium Checkout Experience | Complete |
| Phase 2B | Order Confirmation and Order Tracking | Complete |
| Phase 3A | Staff Operations Foundation | Complete |
| Phase 3B | Order Management | Complete |
| Phase 3C | Production Management | Complete |
| Phase 3C.5 | Identity, Roles, Permissions & Delegation Architecture | Complete |
| Phase 3C.6 | Production Workspace | Complete |
| Phase 3C.7 | Inventory Domain Architecture | **Complete — Current Pause Point (Architecture Only)** |
| Phase 3D | Inventory Management Frontend | **Complete — Frontend Only** |
| Phase 3E | Procurement & Supplier Management Frontend | **Complete — Frontend Only** |
| Phase 4A | Point of Sale Frontend | **Complete — Frontend Only** |
| Phase 4B | Delivery & Fulfillment Frontend | **Complete — Frontend Only** |

## Pause gate

- Do not begin Inventory or Procurement backend implementation without a separate approved milestone.
- Phase 3D created frontend routes, templates, mock projections, capability simulation, styles, scripts, tests and documentation only; it created no Inventory model, migration, API, movement, deduction, procurement, accounting, report engine or calculation.
- Backend work must not begin until the project owner approves the Phase 3C.7 item/location taxonomy, units/tracking controls, transaction reasons, negative-stock policy, opening-balance cutover, reservation semantics, approvals and integration decisions listed in its audit.
- Phase 3C.5 authorization governance and Phase 3C.6 Production boundaries remain mandatory dependencies.
- Completion of the Phase 3D frontend is not approval to implement Inventory persistence.
- Completion of the Phase 3E frontend is not approval to implement Procurement, Inventory receipt integration or Accounting.
- Completion of the Phase 4A frontend is not approval to implement sales, payments, register posting, Inventory deductions, Accounting, returns or receipt generation.
- Phase 4A parked carts do not reserve Inventory. Future sale, payment, Inventory and Accounting outcomes must remain independently owned and correlation-driven.
- Completion of Phase 4B is not approval to implement Delivery/Fulfillment persistence, GPS, routes, driver/vehicle management, stock changes, payments or Accounting.
- Phase 4B tracks customer handover progress only. WayTop transport remains manually arranged and Fulfillment, Order, Inventory, Payment and Accounting ownership stays independent.
- Resume only through a separately approved milestone with the implementation boundary stated explicitly.
