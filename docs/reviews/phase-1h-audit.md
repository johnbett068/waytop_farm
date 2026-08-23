# Phase 1H — Continuous PostgreSQL and Boundary Hardening Audit

Audit date: 22 August 2026
Authority: Phase 1H directive and owner route ratification
Status: **BLOCKED — HOSTED CI ACTIVATION PENDING**

## 1. Outcome

The seven informational routes H-R01 through H-R07 are DEFERRED and outside current product
scope. No page, template, redirect, fixture, demo data, route, navigation item or business behavior
was added. Because no exact 404/410 retirement policy was ratified, their runtime behavior remains
unchanged. Route-integrity tests now preserve that boundary.

All other authorized Phase 1H implementation items are complete and locally verified. The only
external closure action is configuring the GitHub repository secret `POSTGRES_TEST_PASSWORD` and
observing the first hosted workflow run.

## 2. PostgreSQL CI and infrastructure

`.github/workflows/postgresql.yml` adds a PostgreSQL 18 job with:

- an external repository-secret password and an explicit non-empty credential check;
- distinct control (`waytop_ci_control`) and disposable test (`waytop_ci_test`) databases;
- no SQLite fallback for concurrency evidence;
- 15-second lock and 60-second statement timeouts plus a 20-minute job timeout;
- dependency integrity, migration drift, Django system and production-shaped deployment checks;
- a 258-test non-concurrency partition and a separately asserted 9-test PostgreSQL concurrency
  partition, totaling the complete 267-test suite without the monolithic runner-order stall.

`docs/deployment-configuration.md` records the required secret and the nine-test concurrency gate.

## 3. Cross-root idempotency race hardening

`apps/core/idempotency.py` validates UUID keys, requires an active atomic transaction and, only on
PostgreSQL, takes a transaction-scoped advisory lock derived deterministically from the complete
UUID. SQLite remains a no-op regression backend and is not concurrency evidence.

Every current idempotent command acquires this key lock before aggregate/root row locks: Order
creation, rejected and accepted Payment verification, Inventory movement, Commitment creation,
Reservation/allocation, Commitment supply, Order cancellation, Order processing and Fulfillment
completion. Payment evidence submission intentionally remains repeatable evidence without an
idempotency key. Existing per-operation fingerprints and collision rules remain unchanged; no new
global cross-domain key namespace was invented.

New PostgreSQL tests prove same-request concurrent Order creation converges to one Order,
changed-request reuse produces one success and one domain rejection rather than an integrity
error, and one confirmation key used against different Payment roots has one winner.

## 4. Initial-event enforcement

Initial status/event creation now goes through explicit service-write flags. Database constraints
enforce one initial Order status event, Payment status event, Commitment event, Reservation CREATED
event and Allocation INITIAL operation per aggregate, plus the ratified transition shapes.
Commitment, Reservation and Allocation initial history also validates the aggregate's creation
identity and quantities. Rejected Payment verification attempts now require their authorized
service path just as approvals already did.

Four additive migrations install these constraints. Migration autodetection reports no further
changes and all migrations applied successfully on fresh PostgreSQL 18.4.

## 5. Documentation authority

`docs/document-authority.md` defines AUTHORITATIVE, IMPLEMENTATION STATUS, DECISION GATE,
HISTORICAL/SUPERSEDED and DEFERRED markers and the current hierarchy. Prominent markers were added
to the Inventory/permissions architecture, Production contract/flow, governance and roadmap
documents. Historical material was preserved; no contract was rewritten to change behavior.

## 6. Route integrity

`apps/core/test_phase1h_routes.py` asserts that all seven deferred URLs still resolve to their
existing view wiring, that their unratified templates remain absent, and that no route name or
literal path appears in active navbar/footer surfaces. This intentionally documents deferral rather
than converting a broken scaffold into a fabricated 200, redirect, 404 or 410 policy.

## 7. Files added

