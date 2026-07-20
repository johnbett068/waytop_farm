# Authorization scopes

## Rule

A capability says **what** may be attempted; scope says **where or on which records**. Both must match. Scope never expands a capability and a role name never implies scope.

## Scope dimensions

| Dimension | Examples | Match rule |
|---|---|---|
| Branch | Bomet Town, Ndaraweta, all branches | Resource branch is in explicit grant. |
| Production area | Greenhouse A, Hardening Yard | Batch/task current area is in grant; transfers require source and destination authorization or approval. |
| Register | BMT-01 | Register ID matches and authorized session conditions hold. |
| Warehouse/location | Main Store, Quarantine | Inventory location matches; both ends are evaluated for transfer. |
| Assigned order | Order IDs or assignment queue | Actor is current assignee/team member and branch grant also matches. |
| Assigned task | Production/delivery task | Actor owns or belongs to assigned team; task completion does not perform its source action. |
| Department | Sales, Nursery, Inventory | Routing/visibility dimension only when policy explicitly uses it. |
| Global | Administrative policy objects | Explicit grant; never inferred from Administrator label. |

Scopes may intersect: a cashier needs `pos.process_sale`, branch Bomet, register BMT-01 and an open session. An Inventory Clerk with Bomet/Main Store scope cannot receive into Ndaraweta. An Operations Manager may receive explicit all-branch scope.

## Representation and evaluation

Future grants use stable opaque IDs, type, inclusion set or explicit `all`, effective start/end and assignment source. Hierarchy expansion (branch contains warehouse) is policy-controlled and versioned; the browser must not infer it from names.

Evaluation uses the target's authoritative ownership/location at command time, including source and destination for multi-resource actions. Queries are filtered server-side and field-level rules may further redact data. Moving a record cannot be used to gain access: the move itself is authorized against current and proposed scope.

Conflicts resolve as follows: inactive/expired assignment denies; explicit deny wins; every required dimension must match; delegation can only narrow the delegator's delegable authority; separation-of-duties and approval requirements still apply.

## Temporary assignments

Temporary assignments include reason, sponsor/approver, scope, start/end, handover reference and review state. Expiry is automatic. They may place a worker at another branch/register/area but confer no new capability unless an explicit effective-dated capability assignment or delegation accompanies them.

## Query, URL and cache safety

Counts, exports, searches and direct object URLs use the same effective scope as detail/actions. Authorization-sensitive projections are keyed by actor, active role, scope and policy version, and invalidated after assignment/delegation changes. “Not found” may conceal records outside scope as defined in the frontend policy.

