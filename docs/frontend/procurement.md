# Procurement Management frontend

## Scope and ownership

Phase 3E is a frontend-only executable specification. Procurement owns external supplier sourcing, purchase demand, quotations, purchase orders, delivery expectations, inspection evidence and approval history. It never owns stock, Inventory movements, payables, payments or accounting entries.

“Only external source” means Procurement is the sole business source of supplier-acquisition expectations. Inventory may still receive approved Production releases, internal transfers and customer returns under their established contracts.

All displayed values, scores, spend and trends are static mock data. There is no backend, database, API, purchase posting, Inventory mutation, Accounting, authentication, upload or report calculation.

## Modules

| Module | Purpose | Boundary |
|---|---|---|
| Dashboard | Pending request/quotation/approval/delivery/receipt metrics, alerts, supplier scorecard, activity and quick actions. | Metrics are read projections; mock spend is not Accounting. |
| Supplier Directory/Profile | Supplier type/status, products, contacts, location, lead time, preference and performance. | Supplier master is Procurement-owned; product and Inventory item masters remain references. |
| Purchase Requests | Draft, Submitted, Approved, Rejected, Cancelled and Converted lifecycle with requester/department/date/priority/items/estimate/history. | Approval creates authority to source, not a supplier or stock commitment. |
| Purchase Orders | List plus Overview, Supplier, Items, Delivery Schedule, Approvals, Documents and Activity tabs. | Approved/issued PO is a commercial commitment, never on-hand stock or payable. |
| Goods Receiving | Supplier delivery, partial acceptance, rejection, damage/hold, notes and history. | Procurement records inspection evidence; Inventory alone posts receipt. |
| Supplier Performance | On-time, rejection, lead time, accuracy, quality, mock spend and accessible trends. | Future Reporting owns definitions/calculation/grain. |

## Authorization simulation

The persistent development banner switches among Mary, Peter, Sarah, John, Amina and denied Cashier fixture Jane. One evaluator reads capability arrays and filters `data-procurement-capability` actions; it never compares role names.

- Requesters can create demand but cannot approve their own request.
- Nursery Supervisor may independently approve in-policy requests.
- Inventory Clerk may record supplier-delivery inspection evidence but cannot approve purchase commitments.
- Operations Manager holds sourcing/order/approval capabilities.
- Administrator has supplier governance, high-level order approval and spend visibility without automatic operational creation/receiving authority.

Missing `procurement.view` would simulate direct URL denial. Hidden UI is explicitly not security; the future server remains authoritative.

## Accessibility and responsive behavior

Purchase-order tabs implement ARIA tab/tabpanel relationships, roving focus, Arrow keys and Home/End. Tables preserve comparison fields through horizontal scrolling. Statuses use text plus color. Activity and handoff history use ordered lists. Forms retain visible labels and disabled/mock behavior is explained.

Desktop uses dense grids and split workspaces. Tablet collapses main/aside content. Mobile stacks metrics/cards/forms, keeps module/tab navigation scrollable and retains item quantities, units, approvals and references.

## Definition of Done

All Procurement routes render, full lifecycle/status language is present, capability actions are centralized, Inventory/Accounting boundaries are visible, states are exercisable, and no backend behavior exists.
