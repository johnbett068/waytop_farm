# Phase 1G decision record — entry into PROCESSING

Status: **Ratified and implemented**

Ratified: 21 August 2026 under Phase 1G-Final

## Ratified decision

The Order lifecycle remains `PENDING -> CONFIRMED -> PROCESSING -> FULFILLED`. Phase 1F atomic
confirmation ends at CONFIRMED. Entry into PROCESSING is a separate, deliberate staff command and
means that fulfillment work has explicitly started.

### A. Authority

`start_order_processing()` requires an authenticated, active staff actor with the native Django
permission `orders.process`. Permission checks use normal Django `has_perm()` behavior, including
standard superuser semantics. No role-name check is used.

### B. Trigger

Only an explicit call to `start_order_processing()` triggers `CONFIRMED -> PROCESSING`. Payment
verification, confirmation, Inventory, Reservation, Allocation, supply and fulfillment operations
do not trigger it automatically. No signal, timer, route or UI is introduced.

### C. Prerequisites

The locked Order must be CONFIRMED, its Payment must be CONFIRMED, and all Order Lines must be
READY. Every line must have its matching Commitment, Reservation and Allocation structure. Their
existing identity, state, conversion and quantity equations must remain valid, with no cancelled
or released active supply accepted. Already-supplied quantities are valid when the remaining
structure still agrees.

Validation is read-only: the command does not select, repair, consume, release or otherwise mutate
Payment or supply records.

### D. Idempotency and concurrency

The command requires a correlation ID, unique idempotency key and non-empty reason. The Order row
is locked first. An equivalent same-key retry returns the original result and appends nothing. A
same-key request with changed Order, actor, correlation ID or reason is rejected. A different key
after success is an invalid transition. The Order state and event share one atomic transaction.

### E. Audit and side effects

Success changes only Order status and appends exactly one immutable `OrderStatusEvent` containing
`CONFIRMED -> PROCESSING`, actor, server timestamp, normalized reason, correlation ID and
idempotency key. Payment, Customer, Inventory, Commitment, Reservation, Allocation, supply and
fulfillment facts remain unchanged.

## Scope

`PENDING`, `CANCELLED` and `FULFILLED` cannot enter PROCESSING. An already-PROCESSING Order accepts
only an equivalent retry. This decision introduces no new Order state, API, UI, public tracking,
Branch or logistics behavior.
