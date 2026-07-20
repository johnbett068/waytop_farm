# Inventory UI contract

## Boundary

This contract describes future server projections needed by the Phase 3D frontend. It is not an API or backend implementation.

## Shared page envelope

Future Inventory pages receive:

- immutable actor ID, active role assignment/version, effective capabilities and normalized scopes;
- branch/location context and active delegation summary;
- `as_of`, projection/policy version and safe freshness/stale state;
- allowed-command hints that remain advisory to the browser;
- pagination, stable sorting, filters and field-redaction status;
- safe error/denial reason and correlation reference.

## Dashboard projection

Metrics provide labelled grain/unit and source time for item count, available, reserved, hold, low/out, in-transit and pending workflow counts. Mixed-unit quantities must not be exposed as a meaningful aggregate without explicit compatible unit/grain. Alerts expose type, severity, item/lot/location/reference, safe explanation, owner/due time and allowed navigation.

## Item projections

List rows expose item ID/code/name, category ID/path, location projection, base/display unit, available/reserved values, condition, item lifecycle, last movement and allowed links. Detail separately exposes on-hand, available, reserved, allocated, hold and in-transit; item definition; lots; locations; movements; reservations; transfers; counts and activity. Every child collection has independent permission/freshness/pagination metadata.

## Workflow projections

- Lot: stable lot ID/number, item, source type/reference, supplier/Production batch where applicable, dates/expiry, condition, current location quantities and movement links.
- Movement: immutable transaction/line reference, posting/effective time, type, endpoints, item/lot quantity/unit, actor/approver, reason/evidence, state, reversal chain and correlation ID.
- Receipt: source expectation/release/dispatch/return reference, inspection lines, accepted/rejected quantities, condition/location, obligations and status.
- Transfer: source/destination scopes, lines, approvals, dispatch/receipt actors, in-transit balance, planned/actual times, discrepancy lines and state history.
- Count: type/scope/snapshot, blind-mode policy, assignments, observations/recounts, variance investigation/approval and resulting movement references.
- Adjustment/hold: reason category, item/lot/location quantity evidence, hold restriction, approval, attachments, status and audit.

## Command presentation

Future forms submit named commands, never balance PATCHes. The browser supplies expected version, reason/evidence, selected item/lot/location/quantity/unit, source reference, approval reference when applicable and idempotency/correlation context. The server reauthorizes transactionally. Success returns affected projection and audit reference; validation, conflict, permission or system failure posts nothing.

## Frontend simulation contract

Current fixtures are embedded in `staff-inventory.js`, namespaced to Inventory and local browser storage. They contain no credential/token and make no network request. Capability arrays—not roles—drive `data-capability` elements. This simulation must be removed/disabled in a production build when real authorization arrives.

## Safety

Empty differs from zero and unauthorized. 404 hides out-of-scope object existence; 403 explains known module/action denial. Offline commands are blocked. Analytics must not capture sensitive lot, chemical, variance, role/scope or denial details without privacy review.
