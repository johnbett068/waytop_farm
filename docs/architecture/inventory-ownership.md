# Inventory ownership and cross-domain boundaries

## Meaning of ownership

Domain ownership means authority to create/change the canonical business fact. It differs from legal title, physical custody and responsibility:

- WayTop may retain legal title while stock moves through stores, Production and dispatch.
- Inventory owns stock ledger and custody handoff facts.
- Production owns WIP quantities, biological observations, losses, labour, tasks and quality/release decisions after materials are issued.
- Procurement owns supplier selection, purchase order and commercial receipt expectations—not on-hand stock.
- Orders/Fulfillment own customer commitment and delivery work—not stock.
- POS owns sale/session/tender facts—not balances.
- Reporting owns no transactional facts.

## Ownership journey

| Stage | Legal/custody context | Canonical owner | Boundary event |
|---|---|---|---|
| Supplier before acceptance | Supplier | Procurement expectation | Purchase order/dispatch reference only |
| Receiving/quarantine | WayTop conditional custody | Inventory | Supplier receipt movement |
| Store/available stock | WayTop Inventory custody | Inventory | Posted receipt/transfer |
| Requested for Production | Still Inventory stock; possibly reserved | Inventory | Production request causes no movement |
| Issued to Production | Production WIP custody | Production for WIP; Inventory preserves issue history | Production consumption issue |
| Growing/quality/hardening | Production WIP | Production | Production observations/loss/release |
| Approved release awaiting receipt | Production WIP, not saleable | Production | Approved `ProductionRelease` only |
| Received finished seedlings | WayTop saleable/restricted stock | Inventory | Production release receipt |
| Reserved/allocated to Order | WayTop stock with commitment | Inventory | Reservation/allocation, no on-hand change |
| Picked/dispatch staging | WayTop stock | Inventory + Fulfillment custody context | Location movement/staging |
| Delivered/collected/POS completed | Customer custody/title per policy | Inventory records issue; Order/POS records commercial fact | Customer/POS sale issue |
| Customer return received | WayTop quarantine custody | Inventory | Return receipt, inspection required |

Inventory therefore remains the central stock authority without pretending that growing WIP is available stock. Inventory can report issued-to-Production history; Production reports current WIP. Cross-domain reporting joins their correlated events without dual-writing a balance.

## Production integration

`Production requests inputs → Inventory authorizes/reserves → Inventory issues item/lot/quantity → Production records usage/WIP → Production quality and release approval → Inventory independently receives released goods`

- A Production request identifies batch, task/activity, item, requested quantity/unit, needed date, permitted substitutions and destination Production area.
- Request approval does not change stock. Inventory chooses authoritative lot/location and posts the issue.
- Production may acknowledge/record actual use but cannot deduct or amend Inventory. Unused returns are Inventory return receipts/issues under explicit correlation.
- Production losses affect WIP, not previously posted Inventory. Salvage or reusable material re-enters only through a governed receipt.
- Release includes product/variant, grade, quantity/unit, batch/traceability and approval. Inventory validates it, creates/links stock lot and posts receipt.
- Duplicate issue/receipt is prevented by stable source reference plus idempotency.

## Procurement integration

`Purchase order → supplier dispatch → receiving inspection → Inventory receipt → invoice/accounting matching`

Procurement owns vendor, quotation, order, agreed quantity/price and delivery expectation. Inventory owns actual accepted/rejected quantity, lot, condition and location. A purchase order never increases stock. Inventory receipt emits evidence for Procurement three-way matching and future Accounting; it does not create a payable by itself. Supplier returns are Inventory movements correlated to Procurement authorization and future credit notes.

## Orders and Fulfillment integration

`Order accepted → future reservation → allocation → pick/stage → dispatch/delivery → Inventory sale issue`

Orders express demand and commercial commitment. They request reservation but never mutate stock. Inventory owns reservation/allocation and authoritative availability. Fulfillment orchestrates picking and customer handoff; Inventory posts location and sale/dispatch movements. Cancellation releases remaining reservation through Inventory. Partial fulfillments consume only correlated allocation lines.

## POS integration

`POS builds sale → Inventory availability check → tender/payment succeeds under orchestration → POS sale completes → Inventory posts sale issue → receipt composes sale/payment/movement references`

The future transaction boundary must prevent double-selling and ambiguous partial success through idempotent orchestration and compensation. POS never calculates or writes stock. A receipt is a projection, not a stock event. Void/refund alone does not add stock; a physical customer return and inspected Inventory receipt is required where goods return.

## Costing boundary

| Source fact | Owner | Costing use |
|---|---|---|
| Purchase price/freight expectation | Procurement | Input to landed-cost policy |
| Accepted lot quantity and stock movements | Inventory | Quantity layer and movement grain |
| Inventory valuation layers/policy result | Future Costing/Accounting policy over Inventory facts | Stock valuation; never edited on item balance |
| Labour time/rate reference | Production/Workforce | Batch cost input |
| Input usage | Production correlated to Inventory issue | Batch material consumption |
| Production expenses | Production evidence; Finance validates posting | Batch overhead/direct expense input |
| WIP quantities, loss and release | Production | Yield/unit-cost denominator under policy |
| Ledger/account entries | Accounting | Financial authority |

Costing is a derived, versioned service/read model. Inventory owns physical quantities, not final profitability or general-ledger truth.

## Reporting boundary

Inventory publishes governed facts/projections for current on-hand/available stock, movement history, lot/expiry, consumption, transfers, count variance, damage/waste/shrinkage and reorder signals. Stock valuation joins Costing policy. Production yield joins correlated issued inputs and released output. Reporting defines grain, timezone, units and freshness and never reimplements movement posting.
