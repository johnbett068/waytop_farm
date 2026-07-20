# Inventory Management frontend flows

## Discovery

`Inventory Dashboard → alert/queue/quick action → focused module → item/transaction evidence → read-only history`

Dashboard metrics are independent projections. “Available” does not mean on-hand, reserved does not reduce physical quantity, and mixed units are never added into valuation.

## Item and lot investigation

`Search/filter Items → open Item Workspace → compare on-hand/available/reserved/hold/transit → inspect lot/location/movement/activity`

The item header remains stable while tab projections change. Lot source and Production references establish traceability. No tab owns or rewrites another.

## Receiving preview

`Choose Supplier/Production/Transfer/Customer Return → reference source → identify item/lot/quantity/unit/condition → choose controlled destination → preview`

No posting occurs. Future Inventory validates the source once and posts physical receipt. Procurement owns purchase expectation, Production owns release, transfer owns dispatch custody and returns enter inspection/quarantine.

## Transfer preview

`Draft → independent approval where required → source dispatch → in transit → destination inspection/receipt → variance resolution → completed`

The UI shows dispatch lines and destination states together without treating them as one editable status. Variance does not rewrite dispatched evidence.

## Count preview

`Plan cycle/full count → assign blind count → record observations → recount/investigate → independent variance approval → future variance movement → close`

The Phase 3D UI displays queues and history only. Expected quantity remains hidden in blind-count execution. Approval buttons require `inventory.approve_count_variance`.

## Adjustment and quality-hold preview

`Record evidence/reason → request adjustment → independent review → future posted movement or rejection`

Quality hold is an availability restriction, not a quantity movement. Damage/spoilage/waste/correction use their governed transaction meanings. The original remains immutable.

## Cross-domain flows

- Production requests inputs; Inventory issues. Production release requests receipt; Inventory alone posts it.
- Orders/Fulfillment request reservation/allocation/issue; they never write stock.
- POS availability and completed-sale orchestration request an Inventory issue; the receipt is only a projection.
- Procurement creates purchase expectations; Inventory records accepted physical stock.
- Reporting later consumes Inventory projections/events without owning commands.

## Permission and state flow

The simulator switches capability bundles and re-evaluates module/action visibility. Missing `inventory.view` results in simulated Permission Denied. Missing action capability omits its action. Loading/empty/error/offline states leave all mock facts unchanged.
