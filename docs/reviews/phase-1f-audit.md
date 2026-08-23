# Phase 1F — Atomic Payment Verification and Order Confirmation audit

Status: **Implemented and verified**
Completed: 20 August 2026

## Exact scope

Phase 1F now provides one internal command, `verify_payment_and_confirm_order`, for complete
READY-only Order confirmation. It records an authorized staff decision over submitted M-Pesa
evidence, establishes a Commitment, Reservation, and complete deterministic Source Allocation for
every Order Line, confirms the Payment, and ends the Order at CONFIRMED. It does not enter
PROCESSING, deduct physical stock, or post an Inventory ISSUE.

PRE_ORDER-only and mixed READY/PRE_ORDER Orders are rejected before an accepted verification is
recorded. Production capacity and every later lifecycle phase remain out of scope.

## Files

Added:

- `apps/payments/confirmation.py`
- `apps/payments/test_confirmation.py`
- `apps/payments/migrations/0002_paymentverificationattempt_provider_reference_and_more.py`

Changed:

- `apps/payments/models.py`
- `apps/payments/services.py`
- `apps/orders/models.py`
- `apps/inventory/models.py`
- `apps/inventory/reservations.py`
- `docs/reviews/phase-1f-audit.md`

Files removed: none.

No route, template, UI, demo data, role name, or new permission was added.

## Migration

Payments migration `0002` adds the accepted canonical provider reference and SHA-256 request
fingerprint to append-only `PaymentVerificationAttempt` history. The complete migration graph was
applied successfully to the isolated Django test database. Migration drift is clean.

The real development `db.sqlite3` was not migrated or populated and remains zero bytes.

## Service and authorization boundary

The public internal boundary is exported from `apps.payments.services`. It requires a normal Django
authenticated, active staff actor with both:

- `payments.verify`
- `commitments.allocate`

There are no role-name checks and Django superuser permission semantics are preserved. No separate
confirmation permission was introduced.

The command must own its runtime transaction boundary. Calling it inside a caller-owned atomic
block is rejected because that would make the ratified durable-verification behavior impossible.

## Verification semantics and history

`PaymentEvidence` remains an untrusted, encrypted, append-only customer submission. An APPROVED
`PaymentVerificationAttempt` means an authorized staff actor reviewed that evidence against the
Order and Payment facts and explicitly accepted a canonical M-Pesa reference. It does not claim an
M-Pesa API lookup or provider-side verification.

The attempt records Payment, evidence, actor, outcome, reason, accepted provider reference,
timestamp, correlation ID, idempotency key, and a request fingerprint. Invalid evidence,
Payment/Order mismatch, wrong amount, unsupported method/currency, PRE_ORDER, mixed supply, and
authorization failures are rejected before accepted history is created.

## Transaction and locking design

The operation has two deliberate units required by ratified decision F04:

1. A short transaction locks Payment then Order, validates the acceptance request, and commits the
   append-only APPROVED verification decision.
2. A separate all-or-nothing confirmation transaction locks Payment, Order, Order Lines, Inventory
   Items in stable UUID order, and eligible Positions in stable primary-key order. It revalidates
   every prerequisite and then composes the existing Commitment and Reservation/Allocation
   services.

The second transaction either commits every READY supply effect plus both state transitions or
rolls all of them back. If availability, FIFO, allocation, an event, or a later write fails, the
Payment and Order remain PENDING and no Commitment, Reservation, or Allocation from that attempt
survives. The already committed APPROVED verification attempt remains truthful history.

PostgreSQL remains the authoritative concurrency environment. The row-lock structure is present,
but PostgreSQL was not configured in this workspace, so competing-transaction behavior is not
claimed as runtime-verified. SQLite tests are correctness tests, not concurrency proof.

## Availability, Commitment, Reservation, and Allocation

READY availability is re-evaluated through the existing Availability service after the inventory
locks are held. Each line then uses the existing Commitment creation service and the existing
automatic Reservation/Source Allocation service; calculations and eligibility rules are not
duplicated.

Commitments preserve the existing FIFO timestamp and monotonic sequence. Reservations remain
complete, ACTIVE, and equal to committed base quantity. Initial Source Allocations cover the full
Reservation and select eligible Location/Lot positions deterministically through the existing
allocation rules. An earlier eligible unreserved READY Commitment blocks a later one.

The Reservation integration received a private lock-aware composition flag so it can validate a
Commitment while its already-locked Order is still PENDING inside the outer confirmation
transaction. Its public behavior still rejects PENDING Orders. A pre-existing FIFO identity
comparison was corrected to compare Reservation commitment IDs with the Commitment primary key.

No on-hand Stock Position quantity is changed and no ISSUE movement is created at confirmation.

## Payment and Order transitions

Only these transitions are written:

- Payment: `PENDING -> CONFIRMED`
- Order: `PENDING -> CONFIRMED`

Payment stores the normalized provider reference, verification actor, and verification timestamp.
Order Lines store confirmed and outstanding quantities equal to their ordered quantities. Matching
append-only Payment and Order status events share the parent correlation ID and actor.

PROCESSING is intentionally not part of Phase 1F.

## Idempotency and rollback

The parent idempotency key identifies the accepted verification and complete confirmation request.
Its SHA-256 fingerprint covers Order, Payment, evidence, accepted reference, actor, correlation ID,
and reason. Per-domain and per-line child keys are deterministic UUIDv5 values derived from that
parent.

An identical retry after failure reuses the accepted verification and reruns all confirmation
revalidation. An identical retry after success verifies the persisted complete result and returns
the same Order without duplicating history or supply records. Changed reuse is rejected.

The confirmed Payment database constraint continues to prevent a canonical M-Pesa reference from
confirming more than one Payment.

## Security and privacy

Raw submitted messages remain encrypted at rest and absent from public/admin rendered output under
the existing evidence boundary. The command returns the Order aggregate, not Location, Lot, Stock
Position, or allocation-source data. Audit records retain internal actor and correlation facts.

## Verification results

- Focused Phase 1F tests: 13 passed.
- Full Django suite: 223 passed.
- `python manage.py check`: passed with no issues.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: passed; only existing line-ending conversion warnings were emitted.
- Isolated migration application: passed through the full graph.
- Development `db.sqlite3`: zero bytes.
- Demo/runtime data: none added.
- PostgreSQL concurrency: unavailable and therefore unverified.

The tests cover successful READY confirmation, both permissions and superuser behavior, inactive
staff, Payment and Order terminal states, supply records and complete allocation, FIFO rejection,
insufficient availability, invalid evidence, amount mismatch, stale states, durable accepted
history, injected rollback after Commitment/Reservation/Allocation/Payment writes, same-key
recovery, completed idempotency, changed-key reuse, provider-reference uniqueness,
PRE_ORDER/mixed rejection, no physical deduction, audit correlation, and privacy.

## Architectural deviations and remaining blockers

There is no deviation from the four Phase 1F ratifications. The only integration extension is the
private Reservation composition path described above; all public Phase 1E invariants remain in
force.

Phase 1F has no remaining implementation blocker. PostgreSQL concurrency verification remains an
environmental verification gap, not an implemented concurrency guarantee.

The exact next lifecycle phase is a separately authorized transition from CONFIRMED to PROCESSING.
Fulfillment, delivery, cancellation, returns/refunds, customer tracking, Production capacity, and
PRE_ORDER fulfillment remain unavailable until their own phases are ratified.
