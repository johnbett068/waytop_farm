# Staff authorization frontend specification

## Scope

This specification describes a frontend-only authorization simulation for design and testing. It is not login, authentication, impersonation or security enforcement. Phase 3C.5 requires documentation only; implementation belongs to a separately approved frontend milestone.

## Staff context presentation

The staff shell presents the simulated person's name, staff ID, active role, branch/area/register context and delegation state. Role and context selectors use clear labels and never imply that a role is the identity. Status, scope and expiry are readable text, not color alone.

Navigation is built from canonical module-view capabilities. Within a page, controls are derived from action capabilities plus simulated scope/state/approval policy. One shared permission evaluator consumes fixture data; templates and modules must not duplicate role-name conditionals.

## Development role switcher

The development-only switcher provides:

- instant selection among the mock identities in `docs/architecture/identity.md`;
- explicit active-role selection where a fixture has multiple assignments;
- optional branch/area/register and valid/expired delegation scenarios;
- a persistent, visually distinct banner reading “Authorization simulation — not secure” with actor, role, scope and delegation expiry;
- immediate recomposition of sidebar, module cards, field redaction, buttons and approval affordances;
- direct-URL denial simulation using the policy below;
- reset to the default fixture and a copyable scenario identifier for reproducible testing.

The selected fixture/scenario may persist in namespaced browser storage across reloads. It must never use cookies/tokens resembling production credentials, call a backend, mutate business data or ship enabled in production. A build-time development flag plus runtime environment assertion removes/blocks it outside approved local/test environments. Query-string scenarios are allowlisted and contain no PII or authority claims.

## Interaction and accessibility

The switcher is a native button opening a labelled dialog or popover with predictable focus entry/return, Escape close, keyboard-operable controls and status announcements through a polite live region. Selection does not unexpectedly navigate. The simulation banner is a landmark/status message and remains visible without covering content at zoom or on mobile.

Hidden controls are preferred when an action is irrelevant or undiscoverable. A visible disabled control is used when teaching workflow or explaining a prerequisite; it includes adjacent explanation and does not rely on `title`. Denial, expired delegation and scope mismatch states move focus to a clear heading, explain the safe reason, identify an escalation path and provide a useful navigation action. No inaccessible “disabled link” pattern is used.

## Direct URL policy

| Situation | Simulated result |
|---|---|
| Known module, actor lacks module-view capability | `Permission Denied` (403 semantics) with return to Dashboard. |
| Actor has module access but resource is outside view scope or existence is sensitive | `Not Found` (404 semantics), without confirming existence. |
| Route retired/moved and replacement is safe for the actor | Redirect to documented canonical route with notice. |
| Actor can view but cannot perform action | Render page, omit/disable action as specified; a forged action simulation returns Permission Denied. |
| Delegation/temporary assignment expired after page load | Persistent expiry notice, refresh effective context, block submission and preserve safe draft input. |

The same scenario outcome applies to navigation, direct URL, page projection, buttons and simulated command checks. Hidden navigation is usability only; future server behavior is governed by `docs/contracts/authorization.md`.

## Test scenarios

At minimum verify each identity, every module row, representative allowed/denied action, wrong branch/area/warehouse/register, assigned versus unassigned order/task, valid/expired/revoked delegation, approval required, self-approval prohibition, offline/stale state and direct URL denial. Automated tests must fail on role-name authorization checks and unknown capabilities.

## Future handoff

When backend authorization exists, the server supplies effective capabilities, scopes, allowed-command hints, policy version and safe denial responses. The browser may use them for presentation but never declares itself authorized. Frontend analytics must not capture sensitive role/scope or denial details without privacy review.

