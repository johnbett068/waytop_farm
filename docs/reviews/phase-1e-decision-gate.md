# Phase 1E Availability and Commitment decision gate

Status: **Resolved - AC01-AC28 ratified; retained as historical decision evidence**
Reviewed: 15 August 2026

Resolution: [Availability and Commitment V1 Contract](../architecture/availability-commitment-contract.md). AC01-AC28 are ratified and Phase 1E implementation is authorized only in its staged order.

## Outcome

No Phase 1E models, migrations, services, permissions, routes, templates, or runtime behavior were created. The ratified V1 contract establishes the high-level rules for aggregate availability, hidden internal allocation, non-negative physical stock, and deterministic FIFO commitments. It does not define enough Inventory, future-supply, reservation, allocation, or unit semantics to create a durable schema without making business decisions.

The older Inventory architecture is not implementation authority. It states that Phase 3C.7 was architecture-only, its Inventory contract labels all aggregates as future concepts rather than approved models, and its audit explicitly requires governance approval of reservation/allocation semantics, item/location masters, base units, conversion precision, and related policies before implementation.

## Blocker 1 - authoritative physical availability source

- **Ambiguity:** No ratified persistent Inventory item, location, lot, movement, or balance source exists. Therefore physical on-hand and aggregate READY availability have no authoritative data source.
- **Existing contract language:** Inventory owns physical quantity, lots, locations, movements, and availability; physical availability cannot become negative; aggregate availability may span internal locations.
- **Why implementation depends on it:** An Availability service cannot calculate physical on-hand, committed-ready quantity, or projected-ready availability without a governed quantity ledger and eligible-stock rules.
- **Recommended decision:** Ratify the minimum Inventory ledger contract before READY availability: Inventory item-to-Catalog mapping, base unit, internal location, lot/condition eligibility, immutable movements, and a lockable balance or partition record.
- **Schema impact:** Requires approved Inventory-owned tables and references. A projection-only interface without a source ledger cannot enforce non-negative supply.
- **Runtime impact:** Defines which stock can be promised, which rows confirmation must lock, and how multi-location quantities are aggregated.
- **Tests required:** Multi-location aggregation, eligibility exclusions, movement-derived balances, zero/empty availability, no negative availability, unit conversion, and PostgreSQL competing-consumer tests.

## Blocker 2 - reservation versus allocation semantics

- **Ambiguity:** The ratified V1 contract says the owner confirms or adjusts hidden allocation and that future confirmation creates approved internal allocations. Older Inventory planning describes `reservation -> allocation -> pick/stage`, while its audit says reservation/allocation semantics still require approval. It is not ratified whether confirmation creates a reservation, a source allocation, or both.
- **Existing contract language:** READY commitments reference physical Inventory supply; the owner confirms/adjusts hidden allocation; customers cannot see internal locations. The future confirmation transaction is expected to create commitments and approved internal allocations.
- **Why implementation depends on it:** The distinction determines aggregate boundaries, lifecycle, quantity equations, release/consumption history, owner action timing, and which rows are locked during confirmation.
- **Recommended decision:** Ratify two separate Inventory-owned concepts: a confirmation-time reservation that reduces available quantity, and a later staff-confirmed source allocation that selects eligible location/lot quantities. If source allocation must occur during confirmation instead, state that explicitly and define the responsible permission and fallback when the owner is unavailable.
- **Schema impact:** Either one allocation table or separate reservation/allocation aggregates, plus append-only quantity-change records, idempotency, actor, timestamps, and source references.
- **Runtime impact:** Determines whether automatic confirmation can succeed from aggregate supply alone and when staff intervention is required.
- **Tests required:** reservation-versus-allocation transitions, exact aggregate equations, owner adjustment, release/consume behavior, over-allocation rejection, internal-only projections, and idempotency.

## Blocker 3 - allocation grain and cross-location substitution

