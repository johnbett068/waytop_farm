# Capability permission catalogue and matrices

> **DEFERRED / FUTURE CATALOGUE.** Only permissions installed and required by the current ratified
> Phase 1 services are runtime authority. This broader matrix must not create permissions, roles,
> Branch scope or behavior. See [Documentation Authority](../document-authority.md).

## Conventions

Canonical capability names use lowercase `domain.verb[_object]`. They describe authority, not job titles. `view` includes an authorized list/detail projection but not export or sensitive fields. `manage` is reserved for administrative CRUD/configuration where individual commands will be refined later; it never implies another domain.

Every allow below is still subject to active status, scope, record state, field policy, approval threshold and separation of duties. `✓` means included in the baseline role bundle; `A` means the role may perform only as an independent approver; `R` means request/initiate only; `—` means absent. Bundles are configurable, so the matrix is a reviewed default—not business logic.

Role abbreviations: **ADM** Administrator, **OPS** Operations Manager, **SAL** Sales Officer, **NUR** Nursery Supervisor, **INV** Inventory Clerk, **CSH** Cashier, **DEL** Delivery Coordinator.

## Canonical catalogue

| Domain | Capabilities |
|---|---|
| Dashboard | `dashboard.view` |
| Orders | `orders.view`, `orders.accept`, `orders.cancel`, `orders.process`, `orders.assign`, `orders.export` |
| Payments | `payments.verify` |
| Customers | `customers.view`, `customers.manage`, `customers.export` |
| Production | `production.view`, `production.create_batch`, `production.record_activity`, `production.record_quality_review`, `production.manage_hold`, `production.release_batch`, `production.view_cost` |
| Procurement | `procurement.view`, `procurement.create_request`, `procurement.approve_request`, `procurement.manage_supplier`, `procurement.manage_quotation`, `procurement.create_order`, `procurement.approve_order`, `procurement.issue_order`, `procurement.record_delivery`, `procurement.view_spend`, `procurement.export` |
| Inventory | `inventory.view`, `inventory.receive`, `inventory.release`, `inventory.adjust`, `inventory.approve_adjustment`, `inventory.transfer`, `inventory.approve_transfer`, `inventory.dispatch_transfer`, `inventory.receive_transfer`, `inventory.count`, `inventory.approve_count_variance`, `inventory.export` |
| Products | `products.view`, `products.manage`, `products.export` |
| POS | `pos.view`, `pos.open_register`, `pos.process_sale`, `pos.close_register`, `pos.request_refund`, `pos.approve_refund`, `pos.issue_refund`, `pos.request_void`, `pos.approve_void`, `pos.void_sale`, `pos.view_reconciliation` |
| Fulfillment | `fulfillment.view`, `fulfillment.assign`, `fulfillment.dispatch`, `fulfillment.record_delivery`, `fulfillment.complete` |
| Branches | `branches.view`, `branches.manage` |
| Reports | `reports.view`, `reports.export` |
| Notifications | `notifications.view`, `notifications.manage_own` |
| Administration | `users.view`, `users.manage`, `users.deactivate`, `roles.view`, `roles.manage`, `settings.view`, `settings.manage`, `audit.view`, `audit.export`, `system.view`, `system.manage` |

Older Phase 3 provisional names (for example `operations.dashboard.view`, `orders.view_order`, `batch.plan`, `quality.review`, `release.approve`) are documentation aliases to migrate to this catalogue. They must not be implemented as parallel grants.

## Module visibility matrix

Module visibility uses its `*.view` capability unless noted. It controls navigation and projections, not security by itself.

