# Delivery & Fulfillment frontend

## Scope

Phase 4B is a frontend-only executable specification for tracking home delivery and customer pickup. WayTop arranges transport manually with customers and external providers. The module records process evidence; it is not a transport or logistics management system.

## Routes

| Route | Purpose |
|---|---|
| `/dashboard/delivery/` | Queues, daily activity and capability-filtered quick actions |
| `/dashboard/delivery/jobs/` | Searchable mock job register with delivery/order/customer fields |
| `/dashboard/delivery/jobs/<number>/` | Confirmation, checklist, dispatch, completion, failure, pickup and activity workspace |

## Interaction and states

Search filters local mock job rows. Confirmation, dispatch, delivered, failed and collected controls show transient preview feedback only. Loading, empty, permission, offline, error and success states can be exercised with `?state=<state>`.

The simulator uses canonical Fulfillment capability arrays. Operations can see mock action controls; Sales and Inventory examples can view progress; the Administrator example has configuration context but no operational access. This is presentation scaffolding, not authentication or enforcement.

## Responsive and accessible behavior

Desktop dashboards use metrics and two-column workspaces. Tablet layouts collapse panels while preserving reading order. Mobile layouts use single-column forms, vertically presented lifecycle progress, horizontally scrollable tables/navigation, touch-sized controls, explicit labels and text-plus-color states. Live regions announce simulator and placeholder feedback.

## Explicit exclusions

No backend, persistence, GPS, route optimization, driver/vehicle registry, assignment, fuel, delivery-cost calculation, payment, Inventory reservation/deduction, Accounting or external communication is implemented.
