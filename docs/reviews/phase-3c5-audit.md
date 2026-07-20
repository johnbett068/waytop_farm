# Phase 3C.5 architectural review

## Outcome

**Complete — architecture and frontend specification only.** Phase 3D remains paused. Completion means the governance design is internally complete; it does not authorize authentication, backend permissions, database work, APIs, Inventory, POS or Phase 3D implementation.

## Decision summary

- Identity is an immutable actor plus employment/context projection; it is not a role.
- Seven canonical roles are configurable, versioned capability bundles. Business logic never compares role names.
- One canonical `domain.verb[_object]` catalogue replaces provisional Phase 3 labels through a controlled alias migration.
- Effective authority intersects active status, assignment, capability, scope, time/delegation, policy conditions and separation-of-duties rules. Deny wins.
- Branch, production-area, register, warehouse, assigned-order and assigned-task scopes are independently expressible.
- Temporary assignment changes operational placement; authority changes only through an explicit grant/delegation.
- Delegation is capability-allowlisted, scope-bounded, approved, effective-dated, non-redelegable and always attributes the real performer.
- Approval is a distinct command/capability. Thresholds are effective-dated policy, never hardcoded in roles or UI.
- Refund/void request, independent approval and execution are separate capabilities; original financial facts remain immutable.
- Self-approval prohibitions compare human identity across roles and delegation lineage.
- Administrator governs access/configuration but receives no automatic operational superpowers.
- Navigation and actions are capability filtered, while direct URLs and future commands follow the same server policy. Hidden UI is not security.
- Audit identity preserves actor, role version, delegation, approver, reason, server timestamp, correlation, branch and privacy-reviewed device context.

## Deliverable coverage

| Requirement | Evidence |
|---|---|
| Identity architecture and mock identities | `docs/architecture/identity.md` |
| Roles, responsibilities, authority, restrictions, escalation | `docs/architecture/roles.md` |
| Capability catalogue, visibility/action matrices, approval hierarchy | `docs/architecture/permissions.md` |
| Branch/area/register/warehouse/order/task scopes | `docs/architecture/scopes.md` |
| Temporary delegation and complete attribution | `docs/architecture/delegation.md` |
| Prohibited actor pairs and emergency rule | `docs/architecture/separation-of-duties.md` |
| Authorization rationale and least privilege | `docs/architecture/authorization-philosophy.md` |
| Future decision, command, denial and audit contract | `docs/contracts/authorization.md` |
| Role switcher, navigation, direct URL and accessibility specification | `docs/frontend/staff-auth.md` |

## Constitutional and architectural review

- **Constitution:** Frontend remains an executable specification and future backend remains authoritative. Milestone review is recorded before any later phase.
- **Domain boundaries:** Authorization decides authority but does not perform Order, Production, Inventory, POS, Payment or Fulfillment transitions. Inventory remains movement-based; financial corrections remain reversals.
- **Consistency:** Stable capabilities and a central evaluator prevent duplicated permission logic. Provisional names are migration aliases, not competing grants.
- **Backend compatibility:** Inputs/outputs, stable IDs, policy/role versions, scopes, transactional re-checks, approval and audit envelopes are defined without prescribing Django models.
- **Security:** Default deny, least privilege, explicit global scope, server-side query filtering, safe 403/404 policy, cache invalidation and field protection are specified.
- **Auditability:** Historical identity, authority, delegation, approval and correlation survive assignment and policy changes; corrections append events.
- **Scalability:** New modules add capabilities and resource adapters without adding role branches. Custom roles compose the same catalogue.
- **Accessibility:** Switcher/banner, keyboard/focus behavior, non-color status, denial guidance, zoom/mobile behavior and live announcements are specified.

## Quality gate

- [x] Constitution compliance reviewed.
- [x] Existing operational architecture and independent domain lifecycles preserved.
- [x] Future backend authorization contract defined without implementation.
- [x] Canonical catalogue prevents duplicate permission logic and role hardcoding.
- [x] Required module and action matrices are complete.
- [x] Scope, delegation, approval and separation-of-duties rules are explicit.
- [x] Audit identity envelope includes every requested field.
- [x] Development-only frontend simulation and direct URL policy are specified.
- [x] Accessibility considerations are testable.
- [x] No authentication, models, migrations, APIs, Django permissions/groups, Inventory, POS or business logic were created.

## Support for future phases

Inventory can reuse location scopes, movement capabilities, dual custody and independent variance approval. POS can combine register scope, open-session conditions, tender actions and independent refund/void approval. Orders and Fulfillment can use assigned-object plus branch scopes without collapsing their lifecycles. Production can distinguish recording, quality review and release while preserving WIP/Inventory ownership. Reports inherit source-domain scopes and separate export authority. Administration gains versioned roles/policy and privileged-change review. Every module emits the same audit identity envelope and correlation chain.

## Remaining approval gate

The project owner should review role bundle defaults, real branch/warehouse/area/register taxonomy, monetary/quantity thresholds, emergency governance and data-export classifications before implementation. These are policy decisions, not gaps in this architecture. Do not begin Phase 3D until separately approved.
