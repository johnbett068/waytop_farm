# Delegation architecture

## Purpose

Delegation preserves operations during annual leave, sick leave, an acting appointment or a declared emergency. It lends a precise subset of authority for a limited time; it never changes identity, copies a whole role implicitly or transfers accountability.

## Delegation record

The future contract requires: delegation ID; delegator; delegate; requested and approved by; reason/category; capability allowlist; scope intersection; start/end; source assignment; approval policy; status (`draft`, `scheduled`, `active`, `expired`, `revoked`, `rejected`); revocation reason/time; created/updated timestamps; and audit/correlation IDs.

The delegate must already be active. The delegator may transfer only capabilities marked delegable, within scopes and dates they currently hold. Administrative security controls, audit mutation, break-glass authority and approval of the delegator's own pending item are non-delegable. Delegation chains are prohibited in the baseline policy: delegated authority cannot be redelegated.

## Lifecycle

`Requested → Approved/Scheduled → Active → Expired`, with `Rejected` and `Revoked` alternatives. Activation and expiry are authoritative server-time events. Revocation takes effect immediately for new commands without rewriting completed audit events. Open work returns to a governed queue for reassignment.

Emergency delegation uses the same record, smaller maximum duration and mandatory reason/incident reference. It does not bypass prohibited combinations or self-approval. A post-event review is required.

## Effective authority and action audit

Delegated authority is:

`delegate baseline constraints ∩ delegated capabilities ∩ delegator capability/scope ceiling ∩ effective window ∩ policy conditions`

Every delegated action preserves:

- **Performed By:** immutable human/service actor ID (the delegate).
- **Acting As:** delegated role/authority label and version, not the delegator's identity.
- **Delegated By:** delegator ID and delegation ID.
- **Reason:** delegation reason plus command reason where required.
- **Start / End:** effective window used in authorization.
- **Approver:** delegation approver and action approver, kept distinct.

The UI shows a persistent “Delegated authority” banner, exact expiry and scope, offers a clear return to normal authority, and never visually impersonates the delegator. Expired delegation produces a permission-state refresh; unsaved forms must preserve safe local input where possible but cannot submit.

## Review controls

Delegations appear in an immutable audit trail and review queue. Managers review upcoming/active/expired grants; administrators review emergency, privileged, unusually broad and repeatedly renewed grants. Alerts occur before expiry and on revocation. Reports distinguish baseline from delegated actions.

