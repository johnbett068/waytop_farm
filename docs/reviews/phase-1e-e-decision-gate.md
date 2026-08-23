# Phase 1E-E supply foundation decision gate

Status: **Resolved by Chief Engineer ratification D01-D14**
Reviewed: 20 August 2026

## Ratification resolution

The original stop was accepted and all three decisions were subsequently ratified:

- active Source Allocations are consumed by creation/authorization sequence ascending, then
  Allocation UUID ascending; the caller cannot submit a split;
- the complete atomic supply command requires authenticated active staff with `inventory.release`,
  using Django's normal permission and superuser behavior; and
- the command accepts only a valid existing READY Commitment on a CONFIRMED or PROCESSING Order and
  leaves the existing Order and Payment states unchanged.

These decisions resolve the stop conditions below and authorize Phase 1E-E implementation. The
sections that follow preserve the original decision-gate reasoning as historical context.

## Scope audited

The implemented Inventory, Commitment, READY Availability, Reservation and Source Allocation
models/services were compared with the canonical V1, Order/Customer/Payment, and
Availability/Commitment contracts and the Phase 1E-A through Phase 1E-D audits. No Phase 1E-E model,
migration, service, permission, test fixture or runtime data was created.

The existing foundations are otherwise composable:

- Commitments store exact whole commercial quantities and `Decimal(32,3)` base quantities with
  database-enforced committed/supplied/cancelled/outstanding equations.
- Reservations and Source Allocations already store consumed and remaining quantities with additive
  equations and controlled service-write paths.
- active Allocation remaining totals are required to equal Reservation remaining quantity;
- `post_inventory_movement()` already supports idempotent ISSUE movements, exact quantities,
  negative-stock rejection, immutable Movement history and nested atomic composition;
- the established mutation lock root is Inventory Item, followed by stable ordered source rows; and
- READY availability subtracts active Reservation remaining quantity only.

## Original mandatory stop condition 1: partial multi-source consumption

The ratified contract permits both of these facts:

1. a Commitment may be supplied through multiple positive whole-sale-unit events; and
2. its Reservation may be split across multiple Location/Lot Source Allocations.

It requires a supply transaction to consume the exact affected Allocations, but does not define how
the affected split is selected. The existing deterministic expiry/Lot/Location/ID order explicitly
governs source selection during allocation; it is not stated as the consumption order.

For example, a one-sale-unit supply requiring `5.000` base units against active allocations of
`3.000` at Lot A and `7.000` at Lot B has at least two materially different valid outcomes:

- issue and consume `3.000` from A plus `2.000` from B; or
- issue and consume `5.000` from B.

Both preserve aggregate equations, but they create different physical Inventory, lot provenance and
cost history. Automatically choosing an allocation order or accepting a caller-selected split would
therefore invent an unratified business rule. This triggers mandatory stop conditions 1 and 7 in the
Phase 1E-E directive.

### Smallest required ratification

Choose exactly one supply-source policy:

- **Deterministic consumption:** consume active allocations in the already-defined source order
  (earliest non-null expiry, null expiry last, Lot creation time, Location code, stable Position ID),
  splitting the supplied base quantity across lines as needed; or
- **Explicit authorized split:** require the supply command to provide exact allocation IDs and base
  quantities, define who may approve that split, and reject anything that does not exactly equal the
  supply event base quantity.

The deterministic option is the smallest extension because it needs no new operator choice and
reuses an existing stable ordering, but the contract must explicitly extend that ordering from
allocation creation to supply consumption before implementation.

## Original mandatory stop condition 2: cross-domain supply permission

The implemented permission catalogue assigns `inventory.release` to governed Inventory ISSUE
posting, `commitments.allocate` to initial allocation/reallocation, and `fulfillment.complete` to a
future completion operation. It does not state which capability authorizes the complete operation
that simultaneously consumes a Commitment, Reservation and Allocations and posts an ISSUE.

Treating `inventory.release` as authority for the entire supply transaction, requiring a combination
of existing permissions, or adding a narrow `commitments.supply` capability would produce different
authorization boundaries. Choosing among them would violate the directive's prohibition on
inventing permissions and triggers mandatory stop condition 5.

### Smallest required ratification

Explicitly designate the permission set for the atomic supply command. The smallest implementation
change would ratify authenticated active staff with `inventory.release` as sufficient authority for
the entire physical supply operation. If separation of duties is required, the contract must instead
name the exact additional permission and whether all named permissions are mandatory.

The directive also says that superuser status alone must not grant supply authority, while the
project currently uses Django's standard `has_perm()` behavior, under which an active superuser has
all permissions. Ratification must clarify whether Phase 1E-E should retain standard Django
superuser semantics or require an explicit direct/group grant for the selected supply permission.

## Original Order-state wording requiring clarification

The Phase 1E-E definition of done says “Order remains PENDING,” while the ratified confirmation
contract and Phase 1E-D Reservation service prohibit Reservations for PENDING Orders. A valid READY
supply candidate must therefore belong to an already CONFIRMED or PROCESSING Order. This phase can
and should leave that existing state unchanged, but it cannot truthfully require a valid supplied
Order to be PENDING.

The smallest clarification is: **“The supply operation never transitions Order state; the existing
CONFIRMED or PROCESSING state remains unchanged.”** Payment state should likewise remain unchanged,
rather than requiring a state inconsistent with the already-confirmed upstream transaction.

## Authorized implementation after ratification

The resolved decisions authorized Phase 1E-E to narrowly add:

- immutable `CommitmentSupplyEvent` persistence referencing its Commitment and Inventory ISSUE;
- append-only per-Allocation consumption facts linked to the Supply Event where needed for exact
  Location/Lot history;
- one idempotent atomic READY supply service that locks the Inventory Item supply pool and related
  Commitment/Reservation/Allocation/Position rows in the established deterministic order;
- nested use of `post_inventory_movement()` for the exact ISSUE;
- controlled counter/state transitions for Allocations, Reservation and Commitment; and
- focused invariant, rollback, idempotency, permission, privacy and boundary tests.

No Order, Payment, confirmation, cancellation, release, Production, Fulfillment, Delivery, return or
customer-facing behavior is needed.

## Decision-gate outcome

- Source/schema implementation: authorized after ratification; recorded in the separate Phase 1E-E
  implementation audit.
- New migrations: only the new Phase 1E-E schema migrations; earlier migrations remain unchanged.
- Existing migrations rewritten: none.
- Runtime/demo data: none.
- Development `db.sqlite3`: remains zero bytes.
- PostgreSQL: not configured and no concurrency claim is made.

The decision gate is resolved. Completion evidence and the exact next phase are recorded in the
Phase 1E-E implementation audit.