- **Ambiguity:** It is not ratified whether allocation targets location, lot, or both; whether READY demand may be split or substituted across locations; or which condition/expiry rules make a source eligible.
- **Existing contract language:** Aggregate availability may use multiple internal locations, while customers never select or see Branch, Stock Location, or Stock Lot.
- **Why implementation depends on it:** Foreign keys, uniqueness rules, allocation quantity constraints, lock ordering, and customer-safe projections all depend on the source grain.
- **Recommended decision:** Allocate internally at `(inventory item, location, lot)` grain, permit splitting across eligible locations, and define deterministic source-selection policy separately from customer-facing availability. Require explicit owner adjustment history rather than changing the customer commitment.
- **Schema impact:** Allocation lines need protected source references and a stable ordering/identity; aggregate constraints require transactional enforcement because cross-row sums cannot be expressed as ordinary database checks.
- **Runtime impact:** Defines how aggregate promises become operational picks and how unavailable/held/expired sources are excluded.
- **Tests required:** split allocation, substitution policy, location/lot eligibility, deterministic lock ordering, aggregate equality, over-allocation, and customer-field redaction.

## Blocker 4 - quantity unit and partial-supply ledger

- **Ambiguity:** Existing Order quantities are counts of sale units, while Inventory is intended to use product base units. The conversion precision, rounding policy, and authoritative record that increments `supplied_quantity` are not ratified.
- **Existing contract language:** `OrderLine.quantity` counts sale units and snapshots `base_quantity`; commitments preserve committed, supplied, and outstanding quantities; partial supply must not rewrite the original commitment.
- **Why implementation depends on it:** A tray Order may reserve many seedlings. Storing only sale-unit counts cannot represent partial base-unit supply, while storing only base units can diverge from the immutable commercial quantity.
- **Recommended decision:** Preserve both immutable commercial sale-unit quantity and exact base-unit committed quantity captured at confirmation. Derive supplied and outstanding values from append-only Commitment supply/release records in base units, with an explicitly ratified conversion and rounding policy.
- **Schema impact:** Commitment requires separate commercial and base-unit quantities plus immutable supply events; Order Line counters need a defined mapping or must remain commercial projections.
- **Runtime impact:** Determines whether partial supply may split a sale unit and how customer-visible outstanding quantities are represented.
- **Tests required:** unit conversion, non-integral conversion rejection or rounding, tray/seedling partial supply, immutable original quantity, cumulative supply bounds, and projection consistency.

## Blocker 5 - future supply and FIFO scope

- **Ambiguity:** Production persistence does not exist. There is no ratified definition of effective future capacity, forecast reliability, required-date interpretation, or the partition within which FIFO competes.
- **Existing contract language:** Forecast is not guaranteed stock; PRE_ORDER may consider future Production Batches whose expected-ready date satisfies the required date; FIFO uses confirmation timestamp and a database-generated tie-break.
- **Why implementation depends on it:** Remaining future capacity cannot be calculated, and FIFO cannot be safely applied without defining whether priority is per Product, Inventory item, sale unit, required-date window, grade, or another supply pool.
- **Recommended decision:** Keep future availability explicitly unavailable until Production Batch/capacity persistence is ratified. Ratify FIFO per compatible base-unit supply pool, ordered by confirmation timestamp and database sequence, while separately defining required-date eligibility and priority behavior.
- **Schema impact:** Future-capacity references cannot be added until the Production aggregate exists. Commitment can eventually retain its FIFO sequence and required date without fabricating capacity.
- **Runtime impact:** PRE_ORDER confirmation must remain unavailable until a real future-supply provider can lock and reserve compatible capacity.
- **Tests required:** unavailable dependency response, equal-timestamp deterministic sequence, FIFO partitioning, required-date boundaries, partial releases, and no negative/fabricated Production capacity.

## Concurrency consequence

SQLite cannot prove the required competing-consumer behavior. PostgreSQL is not configured in the current repository. Once the schema decisions above are ratified, integration tests must run against PostgreSQL and prove deterministic row locking, no double consumption, idempotent retries, and rollback of every cross-domain write on failure.

## Required ratification before implementation

1. Minimum Inventory persistence and eligible-stock definition.
2. Reservation versus source-allocation lifecycle and timing.
3. Location/lot allocation grain and cross-location substitution policy.
4. Sale-unit to base-unit conversion and partial-supply representation.
5. Future-capacity authority, required-date semantics, and FIFO competition scope.
6. Cancellation/release and commitment-expiry rules before those operations are implemented.

Ratification resolved this decision gate. `VerifyPaymentAndConfirmOrder`, Payment confirmation, Order confirmation, commitment creation, allocation, and availability claims nevertheless remain unavailable until their later implementation phases are explicitly authorized and completed.
