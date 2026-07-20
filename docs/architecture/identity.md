# Staff identity architecture

## Purpose and boundary

This document defines the identity projection required by future staff experiences. Phase 3C.5 is specification only: it creates no authentication, users, groups, models, migrations, APIs or server enforcement.

Identity answers **who is acting and in what operational context**. A role answers **which reusable capability bundle may contribute authority**. They are deliberately separate: one person may hold several assignments, select one active role for a session, and receive a temporary delegation without becoming another person.

## Canonical concepts

| Concept | Definition | Invariant |
|---|---|---|
| Staff User | Future security principal linked to one human worker; owns credentials only when authentication is implemented. | Never shared; disabled access does not erase history. |
| Staff Profile | Employment and display projection: staff number, preferred name, contact, department and status. | Contains no password or permission truth. Personal data is field-protected. |
| Active Role | One currently selected role assignment used to explain the UI and evaluate its capability bundle. | Selection cannot create authority and is recorded on consequential actions. |
| Assigned Branch | Operational branch scope granted by an assignment. Zero, one or many may be allowed. | “All branches” is an explicit scope grant, never inferred from role label. |
| Assigned Department | Organisational home such as Sales, Nursery, Inventory or Operations. | Used for routing/reporting, not implicit authorization. |
| Assigned Register | Future POS register(s) on which the person may open or operate a session. | Register capability and register scope are both required. |
| Assigned Production Area | Nursery, greenhouse, hardening zone or other production scope. | Area capability and area scope are both required. |
| Status | `invited`, `active`, `suspended`, `inactive` or `departed` in the future contract. | Only `active` may act; historical identity remains resolvable. |
| Delegation | Effective-dated, approved transfer of a constrained subset of delegable capabilities and scopes. | Does not transfer identity or bypass separation of duties. |
| Temporary Assignment | Effective-dated placement into a branch, department, register, warehouse or production area. | Changes scope/context only unless paired with an explicit role/capability grant. |

Warehouse assignment follows the same scope rules even though it is not displayed as a primary profile field. A register session is an operational record, not an identity assignment.

## Effective authority

For a request, future enforcement computes:

`active status ∩ active assignments ∩ capability grants ∩ resource scope ∩ delegation window ∩ policy conditions ∩ separation-of-duties rules`

Deny wins over allow. Role selection narrows the session to its bundle; it never unions every role silently. Direct exceptional grants should be rare, time-bounded, reasoned and reviewed. Department membership, job title, route visibility and frontend state never grant permission.

## Session and context projection

The future staff context should provide immutable staff ID, display name, status, available role assignments, active role, effective capabilities, normalized scopes, active delegation summary, branch/timezone (`Africa/Nairobi` for display), and a permission-policy version. It must omit secrets and unrestricted personal data.

Changing active role or operational context requires a fresh authorization projection. Consequential commands carry the selected role and scope snapshot; a later reassignment must not rewrite history.

## Mock development identities

These records are fictional frontend fixtures only.

| Name | Staff ID | Active role | Department | Default scope | Special fixture |
|---|---|---|---|---|---|
| Mary Chebet | STF-1001 | Sales Officer | Sales | Bomet Town; assigned orders | Customer/order workflow |
| Peter Kiptoo | STF-1002 | Nursery Supervisor | Nursery | Bomet Nursery; Greenhouse A and Hardening Yard | Production review queues |
| Sarah Wanjiku | STF-1003 | Inventory Clerk | Inventory | Bomet Town; Main Store | Receipt, transfer and count drafting |
| Jane Atieno | STF-1004 | Cashier | Sales | Bomet Town; Register BMT-01 | POS session and sale simulation |
| John Bett | STF-1005 | Operations Manager | Operations | All branches and operational areas | Approval and cross-branch views |
| David Korir | STF-1006 | Delivery Coordinator | Logistics | Bomet Town; assigned deliveries | Dispatch and delivery queues |
| Amina Noor | STF-1007 | Administrator | Administration | Global administrative scope | Users, roles, settings and audit |
| Grace Njeri | STF-1008 | Inventory Clerk acting as Operations Manager | Inventory | Ndaraweta Store plus delegated Ndaraweta approval scope | Active delegation fixture, fixed start/end/reason |

Fixtures must be visibly labelled simulated, contain no production credentials and be excluded from production builds/configuration.

