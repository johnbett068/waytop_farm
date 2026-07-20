# Staff Order Management flow

## Purpose

Define the staff journey from order discovery to domain-owned operational decisions while preserving independent lifecycles.

## Primary journey

Dashboard Order Widget → Order List → search/filter → Order Detail → inspect composed lifecycles → choose permitted domain action → confirmation/reason → owning service command → append state/audit event → refresh composed read projection.

Phase 3B stops at confirmation preview and performs no command.

## Canonical lifecycles

- **Order:** New → Under Review → Accepted → Processing → Completed; alternative Cancelled.
- **Fulfillment:** Awaiting Feasibility Check → Ready for Assignment → Assigned → Picking/Preparing → Fulfillment Quality Check → Ready for Pickup/Dispatch → Collected/Delivered.
- **Payment:** Pending → Confirmed or Failed; Refund Requested → Refund Pending → Refunded is represented by dedicated Refund records/events rather than overwriting the original payment.
- **Return:** Requested → Authorised → Received → Inspected → Resolved.
- **Production:** canonical Phase 3A propagation lifecycle; never advanced by Order/Fulfillment.

## Availability / Feasibility

Fulfillment requests a read assessment using released Inventory, production forecasts and incoming batches. The result may be feasible, partially feasible, delayed, or unavailable with timestamp/reasons. It informs Fulfillment planning only. It never reserves stock, changes Production, or changes Order automatically.

## Partial-operation flows

- **Partial fulfillment:** Order Items remain immutable; one/more Fulfillments and Fulfillment Lines cover quantities. Unfulfilled quantity remains explicit.
- **Multiple delivery:** Delivery records belong to Fulfillment and carry separate windows/status/events.
- **Split payment:** Payment Allocations sum toward Order amount; payment attempts retain provider history.
- **Partial refund:** Refund/Refund Allocation references eligible payment/order-line quantities and never edits original tender facts.
- **Partial return:** Return Lines reference delivered quantities; inspection determines disposition and resulting Inventory/reversal commands.

Order can remain Processing while partial operations continue and becomes Completed only under explicit completion policy.

## Quick Action ownership

Assign/prepare/quality/ready/collection/delivery are Fulfillment commands. Cancel is an Order command with policy checks. Request Refund creates a Refund lifecycle command. Picking List is a Fulfillment read document; Receipt is a financial/customer document. UI never chains implicit cross-domain transitions.

## Timeline and activity

The operational timeline orders permission-safe events from multiple domains and displays time, staff/service actor, action, owning status and comments with Completed, Current, Pending, Cancelled and Exception styling. It is a read projection, not a persisted universal lifecycle. Activity history is not the immutable Audit ledger; it links to audit references in production.

## States and permissions

Loading, empty/filter-empty, error, permission, offline and success apply to list/detail. Future commands require action/object permissions, current version, CSRF, reason and audit metadata. Offline commands are prohibited. Staff-only notes/assignment/customer data do not cross into customer tracking.

## Backend contracts, models and business rules

Contracts/models follow `docs/contracts/order-management.md` and the frontend specification. Inventory changes only through movements; financial facts are immutable; returns/refunds reverse through owned lifecycles; every transition is independently audited.

## Definition of Done

Discovery, detail, feasibility, quick-action ownership, partial operations, timelines, states, permissions, model boundaries and audit handoff are fully specified without backend mutation.
