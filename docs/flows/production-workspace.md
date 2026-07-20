# Production workspace flow

## Primary flow

`Production queue → open Batch → review Overview → inspect or record one child domain → return to Batch context`

1. Staff open an authorized batch from the Production queue.
2. Overview establishes batch identity, area, supervisor, lifecycle position, health and expected release.
3. Staff select the domain that matches the evidence being handled: Task, Labour, Input, Expense, Quality, Photo or Activity.
4. The selected view retains the same batch header and does not mutate another tab.
5. A future command records one domain fact with actor, time, reason/evidence, batch reference and optional task reference.
6. The future server returns refreshed permission-scoped projections and appends an audit event.

Phase 3C frontend controls are disabled; steps 5–6 describe future behavior only.

## Independent record flows

- **Task:** plan work → assign worker/team → perform work → record actual date/status/notes. Completion does not record time, consume materials, advance the batch stage or release stock.
- **Labour:** select worker/staff type → record hours/days and applicable rate reference → optionally link a Task → supervisor attests. Many workers or entries can reference one Task.
- **Input:** identify item/lot where available → record quantity/unit → link Batch and optional Task → future Inventory independently validates/posts any movement. Usage is not Procurement receipt.
- **Expense:** classify non-inventory spend → describe/date/amount → identify recorder → optionally link Task. Finance later decides whether evidence becomes a payable or ledger event.
- **Quality:** record applicable quantities and observations → append inspection → place hold through a separate command if required → independently review release. Germination is explicitly not applicable to grafting.
- **Photo:** capture milestone/evidence metadata → attach to Batch → append audit event. File scanning, storage, retention and access are future services.
- **Activity:** consume immutable events in chronological order. Corrections append compensating/superseding events rather than editing history.

## Release and Inventory handoff

`Quality evidence → independent release approval → ProductionRelease → separately authorized Inventory production receipt`

Production release records approved product/grade/quantity but remains a Production event. It neither creates an Inventory balance nor makes browser-displayed WIP sellable. Inventory owns the later movement and lot/location valuation. POS consumes only authoritative saleable Inventory; it never reads mock Production quantities as availability.

## Exceptions and states

Permission, scope, stale/offline, validation, conflict and server errors leave prior records unchanged. A task may remain complete while its stage transition fails because these are separate commands. A rejected input movement does not erase the Production usage evidence; the mismatch enters an exception/reconciliation flow. A failed cost projection does not block access to underlying immutable labour/input/expense records.

## Audit continuity

Every future event carries the authorization audit envelope: actor, active role, delegated authority, approver where applicable, reason, server time, correlation ID, branch and privacy-reviewed device context. The Batch Activity Log composes these events but does not own or rewrite them.