| Module | Capability | ADM | OPS | SAL | NUR | INV | CSH | DEL |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Dashboard | `dashboard.view` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Orders | `orders.view` | — | ✓ | ✓ | — | — | ✓ | ✓ |
| Production | `production.view` | — | ✓ | — | ✓ | — | — | — |
| Procurement | `procurement.view` | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| Inventory | `inventory.view` | — | ✓ | — | ✓ | ✓ | — | — |
| Products | `products.view` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Customers | `customers.view` | — | ✓ | ✓ | — | — | ✓ | ✓ |
| POS | `pos.view` | — | ✓ | — | — | — | ✓ | — |
| Branches | `branches.view` | ✓ | ✓ | — | — | — | — | ✓ |
| Reports | `reports.view` | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| Notifications | `notifications.view` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Users | `users.view` | ✓ | — | — | — | — | — | — |
| Roles | `roles.view` | ✓ | — | — | — | — | — | — |
| Settings | `settings.view` | ✓ | — | — | — | — | — | — |
| Audit Logs | `audit.view` | ✓ | ✓ | — | — | — | — | — |
| System | `system.view` | ✓ | — | — | — | — | — | — |

Administrator intentionally receives administration rather than automatic operational access. Operational troubleshooting requires a separately approved, scoped assignment.

## Action permission matrix

