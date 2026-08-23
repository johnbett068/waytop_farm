# WayTop Farm Documentation Authority Index

Status: **IMPLEMENTATION STATUS — CURRENT CLASSIFICATION INDEX**
Updated: 21 August 2026

This index classifies documentation; it does not change business behavior or rewrite historical
decisions. When prose conflicts, use the highest applicable authority below and then the most recent
ratified refinement within that scope.

## Marker convention

- **AUTHORITATIVE:** ratified business contract currently controlling implementation.
- **IMPLEMENTATION STATUS:** evidence of what code/tests implement; not authority to invent rules.
- **DECISION GATE:** an unresolved question or a retained record of its ratification.
- **HISTORICAL / SUPERSEDED:** preserved provenance that cannot authorize current V1 behavior.
- **DEFERRED:** future scope that has no current implementation authority.

## AUTHORITATIVE

1. `architecture/v1-business-contract.md` — cross-domain V1 authority.
2. `architecture/order-customer-payment-contract.md` — Customer, Order, Payment and minimal
   Fulfillment refinement.
3. `architecture/availability-commitment-contract.md` — Inventory, READY Availability,
   Commitment, Reservation, Allocation, Supply and concurrency refinement.
4. Ratified decision records, including `reviews/phase-1e-e-decision-gate.md` and
   `reviews/phase-1g-processing-decision-gate.md`, only within their stated scope.

The READY lifecycle is `PENDING -> CONFIRMED -> PROCESSING -> FULFILLED`; cancellation is permitted
only from CONFIRMED or PROCESSING. Cash on Pickup, customer Branch/source selection and the older
reservation-before-allocation flow are not current V1 rules.

## IMPLEMENTATION STATUS

- `reviews/phase-1d-audit.md` through `reviews/phase-1g-final-audit.md` record staged implementation
  at their dates; later stage records supersede earlier availability lists.
- `reviews/post-phase-1g-system-audit.md`, `reviews/post-phase-1g-hardening-audit.md` section 23,
  `reviews/post-phase-1-closure-audit.md` and `reviews/phase-1h-audit.md` are current synthesis and
  verification evidence.
- An audit never overrides a ratified contract unless it embeds an explicitly ratified decision.

## DECISION GATES

- Resolved gates remain in `reviews/` as decision history and must be read with their status line.
- `reviews/phase-1h-route-decision-gate.md` records the ratified DEFER disposition for seven
  informational routes; it authorizes no page content or redirect.
- Open product decisions remain listed in the Post-Phase-1 Closure Audit.

## HISTORICAL / SUPERSEDED

- `architecture/operations.md`, `architecture/state-machines.md`, `architecture/business-domains.md`
  and `architecture/inventory-domain.md` are prototype/future architecture where they conflict with
  the ratified V1 contracts.
- older Checkout, Order Management, Order Tracking, POS and Delivery contracts/flows are retained
  UI/future design evidence, not current backend authority.
- Phase 2 through Phase 4 reviews describe frontend prototypes/executable specifications, not
  persisted domain completion.
- `cto-engineering-audit.md` is a historical repository snapshot from before Phase 1 persistence.

## DEFERRED

- Production, Procurement, detailed Delivery, Tracking, Return, Refund and other future contracts,
  flows and frontend documents remain planning inputs only.
- `contracts/production.md` and `flows/production-lifecycle.md` do not authorize Production or
  PRE_ORDER implementation.
- `architecture/permissions.md`, roles, scopes, delegation and separation-of-duties documents are a
  future catalogue except for permissions actually installed and required by ratified Phase 1
  services.
- About, FAQ, Branches, Blog, Blog Article, Reviews and Contact are outside current product scope.

Historical files must not be deleted merely because they are superseded. Add or correct a prominent
marker if a document's classification changes; change ratified behavior only through a new explicit
decision record.
