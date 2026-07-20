# Staff dashboard frontend specification

## Purpose

The staff dashboard is WayTop’s calm, exception-first operational homepage. It helps authorised roles see customer commitments, propagation/quality risks, inventory exceptions and assigned work without pretending the dashboard itself owns domain mutations.

## Displayed information

Overview metrics; Today’s Orders; Awaiting Fulfillment Assignment; Orders in Preparation; movement-based Inventory Exceptions; propagation-neutral Production Exceptions; Today’s Tasks; audit-aware Recent Activity; Notifications; Quick Actions. Mock data covers Anna F1 Tomato trays, grafted Hass Avocado, KPF 12 Passion Fruit and Gloria Star F1 Cabbage across Bomet Town and Ndaraweta operational areas.

Metrics are mock counts, clearly labelled as a mock operational view—not business claims. Exceptions include high mortality, hardening overdue, quality hold, awaiting review, input shortage and movement awaiting posting.

## User actions

Phase 3A permits navigation-shell interaction, mobile menu, notification drawer, dismiss/close behavior and confirmation-dialog preview. Search, filters, pagination, task completion, review, release, movement and quick commands are disabled placeholders. Future actions navigate to domain modules or issue explicit permissioned commands; dashboard cards never mutate cross-domain records directly.

## States

Loading skeleton/state, empty, system error/retry, permission denial, offline/stale and success are exercisable through `?state=`. Offline state explicitly blocks consequential operations. Individual future widgets also require isolated loading/empty/error/permission states so one failed projection does not blank the whole dashboard.

## Staff navigation and future modules

- **Dashboard:** exception and workload projection.
- **Orders:** commercial commitments and independent order status.
- **Production:** source lots, batches, activities, observations, inputs, labour, stages, quality and releases.
- **Inventory:** movement ledger, lots, locations, transfers, counts and availability projections.
- **Products:** catalog, variants, units and governed prices.
- **Customers:** customer records and privacy-safe history.
- **Branches:** internal operational locations, areas and capabilities.
- **POS:** register/session, sale and tender workflows using shared domain services.
- **Reports:** read-only governed metrics and exports.
- **Notifications:** staff/customer delivery status and attention centre.
- **Settings:** versioned policies, thresholds, numbering and business configuration.
- **Profile/Help:** identity/security preferences and operational guidance.

Navigation is grouped by Workspace, Commerce and System rather than a single growing list. Role filtering removes unauthorised modules server-side; hiding links alone is not permission enforcement.

## Reusable staff components

Staff sidebar/topbar, search field, metric card, status badge, horizontally scrollable data table, pagination, compact queue, progress indicator, exception/alert card, task card, activity timeline, notification card, quick action, state surface, drawer and native confirmation dialog. Components use semantic HTML and shared data contracts; domain-specific rules remain outside components.

## Staff design system

- **Purpose:** storefront persuades; staff UI prioritises, compares and decides.
- **Spacing/density:** compact 12–20px-equivalent token spacing inside records; larger separation between operational domains. Dense does not mean cramped.
- **Typography:** existing Manrope stack; clear 12px-equivalent uppercase metadata, strong record IDs and restrained heading scale.
- **Tables:** semantic headers, persistent units/status text, horizontal container on narrow screens, row hover only as enhancement, no essential information encoded solely in position.
- **Forms:** visible labels, units, hints, validation summary, immutable/read-only distinction and confirmation for consequential commands.
- **Dialogs/drawers:** native dialog where appropriate, labelled modal semantics, focus entry/return, Escape/close, no destructive default focus.
- **Charts:** only when trend/relationship is clearer than a table; labelled axes/units, accessible summary/table alternative and no decorative dashboards.
- **Status/alerts:** success, info, warning and danger tokens; every color has text/icon/label. “Critical” reflects governed thresholds, not arbitrary frontend calculation.
- **Icons:** decorative glyphs are hidden from assistive technology; action icons have accessible names. Future icon set must be consistent.
- **Responsive:** desktop persistent sidebar and two-column operations; tablet collapsible sidebar and balanced grids; mobile single-column cards, scroll-contained tables and touch targets.
- **Accessibility:** landmarks, heading hierarchy, skip link, native controls, visible focus, keyboard drawer/dialog, reduced motion, contrast testing and non-color status language.

## Permissions, future models and backend contracts

Dashboard view requires future `operations.dashboard.view`; each widget is independently permissioned. Context is a composed, timestamped `StaffDashboardProjection` containing metric definitions, customer-safe/order-safe staff projections, exception references, tasks, notifications and allowed actions. It may include internal location data only for authorised staff. It must not contain mutation authority or calculate ledger balances in the template.

Future models belong to their domains: Orders, Fulfillment, Inventory, Production, Notifications, Accounts and Audit. The dashboard owns no generic `DashboardMetric`, `Alert` or status model unless a genuine configuration/read-model need is demonstrated.

## Business rules

All operational principles in `docs/architecture/operations.md` apply. Counts link to reproducible queues. Exceptions show source, age, severity and responsible domain. Saleable inventory begins only after approved production release and inventory movement. Activity feed is not the audit ledger; it is a permission-filtered projection.

## Definition of Done

Distinct staff shell, scalable navigation, required dashboard sections, realistic propagation/operations data, reusable components, all states, accessibility/responsiveness, permission/query contracts, canonical production language, no raw CSS colors and no backend logic.
