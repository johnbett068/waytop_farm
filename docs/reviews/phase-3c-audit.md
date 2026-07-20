# Phase 3C Audit

## Scope and architecture
Phase 3C implements frontend-only staff projections for dashboard, source lots, batch list/detail, tasks and exceptions. It preserves the approved method-neutral lifecycle. Production WIP is explicitly not Inventory; a release approval only enables a later Inventory-owned movement.

## Requirements coverage
- Dashboard: stage counts, exception/resource alerts and upcoming tasks.
- Source lots: seed, rootstock, scion and cutting traceability with cost placeholders.
- Batches: all requested scan fields and full detail records.
- Tasks/exceptions: requested work types, overdue/upcoming/completed states and exception-only focus.
- Cost tracking: placeholders and contract only; no calculation.
- Page states: loading, empty, error/validation-ready, offline, permission and success.
- Documentation: frontend, flow, contract and canonical state machines.

## Accessibility and responsive review
Landmarks/headings, labelled controls, native buttons/links, visible focus inherited from staff tokens, keyboard-scrollable tables, state status/alert roles and focus transfer to state headings are present. Layouts collapse at 1100, 760 and 480px; desktop remains information-dense and mobile cards/columns remain usable. Disabled controls communicate preview-only actions.

## Security and permissions
All records are mock. Staff-only access is a future server permission. Sensitive cost and restricted-treatment capabilities are separated. No customer route exposes these pages; no browser control creates an authoritative action.

## Quality-gate evidence
Final results on 16 July 2026:
- Django system check: passed, 0 issues.
- Existing and Phase 3C tests: passed, 46/46.
- JavaScript syntax: passed (`node --check`).
- Raw CSS colour scan: passed for `staff-production.css`; all colours use design tokens.
- Responsive render review: passed at 390px mobile, 1024px tablet batch detail and 1440px desktop dashboard. Navigation is horizontally scrollable on narrow screens; metrics and detail columns collapse without content overlap.
- Browser review used the mock development server only. Its existing warning about unapplied Django framework migrations was not acted upon because Phase 3C prohibits backend/database changes.

## Definition of Done
Complete when checks pass, responsive screenshots are reviewed, accessibility/keyboard/focus behavior is verified, design tokens contain all colors, documents match the UI, and repository inspection confirms no backend model/API/write, inventory mutation, production/cost calculation or scheduling engine was introduced.
