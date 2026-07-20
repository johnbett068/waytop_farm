# Canonical staff roles

Roles are named, configurable bundles of capabilities. They improve assignment and explanation but are never tested in business rules. Future policy asks `can(actor, capability, resource)`, never `role == "Sales"`. Scope and approval policy still apply after a bundle grants a capability.

## Role catalogue

### Administrator

- **Purpose:** Govern access, configuration, policy and system integrity.
- **Responsibilities:** Manage staff lifecycle, role bundles, settings, branch configuration, audit access and incident response.
- **Authority:** Global administrative capabilities; operational capabilities only when separately assigned.
- **Restrictions:** Cannot erase audit history, grant a capability beyond their own grant authority, approve their own privileged change, or use administration status as automatic operational authority.
- **Escalation:** Project owner/governance authority for constitutional, ownership or break-glass decisions.

### Operations Manager

- **Purpose:** Coordinate cross-domain daily operations and approve material operational exceptions.
- **Responsibilities:** Order escalation, branch workload, production release oversight, inventory variance/transfer approval and operational reporting.
- **Authority:** Broad operational view/action/approval across explicitly assigned branches.
- **Restrictions:** No user/role/security administration by default; cannot self-approve; high-value write-offs and policy changes escalate.
- **Escalation:** Administrator for access/configuration; project owner for policy exceptions.

### Sales Officer

- **Purpose:** Manage customer and order work from enquiry through accepted handoff.
- **Responsibilities:** Customer records, order review/acceptance, notes and assigned-order coordination.
- **Authority:** View and act on assigned/branch orders and customers within granted capability.
- **Restrictions:** No stock adjustment, production release, POS reconciliation, role/settings administration or unrestricted export; cancellations/refunds follow thresholds.
- **Escalation:** Operations Manager.

### Nursery Supervisor

- **Purpose:** Supervise traceable propagation, quality and production-area work.
- **Responsibilities:** Plan batches, allocate tasks, review quality, manage holds and request/approve release where duty separation permits.
- **Authority:** Production capabilities within assigned areas and branch.
- **Restrictions:** Cannot create inventory balances; cannot release own quality review; cannot approve own corrections; no financial/admin authority.
- **Escalation:** Operations Manager; Administrator only for access/configuration.

### Inventory Clerk

- **Purpose:** Record physical stock custody events accurately.
- **Responsibilities:** Receive goods, prepare/release permitted movements, count stock, draft adjustments and transfers, preserve evidence.
- **Authority:** Inventory actions within assigned warehouse and branch.
- **Restrictions:** Never edits a balance directly; cannot approve own count variance/adjustment/transfer; no refunds, production release or administration.
- **Escalation:** Operations Manager.

### Cashier

- **Purpose:** Operate an assigned register and record customer sales/tenders.
- **Responsibilities:** Open/close assigned sessions, process sales, issue receipts and submit refund/void requests.
- **Authority:** POS actions on the assigned register while an authorized session is open; may execute a refund/void only after an independent approval.
- **Restrictions:** No price/settings override, stock adjustment, self-approved refund/void, cross-register operation or user administration.
- **Escalation:** Operations Manager; Sales Officer may resolve customer/order questions but does not approve restricted finance actions unless granted.

### Delivery Coordinator

- **Purpose:** Coordinate dispatch, pickup and delivery execution.
- **Responsibilities:** Assign permitted delivery tasks, prepare dispatch, record handoff/attempt/delivery evidence and manage exceptions.
- **Authority:** Fulfillment actions for assigned branch/delivery/task scopes.
- **Restrictions:** Cannot accept/cancel orders, alter payment facts, adjust inventory, approve refunds or administer access.
- **Escalation:** Operations Manager.

## Bundle governance

Role bundle changes are versioned and effective-dated. Existing audit events retain the role/bundle version used at the time. New custom roles may compose canonical capabilities but must state purpose, owner, review date and prohibited combinations. Direct grants and denials are exceptional policy records, not hidden edits to a person.

No canonical role is a superuser shortcut. Emergency access is time-limited, explicitly approved, intensely audited and reviewed after use.
