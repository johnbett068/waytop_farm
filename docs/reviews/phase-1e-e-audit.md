# Phase 1E-E Commitment supply implementation review

Status: **Complete within ratified Phase 1E-E scope**
Reviewed: 20 August 2026

## Repository findings and ratification

The pre-implementation audit correctly stopped on undefined partial multi-source consumption,
cross-domain authorization and Order-state wording. Chief Engineer decisions D01-D14 resolved those
gates without changing the wider architecture:

- consume active Allocations by creation/authorization time, then Allocation UUID;
- accept only the requested whole commercial quantity and derive exact base quantity;
- authorize authenticated active staff through `inventory.release`, preserving Django's standard
  permission and superuser behavior; and
- leave existing CONFIRMED/PROCESSING Order state and Payment state unchanged.

The existing Inventory Item lock root, movement service, Commitment quantity equations,
Reservation/Allocation current-state counters, idempotency convention and availability calculation
were reusable. No parallel mutation, authorization or availability mechanism was introduced.

## Files

Added:

- `apps/commitments/migrations/0002_commitmentsupplyevent.py`
- `apps/commitments/supply.py`
- `apps/commitments/test_supply.py`
- `apps/inventory/migrations/0003_alter_sourceallocationoperation_kind_and_more.py`
- `docs/reviews/phase-1e-e-audit.md`

Changed:

- `apps/commitments/models.py`
- `apps/commitments/admin.py`
- `apps/inventory/models.py`
- `apps/inventory/admin.py`
- `docs/architecture/availability-commitment-contract.md`
- `docs/reviews/phase-1e-e-decision-gate.md`

No file was removed and no earlier migration was changed.

## Persistence and history

`CommitmentSupplyEvent` is immutable append-only evidence for one physical supply. It protects and
records the Commitment, exact whole commercial and `Decimal(32,3)` base quantities, previous/new
Commitment state, actor, server time, reason, source/reference, correlation and idempotency identity,
request fingerprint, and a unique protected Inventory ISSUE reference. Checks enforce positive
quantities and non-empty audit fields; model validation enforces the immutable Commitment conversion
and ISSUE movement type.

`SourceAllocationOperation.Kind.CONSUMPTION` extends the existing allocation-operation history.
`SourceAllocationConsumption` appends each exact Allocation quantity consumed by that operation and
links it to the supply event. Operation/allocation and event/Commitment ownership are validated;
positive quantity, unique operation line and unique allocation per operation are database-enforced.
Consumption facts and Supply Events reject ordinary update, delete and bulk mutation.

Reservation and Source Allocation current-state rows retain their existing initial, consumed,
released and remaining equations. Their immutable identity/source/initial facts are not rewritten.

## Atomic supply service

`supply_ready_commitment()` owns one `transaction.atomic()` boundary. It:

1. authorizes `inventory.release`;
2. normalizes UUID/audit/idempotency input and a positive whole commercial quantity;
3. rejects PRE_ORDER before mutation;
4. locks the Inventory Item mutation root, Commitment, stable-ID Position rows, Reservation and
   Allocation rows;
5. validates READY mode, CONFIRMED/PROCESSING Order, ACTIVE outstanding Commitment, ACTIVE
   Reservation, matching Reservation/Allocation totals and sufficient eligible allocated quantity;
6. derives exact base quantity from the immutable Commitment conversion;
7. builds the mandatory plan by Allocation creation time then UUID, without caller source input;
8. validates each affected Position has sufficient eligible physical quantity;
9. calls the existing idempotent Inventory movement service for one ISSUE;
10. updates Allocation and Reservation consumed/remaining counters, transitioning Reservation to
    CONSUMED only at zero remaining;
11. appends Allocation consumption, Reservation consumption and Commitment supply history; and
12. updates Commitment supplied/outstanding counters, transitioning it to SATISFIED only at zero.

Any validation or write failure rolls back the ISSUE and all ledgers. The service never creates or
reallocates supply, makes a FIFO decision, directly edits Stock Positions, or changes Order/Payment.

## Idempotency, availability and permissions

One idempotency key and correlation identity are shared by the supply event, ISSUE, Reservation
event and Allocation operation. A SHA-256 request fingerprint covers Commitment, commercial
quantity, actor and audit identity. An identical retry returns the prior Supply Event before any
mutation. Changed reuse or collision with another domain operation is rejected. The unique ISSUE
relationship prevents one movement from supporting multiple supply events.

Supply requires authenticated, active staff with `inventory.release`. `commitments.allocate` is not
required and no new permission was created. Standard Django `has_perm()` behavior is preserved, so
an active superuser satisfies the capability normally. Admin registrations use the existing
`commitments.view` read-only, non-destructive boundary.

After supply, eligible physical on-hand and active Reservation remaining decrease by the same exact
base quantity. Aggregate READY availability therefore remains consistent without subtracting
Commitments, Allocations or supplied quantity separately.

## Tests and verification

- Phase 1E-E focused suite: 15 passed.
- Inventory suite: 61 passed.
- Commitment suite, including Phase 1E-E: 38 passed.
- Combined Inventory/Commitment suite: 99 passed.
- Order/Payment regression suite: 30 passed.
- Full Django suite: 210 passed.
- Django system check: no issues (0 silenced).
- Migration drift: no changes detected.
- `git diff --check`: passed; existing line-ending conversion warnings only.
- Both new migrations applied successfully on clean isolated test databases.
- Migration inspection found schema operations only and no `RunPython`/`RunSQL` data operation.
- Development `db.sqlite3`: zero bytes.

Coverage includes full and partial single-source supply; sequential multi-source crossing;
creation-time and UUID ordering; no caller split; exact conversion and equations; ACTIVE/CONSUMED
Reservation transitions; ACTIVE/SATISFIED Commitment transitions; released/PRE_ORDER/invalid/excess
rejection; insufficient eligible Allocation and physical Position rollback; exact ISSUE and Position
reduction; append-only history; complete retry deduplication and changed-key rejection; anonymous,
inactive and unauthorized denial; authorized staff and native superuser success; unchanged
Order/Payment state; stable availability; and absence of confirmation, Production and customer-source
surfaces.

## Deferred boundaries, data and next phase

No Payment verification/confirmation, Order confirmation/transition/cancellation, Reservation
release/transfer/expiry, source reallocation during supply, PRE_ORDER/Production capacity,
Fulfillment/Delivery/tracking, adjustment approval, returns/refunds, customer source disclosure or
frontend workflow was implemented.

No runtime fixture, demo supply, fabricated stock, Order or Commitment was added. Tests use isolated
test databases and the development database remained untouched.

PostgreSQL is not configured. SQLite verifies ordinary service invariants and rollback but is not
concurrency proof; PostgreSQL competing-transaction verification remains an explicit
environment-dependent gap and no such guarantee is claimed.

There are no architectural deviations and no remaining blocker within ratified Phase 1E-E. The
exact next architectural gate is **Phase 1F: Atomic Payment Verification + Order Confirmation**,
which must not start until its final contract and all prerequisites are independently verified.
