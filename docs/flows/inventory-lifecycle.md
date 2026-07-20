# Inventory lifecycle

## Canonical lifecycle

`External or domain-authorized source → controlled receipt → stored/restricted stock → reservation/allocation or issue/transfer → customer/supplier/disposal/Production boundary → immutable audit`

Inventory records stock only through posted transactions. Drafts, requests, orders, tasks, quality observations, payment confirmations and screen actions do not change quantity.

## Receipt flow

`Expected delivery/source evidence → receiving area → inspect and identify item/lot/quantity/condition → independent approval where required → post receipt → store/restrict`

- Supplier receipt references Procurement but Inventory owns actual accepted stock.
- Production receipt references one approved Production release.
- Customer return enters returns/quarantine, never available stock automatically.
- Rejected quantity remains outside accepted on-hand or moves through an explicit supplier-return/disposition workflow.

## Issue flow

`Authorized demand → select source location/lot → validate scope, availability and handling → approve where required → post issue → acknowledge destination`

Production issue ends Inventory on-hand custody and begins Production WIP. Customer/POS issue ends WayTop stock custody. Waste/supplier return use their own reason and destination boundary rather than generic negative adjustment.

## Production integration

`Production request (no quantity effect) → optional Inventory reservation → Inventory issue → Production WIP/usage → Production quality/release → Inventory finished-goods receipt`

The issue and receipt have independent IDs and may occur in partial quantities. Production loss is not an Inventory adjustment. Unused material re-enters through explicit return. Released output becomes sellable only after Inventory receipt into an eligible location/condition.

## Sales and POS integration

`Order → future reservation → allocation → pick/stage → dispatch/delivery → customer issue`

`POS availability check → completed sale orchestration → customer issue → receipt projection`

Orders and POS never write a balance. Reservation expiry/cancellation releases availability. A void/refund does not imply physical return. Return inspection determines whether Inventory posts saleable, quarantine, damaged or disposal disposition.

## Transfer flow

`Draft → submit → approve if policy requires → dispatch source-to-transit → carry in transit → destination inspect/accept → receive transit-to-destination → resolve variance → close`

Partial receipts remain open with remaining transit quantity. Shortage/damage/excess produces discrepancy evidence and governed movements; it does not overwrite dispatch. Consolidated company on-hand includes in-transit, while branch/location availability does not.

## Count flow

`Plan scope/snapshot → freeze or reconcile concurrent movement → blind count → optional recount → investigate variance → independent approve/reject → post variance adjustment → close`

Counts preserve every observation. Rejected variance changes no stock. Approval references the exact count version. Reopening creates a new governed cycle rather than editing a closed count.

## Correction flow

`Identify erroneous posted transaction → protect dependent workflows → approve correction → post exact reversal → post corrected transaction if required → retain correlation`

No user edits or deletes a posted line. When downstream sale, transfer, Production issue or accounting evidence exists, correction coordinates explicit compensating actions rather than rewriting those domains.

## Stock ledger view

For an authorized item/lot/location and period, the future ledger presents:

- opening balance projection at period boundary;
- receipts by governed reason;
- issues by governed reason;
- transfer dispatch/receipt and in-transit position;
- adjustments/corrections with approval;
- reservation/allocation separately from physical quantity;
- closing balance projection;
- chronological actor, evidence, source, approval and correlation history.

No Phase 3C.7 code calculates these values.
