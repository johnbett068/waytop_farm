# Phase 1E-C Aggregate READY Availability implementation review

Status: **Complete within Phase 1E-C scope**
Reviewed: 20 August 2026

## Files

Added:

- `apps/inventory/availability.py`
- `apps/inventory/test_availability.py`
- `docs/reviews/phase-1e-c-audit.md`

Changed:

- `docs/architecture/availability-commitment-contract.md`

No files were removed.

No model or migration was added or changed for Phase 1E-C.

## Availability query design

`get_ready_availability` is a narrow read-only domain query. It accepts an existing Product and
Product Sale Unit and returns an immutable customer-safe projection containing only:

- whole `available_sale_units`;
- server `calculated_at`; and
- `reservation_coverage`.

It contains no Product, Inventory Item, Location, Lot, Position, Movement, Commitment, FIFO, actor,
Customer or Branch identifier. There is no HTTP endpoint, template integration or new permission.

`AvailabilityUnavailable` distinguishes invalid/unavailable Catalog, Inventory, Reservation and
PRE_ORDER dependencies from honest empty Inventory. Missing or unhealthy providers never become a
fabricated zero.

## Eligibility and aggregation

The query uses the ratified Africa/Nairobi business date and sums positive Stock Positions only
when all current persistent eligibility facts pass:

- Inventory Item is active;
- Inventory Item and Product base units agree;
- Location is active and allows saleable stock;
- Lot is active;
- Lot condition is `SALEABLE`;
- Lot expiry is null or has not passed; and
- on-hand base quantity is positive.

The current Inventory foundation contains no additional hold/restriction record. No status or
policy was invented to simulate one. All eligible Locations and Lots are aggregated into one
customer-visible Product pool; no per-source result exists.

The Product is re-read and must be active and published. The Sale Unit is re-read and must be active
and belong to that Product. A missing Inventory Item is an explicit provider-unavailable result,
while a valid provider with no eligible Position returns zero.

## Conversion and Reservation boundary

Conversion uses exact Decimal arithmetic:

`floor((eligible physical base - active READY reserved base) / current Sale Unit base quantity)`

Inputs must be finite, non-negative and exact to three decimals. The result is a non-negative Python
integer; fractional Sale Units are never returned and no upward rounding or floating-point
arithmetic is used.

Reservation persistence does not yet exist and was not invented. The default
`NoReservationPersistenceProvider` contributes the authoritative current empty-set total of
`0.000` and marks every result `reservation_coverage=NOT_IMPLEMENTED`. This makes the staged
dependency visible and prevents the physical-only result from being mistaken for a completed
reservation-aware confirmation calculation. Existing Commitments are not subtracted and are never
treated as Reservations. Phase 1E-D can replace this provider while preserving the result shape.

## PRE_ORDER and mutation boundaries

Only `READY` is supported. PRE_ORDER raises `PRE_ORDER_CAPACITY_UNAVAILABLE`; no Production
capacity, forecast or physical-Inventory substitute is fabricated.

The query performs aggregate reads only. Tests verify no Position quantity/version/update time,
Movement count, Commitment counter/state or Commitment event count changes during a query. FIFO
does not affect aggregate availability.

## Tests and verification

- Availability-focused suite: 15 passed.
- Product/Inventory/Commitment regression suite: 92 passed.
- Full Django suite: 174 passed.
- Django system check: no issues.
- Migration drift: no changes detected.
- `git diff --check`: passed; only existing line-ending conversion warnings were emitted.
- Clean isolated test databases applied the complete migration graph.

Coverage includes empty Inventory, exact division, remainder flooring, stock below one Sale Unit,
Decimal precision, multi-Location and multi-Lot aggregation, combined thresholds, all non-saleable
lot conditions through the SALEABLE-only filter, inactive items/locations/lots, blocked locations,
expiry boundaries, inactive/unpublished Catalog records, inactive Sale Units, missing Inventory
provider, multiple Products/Sale Units, PRE_ORDER rejection, Commitment non-deduction, read-only
behavior, privacy-safe result fields, demo-data absence and no Branch/customer-location concept.

## Data, PostgreSQL and deviations

No fixture, seed command, Location, Lot, Position, Commitment or fabricated availability data was
added. Existing `mock_data` remains disconnected from this query. The development `db.sqlite3` was
not migrated or populated.

The repository remains configured for SQLite. PostgreSQL concurrency was not tested and is not
claimed. Customer display queries are read-only snapshots; future atomic confirmation must still
recalculate availability under the ratified PostgreSQL locks.

There are no architectural deviations from AC01-AC28. The remaining functional dependency is
Phase 1E-D Reservation and Source Allocation persistence. Until it exists, reservation coverage is
explicitly incomplete and the query must not be used as the atomic confirmation authority.

The exact next phase is **Phase 1E-D: Reservation and Source Allocation**. It must add the active
READY reservation provider and complete owner-approved internal allocation without exposing source
details to customers or implementing Order/Payment confirmation.