| Action / capability | ADM | OPS | SAL | NUR | INV | CSH | DEL | Approval baseline |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Accept order / `orders.accept` | — | ✓ | ✓ | — | — | — | — | None within policy; OPS for exception |
| Cancel order / `orders.cancel` | — | ✓ | R | — | — | — | — | OPS after fulfillment/payment threshold |
| Start processing / `orders.process` | — | ✓ | R | — | — | — | — | Explicit CONFIRMED to PROCESSING command |
| Assign order / `orders.assign` | — | ✓ | — | — | — | — | — | None |
| Export orders / `orders.export` | — | ✓ | ✓ | — | — | — | — | Data-classification policy |
| Create production batch / `production.create_batch` | — | ✓ | — | ✓ | — | — | — | None within plan |
| Record activity / `production.record_activity` | — | ✓ | — | ✓ | — | — | — | None |
| Record quality review / `production.record_quality_review` | — | ✓ | — | ✓ | — | — | — | None; reviewer cannot release same review |
| Manage quality hold / `production.manage_hold` | — | ✓ | — | ✓ | — | — | — | Release of blocking hold follows policy |
| Release batch / `production.release_batch` | — | A | — | A | — | — | — | Independent NUR or OPS; exception to OPS |
| Create purchase request / `procurement.create_request` | — | ✓ | ✓ | ✓ | ✓ | — | — | Supervisor/OPS approval by policy |
| Approve purchase request / `procurement.approve_request` | — | A | — | A | — | — | — | Independent supervisor/OPS; requester cannot approve |
| Manage supplier / `procurement.manage_supplier` | ✓ | ✓ | — | — | — | — | — | Supplier due diligence/change review |
| Manage quotation / `procurement.manage_quotation` | — | ✓ | — | — | — | — | — | Comparison evidence; requester cannot be sole award approver |
| Create purchase order / `procurement.create_order` | — | ✓ | — | — | — | — | — | Approved request/award required |
| Approve purchase order / `procurement.approve_order` | A | A | — | — | — | — | — | Independent threshold-based approval |
| Issue purchase order / `procurement.issue_order` | — | ✓ | — | — | — | — | — | Approved current PO version only |
| Record supplier delivery / `procurement.record_delivery` | — | ✓ | — | — | ✓ | — | — | Inspection evidence only; Inventory posts receipt |
| View Procurement spend / `procurement.view_spend` | ✓ | ✓ | — | — | — | — | — | Commercial-data classification |
| Receive inventory / `inventory.receive` | — | ✓ | — | — | ✓ | — | — | None with source evidence |
| Release inventory / `inventory.release` | — | ✓ | — | — | ✓ | — | — | Governed source command required |
| Draft adjustment / `inventory.adjust` | — | ✓ | — | — | R | — | — | Independent approval |
| Approve adjustment / `inventory.approve_adjustment` | — | A | — | — | — | — | — | OPS; large write-off to ADM/governance |
| Initiate transfer / `inventory.transfer` | — | ✓ | — | — | R | — | — | OPS approval above threshold/cross-branch |
| Approve transfer / `inventory.approve_transfer` | — | A | — | — | — | — | — | Independent OPS |
| Dispatch transfer / `inventory.dispatch_transfer` | — | ✓ | — | — | ✓ | — | — | Approved transfer |
| Receive transfer / `inventory.receive_transfer` | — | ✓ | — | — | ✓ | — | — | Different custody actor from dispatch |
| Count inventory / `inventory.count` | — | ✓ | — | — | ✓ | — | — | None |
| Approve variance / `inventory.approve_count_variance` | — | A | — | — | — | — | — | Independent OPS |
| Process POS sale / `pos.process_sale` | — | — | — | — | — | ✓ | — | Open assigned session |
| Open register / `pos.open_register` | — | — | — | — | — | ✓ | — | Assigned register; float policy |
| Close register / `pos.close_register` | — | — | — | — | — | ✓ | — | Independent review for variance |
| Request refund / `pos.request_refund` | — | ✓ | — | — | — | R | — | Independent OPS approval |
| Approve refund / `pos.approve_refund` | — | A | — | — | — | — | — | OPS; high threshold to ADM/governance |
| Issue approved refund / `pos.issue_refund` | — | ✓ | — | — | — | ✓ | — | Valid independent approval; original payment/tender rules |
| Request void / `pos.request_void` | — | ✓ | — | — | — | R | — | Independent OPS approval |
| Approve void / `pos.approve_void` | — | A | — | — | — | — | — | Independent OPS |
| Void approved sale / `pos.void_sale` | — | ✓ | — | — | — | ✓ | — | Valid independent approval; append reversal, never erase sale |
| Manage products / `products.manage` | ✓ | ✓ | — | — | — | — | — | OPS; price/policy changes may need ADM |
| Manage customers / `customers.manage` | — | ✓ | ✓ | — | — | — | — | PII policy |
| Assign fulfillment / `fulfillment.assign` | — | ✓ | — | — | — | — | ✓ | DEL limited to assigned branch/rules |
| Dispatch fulfillment / `fulfillment.dispatch` | — | ✓ | — | — | — | — | ✓ | Required readiness evidence |
| Record delivery / `fulfillment.record_delivery` | — | ✓ | — | — | — | — | ✓ | Assigned delivery/task |
| Manage branches / `branches.manage` | ✓ | — | — | — | — | — | — | Administrator; operational sign-off |
| Manage users / `users.manage` | ✓ | — | — | — | — | — | — | Independent approval for privileged grants/status changes |
| Deactivate user / `users.deactivate` | ✓ | — | — | — | — | — | — | Independent review; preserve identity and audit history |
| Manage roles / `roles.manage` | ✓ | — | — | — | — | — | — | Independent administrator/governance approval |
| Manage settings / `settings.manage` | ✓ | — | — | — | — | — | — | Critical settings require independent approval |
| Export reports / `reports.export` | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | Scope and data classification; sensitive exports approved |
| View/export audit / `audit.view`, `audit.export` | ✓ | ✓ | — | — | — | — | — | Export restricted and audited |
| Manage system / `system.manage` | ✓ | — | — | — | — | — | — | Change control; no audit deletion |

## Approval hierarchy

| Level | Typical actions |
|---|---|
| No approval | In-scope reads, ordinary order acceptance, recording production activity, evidenced receipt, counting, assigned-register sale. |
| Supervisor approval | Routine batch release by an independent Nursery Supervisor; low-risk hold resolution; configured operational exceptions. |
| Operations approval | Order cancellation after commitment, refund/void, adjustment, variance, cross-branch/threshold transfer, POS close variance, production exception release. |
| Administrator approval | Privileged user lifecycle, role bundle/configuration, critical settings/branch/system changes; administrator does not replace required operational approval. |
| Governance/project-owner approval | Very large write-off/refund, break-glass event, ownership/security-policy change, or action affecting the sole administrator. |

Threshold values are effective-dated settings owned by policy, not embedded in role bundles or frontend code. Approval is a distinct capability and command; an approver cannot be the prohibited initiating actor.

Staff users are never hard-deleted through ordinary administration. A departed or mistakenly created identity is deactivated/tombstoned under retention policy so historical actor references remain intact. Any legally required erasure is a separately governed privacy process that preserves non-identifying audit integrity.
