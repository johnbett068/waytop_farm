# Authorization backend contract (future)

## Boundary

This is a future contract only. Phase 3C.5 implements no authentication, Django permission, model, migration, API or backend enforcement.

## Decision contract

Every query and command asks a central policy service for a decision using:

`actor_id, active_role_assignment_id, capability, resource_type/id, requested_scope/context, time, delegation_id?, command metadata, policy_version`

The result is `allow` or `deny` plus machine reason code, safe user guidance, matched assignment/scope, obligations (approval, reason, evidence, MFA in a later auth phase), decision/policy version and correlation ID. Clients receive only safe detail. Deny is the default; explicit deny wins.

Bulk/list/search/count/export authorization must filter each projection at source and apply field-level rules. It must not fetch unrestricted records and hide them in templates. Commands re-evaluate authorization transactionally against authoritative current resource state and optimistic version.

## Future records and relationships

Conceptual records include `StaffPrincipal`, `StaffProfile`, `Role`, immutable `RoleVersion`, `Capability`, `RoleCapability`, effective-dated `RoleAssignment`, `ScopeGrant`, `TemporaryAssignment`, `Delegation`, `ApprovalRequest/Decision`, `PolicyVersion`, `AuthorizationDecision` and append-only `AuditEvent`. Names describe boundaries, not approved Django models.

Stable IDs—not mutable names—link records. Role and policy versions remain addressable historically. Status/expiry revocation invalidates relevant authorization caches immediately.

## Command requirements

Consequential commands carry actor, selected role assignment, target, capability, expected target version, reason/evidence when required, delegation reference, approval reference, idempotency key, source/device context and correlation ID. Server time controls effective windows. A successful decision does not itself perform a domain transition; the owning domain service validates invariants and appends its event.

Approval is a separate command and capability. It validates proposer/recorder/beneficiary/delegation lineage against separation-of-duties policy and cannot rely on the frontend's assertion.

## Audit identity envelope

Every future consequential event supports:

| Field | Meaning |
|---|---|
| Actor | Immutable real human/service principal ID and safe display snapshot. |
| Role | Active role assignment and role-version snapshot used. |
| Delegated authority | Delegation ID, delegator, “acting as”, effective start/end and reason; nullable. |
| Approver | Independent approval decision/actor; nullable, never conflated with performer. |
| Reason | Governed code plus comment/evidence references where required. |
| Timestamp | Server-generated timezone-aware instant; Africa/Nairobi is display only. |
| Correlation ID | End-to-end operation identifier across authorization/domain events. |
| Branch | Authoritative branch ID/snapshot relevant to the action. |
| Device | Privacy-reviewed session/device/source metadata; no raw secrets. |

Also retain capability, resource, scope decision, policy version, outcome, before/after references or event IDs, idempotency key and IP/security metadata when proportionate. Audit is append-only; correction creates another event. Access and exports are themselves audited and retention is policy-controlled.

## Denial and disclosure

Authenticated staff who may know the module but lack an action receive `403 Permission Denied`. Object URLs outside view scope return `404 Not Found` to avoid existence disclosure. Unavailable/retired routes may redirect only to a documented canonical route; redirects never stand in for denial. APIs use equivalent status/error codes. Every denial may include a safe correlation reference and escalation path.

## Compatibility rules

All modules consume the canonical catalogue in `docs/architecture/permissions.md`; they do not invent role checks. Existing provisional Phase 3 names migrate through one controlled mapping. Domain services own business transitions, Inventory owns stock movements, financial changes use reversals, and authorization does not collapse independent lifecycles.

