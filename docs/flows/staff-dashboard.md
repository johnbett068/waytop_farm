# Staff dashboard workflow

> **Superseded for V1 where conflicting.** Daily Handover, deep Procurement, and detailed Delivery are not active workflows. See the [ratified V1 business contract](../architecture/v1-business-contract.md).

## Purpose

Define how a future authorised staff member moves from operational awareness to a domain-owned decision without using the dashboard as a generic mutation layer.

## Primary flow

Open Dashboard → permission-filtered projection loads → scan overview → triage critical/overdue exceptions → open source domain record → validate evidence/current version → perform authorised command → domain event/audit record → refreshed projection.

Phase 3A stops at the preview/navigation boundary; review/action controls are disabled.

## Daily triage sequence

1. Review customer commitments: received orders, payment exceptions and fulfillment assignment age.
2. Review propagation/quality exceptions: mortality, establishment/germination where applicable, delayed growth, overdue hardening, quality holds and release queue.
3. Review inputs/inventory: shortages, transfers, movement-posting exceptions and counts—not editable balances.
4. Confirm task ownership and deadlines.
5. Review recent customer-relevant and audit-aware events.
6. Handover unresolved exceptions with owner and next decision; task completion never substitutes for domain transition.

## Alternate states

- Loading announces projection preparation.
- Empty suggests filter/date change without implying deleted history.
- Widget/system error preserves other data and states that no record changed.
- Permission denial exposes neither data nor actions.
- Offline identifies stale information and blocks consequential commands.
- Notifications open in a keyboard-managed drawer; confirmation preview opens a native modal and returns focus.
- Narrow screens use a dismissible navigation overlay and scroll-contained tables.

## Displayed information and actions

Information and future actions follow `staff-dashboard.md`. Search, filter and pagination are component contracts. Future search results are role-filtered server-side. Quick Actions are capability-filtered and navigate to structured workflows rather than posting from the homepage.

## Permissions, models and backend contracts

Accounts authorises dashboard and widget reads. Order, Fulfillment, Production, Inventory, Notifications and Audit services provide timestamped read projections. Commands occur only in owning modules with CSRF, object permission, optimistic concurrency/idempotency and reason/audit metadata. Internal branch/area information is valid only in authorised staff projections and never leaks into customer contracts.

## Business rules

Exception severity comes from versioned policies. Metrics have definitions and drill-down parity. Independent status lifecycles remain visible. Production release and inventory posting are separate permissioned events. Financial and stock facts are immutable ledger records.

## Definition of Done

Primary/alternate flow, triage priority, responsive navigation, focus behavior, permissions, query/command separation, future models, states, audit implications and no-backend boundary are documented.