- `.github/workflows/postgresql.yml`
- `apps/core/idempotency.py`
- `apps/core/test_phase1h_routes.py`
- `apps/orders/migrations/0004_order_status_event_constraints.py`
- `apps/payments/migrations/0003_payment_status_event_constraints.py`
- `apps/commitments/migrations/0003_commitmentevent_initial_history_constraints.py`
- `apps/inventory/migrations/0005_initial_history_constraints.py`
- `docs/document-authority.md`

## 8. Files changed

- `apps/orders/models.py`, `apps/orders/services.py`, `apps/orders/lifecycle.py`,
  `apps/orders/tests.py`, `apps/orders/test_postgresql_concurrency.py`
- `apps/payments/models.py`, `apps/payments/services.py`, `apps/payments/confirmation.py`,
  `apps/payments/tests.py`
- `apps/inventory/models.py`, `apps/inventory/services.py`, `apps/inventory/reservations.py`,
  `apps/inventory/test_reservations.py`
- `apps/commitments/models.py`, `apps/commitments/services.py`, `apps/commitments/supply.py`,
  `apps/commitments/tests.py`
- `apps/fulfillment/services.py`
- `docs/deployment-configuration.md`, `docs/architecture/inventory-domain.md`,
  `docs/architecture/permissions.md`, `docs/contracts/production.md`,
  `docs/flows/production-lifecycle.md`, `docs/project-governance.md`,
  `docs/project-roadmap.md`, `docs/reviews/phase-1h-route-decision-gate.md`, and this audit.

## 9. Files removed

None.

## 10. Business rules

None changed. The authoritative READY lifecycle, permissions, confirmation, Inventory,
Commitment, Reservation, Allocation, Supply, Fulfillment, Processing, Cancellation, Availability
and FIFO semantics are unchanged. Production/PRE_ORDER and all seven informational capabilities
remain unavailable/deferred.

## 11. Verification results

- Focused Phase 1H regression: 80 discovered, 80 passed, 0 skipped, 0 failed, 0 errors in
  55.085s.
- Complete SQLite regression: 267 discovered, 267 passed, with the 9 PostgreSQL-only tests skipped,
  in 262.182s.
- PostgreSQL concurrency: 9 discovered, 9 passed, 0 skipped in 69.018s. This includes all six
  retained baseline scenarios plus three Phase 1H cross-root scenarios.
- PostgreSQL non-concurrency partition: 258 discovered, 258 passed, 0 skipped in 378.474s.
- Complete PostgreSQL coverage: 267/267 passed across the two deliberate CI partitions.
- Django system check: zero issues.
- Production-shaped `check --deploy`: zero issues with process-local generated secrets.
- `makemigrations --check --dry-run`: no changes detected.
- `pip check`: no broken requirements found.
- `git diff --check`: passed.
- Development `db.sqlite3`: untouched and remains zero bytes.

The first monolithic PostgreSQL invocation exceeded its bounded 420-second runner window without a
test failure. The tag-based partition is now the CI contract: it covers all 267 tests exactly and
keeps concurrency results explicit. Expected constraint-violation log entries came from negative
tests and did not represent failures.

## 12. Remaining blockers and debt

- External activation only: configure `POSTGRES_TEST_PASSWORD` and obtain the first green hosted
  GitHub Actions run. No credential was committed.
- A uniform global cross-domain idempotency namespace remains an unratified policy question;
  Phase 1H hardened concurrent first use without inventing that rule.
- The seven informational routes remain intentionally deferred with unchanged runtime behavior
  until an exact content or retirement/HTTP policy is ratified.
- Broader closure-audit decisions (Production/PRE_ORDER, Delivery, returns/refunds, Payment
  evidence retention, PENDING abandonment and tracking security) remain outside Phase 1H.

## 13. Exact next action

Configure the GitHub repository secret `POSTGRES_TEST_PASSWORD`, run the new PostgreSQL workflow,
and attach its green run as the external CI activation evidence. Only then mark Phase 1H fully
closed or authorize a separately scoped next phase.

**Phase 1H outcome: BLOCKED only on hosted CI activation. Repository implementation and local
PostgreSQL verification are complete.**
