# Point of Sale frontend

## Scope

Phase 4A is a frontend-only executable specification for fast walk-in nursery sales. It adds a POS dashboard, sale workspace, parked-sale queue, transaction timeline and receipt preview. All data is static mock projection data; browser interactions are deliberately ephemeral.

## Routes

| Route | Purpose |
|---|---|
| `/staff/pos/` | Register status, metrics, recent transactions, top products and quick actions |
| `/staff/pos/sale/` | Search, mock availability, cart, customer and payment display |
| `/staff/pos/parked/` | Resume/cancel mock parked sales |
| `/staff/pos/transactions/` | Filterable transaction-history projection and Phase 4B return notice |
| `/staff/pos/transactions/<reference>/receipt/` | Mock receipt and downstream boundary preview |

## Interaction model

- Product search filters local mock cards. Barcode and QR controls are explicit placeholders.
- Add, remove, quantity and clear actions mutate only the in-memory DOM. Display totals are a mock cashier aid, not authoritative pricing or tax.
- Customer search, discounts, loyalty, payment methods, register controls, parking and receipt delivery are placeholders.
- Loading, empty, error, permission, offline and success states can be reviewed using `?state=<state>`.
- The authorization simulator uses capability arrays. It is visual test scaffolding, not authentication or secure authorization.

## Responsive and accessible behavior

The workspace is desktop-first, collapses into a two-column tablet checkout and then a single-column touch layout. Controls retain touch-sized targets. Headings, labels, semantic lists, status text, focusable denial feedback, live simulator/toast regions and text-plus-color statuses support keyboard and assistive-technology review.

## Ownership boundaries

POS consumes future Catalog, customer and Inventory projections. It does not own or edit stock, availability, reservations, prices, customers, payments, register cash, Accounting entries, orders, returns or audit history. A future completed sale must coordinate independently owned records through explicit, idempotent contracts.
