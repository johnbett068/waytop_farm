# Inventory contract (future)

## Implemented external acquisition lot traceability

Acquire Stock generates `WTP-LOT-<32 uppercase hexadecimal idempotency UUID characters>`
on submission and persists it in the existing `StockLot.lot_code`. Different command
UUIDs yield distinct codes without counts, dates, SKU dependencies, or another lot
table. The existing unique item/lot-code constraint is the database backstop;
collisions fail instead of reusing historical stock. Acquisition idempotency keys
are database-unique; PostgreSQL advisory locks and existing Product row locks
serialize retries and receipt creation inside the atomic acquisition transaction.

Each new acquisition introduces its own lot; retries return the original receipt.
Acquisition lot codes cannot be renamed through model saves or queryset updates.
Supplier Batch / Lot is optional immutable source evidence on
`ExternalStockAcquisition.supplier_batch_reference`, independent of the optional
Supplier relationship and of the WayTop lot. It does not reuse provenance/reference
fields, which retain their existing meanings. History shows it when supplied.
Existing lots and historical movement records are not renamed or backfilled.
Other receipt workflows and all five condition/availability rules remain unchanged.

## Boundary

This is a domain contract, not implementation approval. Phase 3C.7 creates no Django model, migration, API, calculation, movement or stock projection.

## Conceptual aggregates

- `InventoryItem`: stable stock definition linked optionally to Catalog; category, type, base unit, tracking/handling policy and lifecycle.
- `StockLot`: item-specific lot/batch/serial grouping, origin, manufacture/received/expiry dates, condition and traceability.
- `InventoryLocation`: branch hierarchy endpoint and allowed handling classes.
- `StockTransaction`: command/audit header with type, state, references, evidence, actor, approval and correlation.
- `StockMovementLine`: immutable item/lot, quantity/unit and from/to endpoint/condition line.
- `StockBalanceProjection`: derived on-hand/available/reserved/allocated/in-transit view; never command input.
- `Reservation/Allocation`: future non-physical quantity commitments with source demand, expiry and consumption/release history.
- `Transfer`: source/destination custody workflow referencing dispatch and receipt transactions.
- `StockCount`: count scope/snapshot/assignments and immutable observations, investigation and approval.

These names describe ownership, not approved database models.

## Invariants

1. Only a successfully posted Inventory transaction changes quantity projections.
2. Every physical movement balances explicit source and destination/external control boundaries in one base-unit-normalized transaction.
3. Quantity is positive on a movement line; direction comes from endpoints, never a loosely signed form field.
4. Units and conversions are effective-dated, item-compatible and server-controlled.
5. Posted transactions/lines are immutable. Correction posts an exact linked reversal and corrected replacement where needed.
6. Source-domain references are unique where one event may be consumed once.
7. On-hand cannot become negative under baseline policy.
8. Location, lot, condition/availability obligations and source/destination authorization are checked transactionally.
9. Reservation/allocation changes availability, never on-hand.
10. Item/category/location deactivation preserves historical resolution and blocks new incompatible commands.

## Transaction state

Common state is `draft → submitted → approved when required → posted`, with rejected/cancelled before posting. A posted fact cannot return to draft/cancelled. Transfer and count workflow states add custody/investigation stages but affect stock only through their posted movements.

## Command contracts

Future commands include:

- define/version item, category, unit/tracking policy and location;
- draft/submit/approve/post supplier or other receipt;
- request/approve/post issue, including Production consumption;
- receive approved Production release;
- initiate/approve/dispatch/receive/resolve transfer;
- plan/start/record/recount/investigate/approve/close stock count;
- draft/approve/post adjustment, damage, waste, supplier return or correction;
- future reserve/release/allocate/consume commitment;
- record customer return into restricted inspection location;
- post fulfillment/POS customer issue through orchestration.

Each consequential command carries actor/active role/delegation, capability, scope, expected aggregate version, item/lot/location lines, reason/evidence, source-domain type/ID/version, approval reference, idempotency key, correlation ID and privacy-reviewed device context. Server time controls posting and effective windows.

## Query contracts

Queries include permission- and scope-filtered item lists, lot/location balances, available-to-promise projection, movement ledger, transaction detail, transfer/count queues, expiry/hold/reorder exceptions and activity. Every projection declares:

- `as_of`/freshness and policy/projection version;
- item, lot, location, condition and unit grain;
- on-hand, available, reserved, allocated and in-transit as distinct fields;
- field-redaction/permission state;
- stable sorting, pagination and export classification.

Opening/closing balance reports are read projections over a defined period and grain:

`opening posted position + period receipts/issues/transfer effects/approved adjustments = closing posted position`

This equation is a future server/reporting contract only. Transfer lines must not double-count company total: source, transit and destination views change, while consolidated ownership remains until external issue.

## Cross-domain event contracts

| Producer event/request | Inventory response/event |
|---|---|
| Procurement purchase order/delivery expectation | Receipt posted/rejected/variance with accepted item/lot/quantity |
| Production input request | Reservation/issue posted or rejected with selected lot/location |
| Production release approved | Finished-goods receipt posted/rejected, referencing release once |
| Order/Fulfillment demand | Reservation/allocation outcome; later customer issue |
| POS completed-sale orchestration | Idempotent sale issue outcome/correlation |
| Customer return authorized/received | Quarantine receipt and inspection-required outcome |

Events carry stable IDs, versions, line correlations and no secret/unsafe personal data. Consumers cannot update Inventory tables. Failed consumers retry idempotently; they do not infer stock from missing notifications.

## Authorization and approvals

Capabilities come from `docs/architecture/permissions.md`: view, receive, release, adjust/approve adjustment, transfer/approve/dispatch/receive, count/approve variance and export. Implementation may refine more granular commands without role-name logic.

The actor cannot approve their own adjustment, variance or transfer. Source dispatcher cannot receive at destination. Large write-off, restricted chemical movement, cross-branch transfer and negative-stock exception follow effective-dated approval policy. Both endpoints must be in scope.

## Audit and retention

Every posted/dismissed/rejected consequential command appends domain history plus the canonical authorization audit envelope. Stock activity preserves actor, approver, reason, evidence, source-domain reference, before/after projection references, server timestamp, branch/location, idempotency and correlation. Audit is append-only; normal deletion is prohibited.

## Failure and concurrency

Commands recheck current lot/location/availability and optimistic version inside the posting transaction. Duplicate idempotency/source references return the prior result. Insufficient quantity, stale version, expired lot/policy, wrong location class, approval conflict or scope denial posts nothing. Offline stock writes are unavailable. Multi-domain workflows use orchestration/outbox and compensating commands, never distributed direct-table mutation.
