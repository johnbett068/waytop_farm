# Phase 2 Operations Dashboard Design Gate

Status: **IMPLEMENTATION SCOPE — AUTHORITY-SUPPORTED**
Date: 28 August 2026

## Authority

This design is governed by the documentation authority index, the ratified V1 Business,
Order/Customer/Payment and Availability/Commitment contracts, the ratified Supply and Processing
decisions, and the deployment policy. It changes no lifecycle, quantity, permission, availability,
FIFO, allocation, supply, cancellation, fulfillment or privacy rule.

## Existing dashboard

The Operations route is `/dashboard/`. It is served by `apps.dashboard.views.dashboard`, is linked
from the staff navigation, and currently renders an authoritative empty state for authenticated
active staff. The retained `dashboard/dashboard.html` is a disconnected prototype containing mock
metrics and activity and is not an authoritative data source.

## Audience and permissions

Operations shell access retains the existing authenticated active-staff boundary. Operational
sections require their existing read-equivalent capabilities:

- `orders.view` for Order state and lifecycle activity;
- `payments.verify` for Payment state and verification activity, matching existing Payment admin
  visibility;
- `commitments.view` for Commitments, Reservations, allocation operations and supply activity;
- `inventory.view` for Inventory items, Stock Positions and movement activity;
- `fulfillment.complete` for Fulfillment completions, matching existing Fulfillment admin
  visibility.

Sections are independently permission-filtered. Active staff without one of these permissions see
the truthful empty projection and no operational records. No new permission or role-name rule is
introduced; normal Django superuser semantics remain.

## Authoritative projections

- Order counts by persisted lifecycle state and recent `OrderStatusEvent` records.
- Payment counts by persisted state, verification-attempt outcome counts, and recent
  `PaymentStatusEvent` / verification-attempt records.
- Commitment and Reservation counts by persisted state, plus recent `CommitmentEvent`,
  `CommitmentSupplyEvent`, `ReservationEvent`, and `SourceAllocationOperation` records.
- Inventory Item count, positive Stock Position count, movement/ISSUE counts, and recent
  `InventoryMovement` records.
- Fulfillment Completion count and recent completion records.

The recent activity feed is an in-memory chronological merge of bounded read-only queries. It does
not create a unified persisted event or operational state.

## Unsupported projections

The dashboard will not show global commercial/base quantity totals because heterogeneous sale units
and product base units cannot be truthfully summed. READY availability remains product-and-sale-unit
specific and is not generalized. Revenue, performance, risk, health, SLA, ETA, Production capacity,
PRE_ORDER, forecasts, alerts, source allocation detail, FIFO position, customer details, actor
identity, Payment evidence and provider references remain absent.

## Query and performance boundary

`apps.dashboard.queries` will own deterministic presentation-neutral read projections. It will use
database aggregation, bounded ordered event queries and `select_related` only where an authorized
object reference is needed. It will perform no writes and call no command service. No schema or
index change is required.

## Empty-state rule

When no records exist in the viewer's authorized domains, the dashboard continues to state that no
operational data exists. It renders no fabricated zero cards or activity. When some records exist,
all displayed counts and activity items come directly from persisted records.
