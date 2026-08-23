# WayTop Farm — Post-Phase-1G System Architecture Audit

Audit date: 21 August 2026
Mode: audit only; no business behavior changed
Repository database configuration: SQLite; PostgreSQL is not configured

## 1. Executive Summary

The implemented core is a coherent, internal-service READY-order system. It can persist Catalog,
Customer, Order and Payment facts; post governed Inventory receipts, issues and transfers;
calculate aggregate READY availability; atomically verify a Payment and confirm a READY-only
Order; create FIFO Commitments with Reservations and complete Source Allocations; supply those
Commitments through immutable Inventory ISSUE history; explicitly enter PROCESSING; cancel
remaining READY supply; and complete a fully supplied PROCESSING Order.

The core Order lifecycle is `PENDING -> CONFIRMED -> PROCESSING -> FULFILLED`, with
`CONFIRMED|PROCESSING -> CANCELLED`. Payment has only PENDING and CONFIRMED. Confirmation ends at
CONFIRMED; PROCESSING is a separate explicit staff command. Supply may occur while CONFIRMED or
PROCESSING. No service automatically enters PROCESSING.

The lifecycle domain has broad model, service and SQLite regression coverage. All 251 tests were
discovered; 245 passed and the 6 PostgreSQL-only concurrency tests were correctly skipped. The
86-test focused lifecycle set passed, as did the 235-test implemented-domain set with the same six
skips. Consequently, functional behavior is verified on SQLite, but competing-transaction safety
is implemented and test-specified rather than PostgreSQL-verified.

No confirmed ratified-rule defect was found in the READY lifecycle services. Confirmed peripheral
repository defects do exist: seven configured public routes render templates that are absent and
therefore raise `TemplateDoesNotExist`. Production deployment is also blocked by missing explicit
Payment-evidence encryption keys and ordinary HTTPS/secret hardening. These findings were not
corrected because this audit forbids implementation.

All business-domain services are Python service boundaries only. There is no Order, evidence,
verification, processing, cancellation, supply, fulfillment, reallocation or Inventory mutation
HTTP endpoint. Order and Payment public pages render honest empty states; staff domain pages render
authenticated staff-only empty states. The Catalog is the only implemented public domain read
projection.

## 2. Current Implemented Capability Matrix

“Runtime reachable” means callable through current Python/runtime code. “Public” means reachable
through a customer-facing HTTP route, not merely registered in read-only Django admin.

| Capability | Implemented? | Ratified? | Runtime reachable? | Public? | Required permissions | States | Dependencies / limitations | Implementation | Authority |
|---|---|---|---|---|---|---|---|---|---|
| Staff accounts/authentication | Yes | Yes | Login, logout, profile and Django admin | Login/profile only | Django authentication; admin requires staff/model permissions | active/inactive staff flags | No implemented assignment/scope/delegation domain | `apps/accounts/*` | V1 and Phase 1 foundations; future authorization docs are specifications |
| Customer/profile/address persistence | Yes | Yes | Model/admin | No customer API | Django default model permissions in admin | active/inactive; one active default address | No automatic matching/merge; no customer account ownership | `apps/customers/models.py`, `admin.py` | Order/Customer/Payment contract §§2–3 |
| Product/Catalog persistence | Yes | Yes | Model/admin and public reads | Yes | Public read; Django default model permissions in admin | active/published; active sale unit/price | No category persistence; one current price required for ordering | `apps/products/models.py`, `catalog.py`, `views.py` | Order contract and Phase 1 foundations |
| Public Catalog projection | Yes | Yes | `/`, `/products/*` after migration | Yes | None | active + published Products | Exposes commercial data only; not READY availability | `apps/products/catalog.py` | Order contract §§5, 15–16 |
| PENDING Order creation | Yes | Yes | `create_pending_order()` | No command endpoint | Ecommerce: none; POS: active staff + `pos.process_sale` | creates PENDING | Server prices; complete immutable aggregate; no stock promise | `apps/orders/services.py` | Order contract §§4–6, 14–15 |
| Order line/contact/address snapshots | Yes | Yes | Created with Order | Empty pages only | Same as Order creation | immutable snapshots | Address conditionality is service-enforced; no correction command | `apps/orders/models.py` | Order contract §§3–5 |
| Idempotent Order creation | Yes | Yes | Same service | No | Same as creation | PENDING result | Unique key plus reconstructed request comparison; concurrent absent-key race unverified | `apps/orders/services.py` | Order contract §§4, 22 |
| Payment evidence | Yes | Yes | `submit_payment_evidence()` | No command endpoint | Ecommerce none; POS `pos.process_sale`; staff `payments.verify` | Payment must be PENDING | Repeat evidence is intentionally allowed; no idempotency key | `apps/payments/services.py` | Order contract §§8–10 |
| Encrypted raw evidence | Yes | Yes | Encrypted field | Never rendered raw | Same evidence access boundary | append-only | Fernet at rest; dev fallback derives from SECRET_KEY; production key required | `apps/payments/fields.py`, `checks.py` | Order contract §§9, 24 |
| Rejected verification history | Yes | Yes | `record_rejected_verification_attempt()` | No | active staff + `payments.verify` | Payment remains PENDING | Append-only; unique key; correlation ID is server-generated | `apps/payments/services.py` | Order contract §10; Phase 1D audit |
| Payment verification + READY confirmation | Yes | Yes | `verify_payment_and_confirm_order()` | No | active staff + `payments.verify` + `commitments.allocate` | Payment PENDING→CONFIRMED; Order PENDING→CONFIRMED | READY-only; accepted verification is durably recorded before the all-or-nothing confirmation transaction | `apps/payments/confirmation.py` | Phase 1F ratifications/audit supersede original one-transaction wording |
| Confirmation rollback/retry | Yes | Yes | Same service | No | Same as confirmation | retries PENDING or validates CONFIRMED result | Failed domain transaction rolls back all confirmation/supply facts but preserves truthful APPROVED attempt | `apps/payments/confirmation.py` | Phase 1F decision F04/audit |
| Inventory Item | Yes | Yes | Model only | No | Read admin: `inventory.view` | active/inactive | One per Product/base unit; provisioning has no governed runtime service | `apps/inventory/models.py` | Availability/Commitment contract §4 |
| Inventory Location | Yes | Yes | Model only | No | Read admin: `inventory.view` | active/inactive; saleable flag | Flat internal location; no Branch relationship | `apps/inventory/models.py` | Availability contract AC02 |
| Stock Lot | Yes | Yes | Model only | No | Read admin: `inventory.view` | SALEABLE/HELD/QUARANTINED/DAMAGED/EXPIRED | Condition mutation intentionally blocked; audited condition command absent | `apps/inventory/models.py` | Availability contract §§4.1, 4.3 |
| Stock Position | Yes | Yes | Movement service only | No | Indirect movement permission | non-negative Decimal(32,3) | Direct save/bulk mutation blocked; raw SQL remains outside ORM protection | `apps/inventory/models.py`, `services.py` | Availability contract AC04–AC05 |
| Immutable Inventory Movement | Yes | Yes | `post_inventory_movement()` | No | By type | RECEIPT/ISSUE/TRANSFER postable | ADJUSTMENT_IN/OUT and REVERSAL enum values exist but posting is rejected | `apps/inventory/services.py` | Availability contract §4.4 and staged implementation |
| RECEIPT | Yes | Yes | Movement service | No | active staff + `inventory.receive` | posted immutable fact | Requires explicit item/lot/destination and audit data | `apps/inventory/services.py` | Availability contract AC04–AC05 |
| ISSUE | Yes | Yes | Movement service; composed by supply | No | active staff + `inventory.release` | posted immutable fact | Cannot create negative stock | `apps/inventory/services.py`, `apps/commitments/supply.py` | Phase 1E-E ratification |
| TRANSFER | Yes, ledger-level | Yes | Movement service | No | active staff + `inventory.transfer` | one atomic source→destination movement | No dispatch/receipt/in-transit workflow or approval object | `apps/inventory/services.py` | Minimum Inventory contract; broader transfer UI is historical |
| Negative-stock protection | Yes | Yes | Every movement | No | Movement permission | Position ≥ 0 | Service locks/checks plus database CHECK | `apps/inventory/models.py`, `services.py` | Availability contract AC05 |
| READY availability | Yes | Yes | `get_ready_availability()` | Not currently wired to HTTP | None for safe calculation | calculated projection | Eligible on-hand minus ACTIVE remaining Reservations | `apps/inventory/availability.py` | Availability contract AC19–AC20 |
| Reservation deduction | Yes | Yes | Availability provider | No | None for aggregate result | ACTIVE remaining deducted | CONSUMED/RELEASED do not deduct | `apps/inventory/availability.py` | Availability contract §§8, 11 |
| Sale-unit conversion | Yes | Yes | Availability/confirmation/supply | Public Catalog exposes unit conversion, not availability | None for read | floor READY units; exact supply conversion | Decimal(32,3); no rounding of committed base quantity | availability/commitment services | Availability contract AC06–AC07, AC19 |
| Customer-safe availability | Implemented as value object | Yes | Internal callable | No HTTP exposure | None | READY only | Contains count/time/coverage; no sources | `apps/inventory/availability.py` | Availability contract §11 |
| Commitment creation | Yes, internal composition | Yes | Confirmation only | No | `payments.verify` + `commitments.allocate` | starts ACTIVE | Exactly one per Order Line; no standalone public command | `apps/commitments/services.py` | Availability contract AC08–AC09, AC27 |
| Commitment FIFO | Yes | Yes | Confirmation and authorized internal list | No customer exposure | list requires `commitments.view` | ACTIVE queue by confirmed_at + DB sequence | Partitioned by Inventory Item and supply mode; no override | `apps/commitments/models.py`, `services.py` | Availability contract AC16–AC18 |
| Commitment required date | Persisted | Yes | Creation logic | No | Confirmation permissions | null READY; copied PRE_ORDER | PRE_ORDER Commitment cannot currently be reached through confirmation | `apps/commitments/models.py`, `services.py` | Availability contract §7, AC17 |
| Reservation + initial Allocation | Yes, internal composition | Yes | Confirmation-owned transaction | No | `commitments.allocate` | Reservation ACTIVE | READY only; complete source coverage; caller-owned atomic block required | `apps/inventory/reservations.py` | Availability contract AC10–AC14 |
| Reallocation | Yes | Yes | Internal service with caller atomic block | No | active staff + `commitments.allocate` | Reservation stays ACTIVE | Replaces complete remaining split; preserves old lines | `apps/inventory/reservations.py` | Availability contract AC15 |
| Reservation release | Cancellation-only | Yes | Private cancellation composition | No | active staff + `orders.cancel` | ACTIVE→RELEASED | No standalone release, expiry or transfer | `apps/inventory/releases.py` | Phase 1G cancellation ratification |
| READY supply/consumption | Yes | Yes | `supply_ready_commitment()` | No | active staff + `inventory.release` | Commitment ACTIVE→SATISFIED; Reservation ACTIVE→CONSUMED | Whole sale units; allowed while Order CONFIRMED or PROCESSING | `apps/commitments/supply.py` | Phase 1E-E ratification D01–D14 |
| Outstanding quantities | Yes | Yes | Supply/cancellation | No | Owning command permission | supplied + cancelled + outstanding = committed | Order Line mirrors Commitment outstanding | commitment/order models and services | Availability contract AC09, AC23–AC24 |
| PROCESSING transition | Yes | Yes | `start_order_processing()` | No | active staff + `orders.process` | CONFIRMED→PROCESSING | Explicit only; valid partial supply permitted; no supply mutation | `apps/orders/lifecycle.py` | Phase 1G-Final decision record |
| READY cancellation | Yes | Yes | `cancel_ready_order()` | No | active staff + `orders.cancel` | CONFIRMED/PROCESSING→CANCELLED | Releases remaining allocations/reservation; supplied stock is not returned; Payment remains CONFIRMED | `apps/orders/lifecycle.py`, `apps/inventory/releases.py` | Phase 1G audit |
| Fulfillment completion | Yes | Yes | `complete_order_fulfillment()` | No | active staff + `fulfillment.complete` | PROCESSING→FULFILLED | READY-only, Payment CONFIRMED, all lines zero outstanding, Reservations consumed | `apps/fulfillment/services.py` | Order contract §13; Phase 1G audit |

## 3. Complete READY Lifecycle

### 3.1 PENDING aggregate

`create_pending_order()` owns one `transaction.atomic()` boundary. It normalizes contact/address
input, applies channel rules, selects current active Catalog data, calculates KES totals, and creates
Order, Order Lines, immutable snapshots, initial Order event, PENDING Payment and initial Payment
event. POS creation requires active staff with `pos.process_sale`; Ecommerce creation is guest
capable. A same-key retry locks and compares the existing Order aggregate. No Inventory,
Commitment, Reservation or Allocation changes.

### 3.2 Evidence

`submit_payment_evidence()` locks Payment and appends untrusted evidence while it remains PENDING.
Ecommerce submission is unauthenticated by design; POS and staff sources require their respective
permissions. Raw message text is encrypted before database persistence. Evidence does not change
Payment or Order and deliberately has no deduplication requirement.

### 3.3 Verification and confirmation

`verify_payment_and_confirm_order()` requires active staff plus `payments.verify` and
`commitments.allocate`. It must own its transaction topology and rejects a caller-owned production
atomic block.

1. `_persist_accepted_verification()` locks Payment, then Order, validates evidence and request
   identity, and commits one APPROVED `PaymentVerificationAttempt` with a fingerprint.
2. `_confirm_ready_order()` opens a second all-or-nothing transaction, again locks Payment then
   Order, then Order Lines, Inventory Items in UUID order and eligible Positions in primary-key
   order. Nested Commitment and Reservation composition locks the corresponding line/item, the FIFO
   pool, Positions, Reservations and Allocations.
3. It creates one Commitment, Reservation and complete Allocation split per line; sets Order Line
   confirmed/outstanding quantities; confirms Payment and appends Payment history; then moves Order
   to CONFIRMED and appends Order history.

The second transaction does not alter Stock Position on-hand and creates no Inventory Movement.
Any failure rolls back all second-transaction effects. The already accepted verification remains
as truthful durable review history and the same idempotency key can retry confirmation.

### 3.4 PROCESSING

`start_order_processing()` locks Order first, then validates/locks its Inventory Items,
Commitments, Order Lines, Positions, Reservations and Allocations in stable ordering. It requires
active staff with `orders.process`, a CONFIRMED Payment, READY-only lines and exact valid supply
structure. It changes only Order status and appends one `CONFIRMED -> PROCESSING` event. It does not
require zero prior supply and never causes supply automatically.

### 3.5 Supply and Inventory ISSUE

`supply_ready_commitment()` may run before or after PROCESSING while Order is CONFIRMED or
PROCESSING. It locks Inventory Item as the physical mutation root, then Commitment, Order Line,
Positions, Reservation and Allocations. It deterministically consumes active Allocations by their
persisted creation/time identity, composes `post_inventory_movement()` for the exact ISSUE, records
Allocation consumption, updates Reservation and Commitment equations/states, appends supply and
reservation audit facts, and reduces Order Line outstanding quantity in one transaction.

It changes neither Payment nor Order lifecycle state. A partial supply leaves ACTIVE/outstanding
facts; final supply moves Commitment to SATISFIED and Reservation to CONSUMED.

### 3.6 Fulfillment

`complete_order_fulfillment()` locks Order, Commitments, Order Lines and Reservations. It requires
active staff with `fulfillment.complete`, Order PROCESSING, Payment CONFIRMED, READY-only complete
structure, zero outstanding quantities, SATISFIED Commitments, CONSUMED Reservations and no
remaining Allocations. It atomically creates one immutable `FulfillmentCompletion`, moves Order to
FULFILLED and appends the lifecycle event. It posts no Inventory movement and changes no Payment or
supply counters.

## 4. Cancellation Lifecycle

`cancel_ready_order()` accepts only CONFIRMED or PROCESSING READY Orders with CONFIRMED Payment and
active staff holding `orders.cancel`. It locks Order first, then Inventory Items, Commitments, Order
Lines, Positions, Reservations and Allocations. For each outstanding line, its private release
composition appends a RELEASE operation/event, moves remaining Allocation quantities to released,
moves Reservation to RELEASED, moves Commitment outstanding to cancelled and zeroes Order Line
outstanding. Fully supplied lines remain SATISFIED/CONSUMED. Finally it moves Order to CANCELLED and
appends one status event in the same transaction.

Cancellation never reverses an ISSUE, increases on-hand, alters supplied history, unconfirms
Payment, creates a refund or treats a physical return as having occurred. Same-key equivalent retry
validates and returns the completed cancellation; changed reuse is rejected.

## 5. Intentionally Unavailable Capabilities

| Capability | Why unavailable | Blocker type |
|---|---|---|
| PRE_ORDER availability/confirmation/supply | No ratified, lockable Production-capacity provider or capacity reservation lifecycle | Business decisions + missing Production implementation |
| Mixed READY/PRE_ORDER confirmation | Atomic confirmation cannot truthfully confirm every line until PRE_ORDER capacity exists | Dependency |
| Production batches/capacity/releases | Current Production pages are mock/historical specifications; no runtime domain | Explicitly deferred business phase |
| Partial-release Production costing | Allocation of Batch expenses across partial releases is unresolved | Explicit owner ratification |
| Refunds, returns and voids | Excluded from current V1 lifecycle; no state/model/service | Explicitly deferred/new ratification |
| Taxes, discounts, promotions, delivery charges | Order total is exactly line totals; no policy/schema | Explicit V1 non-goal/new ratification |
| Detailed Delivery, dispatch, routes, drivers | Fulfillment is deliberately one minimal completion fact | Explicit V1 boundary/new contract |
| Customer tracking | Empty route only; authentication, rate limiting and non-enumeration contract is not implemented | Security/business contract required |
| Cancellation Inventory return | Cancellation releases only unsupplied reservations; issued goods require a distinct Return/receipt fact | Explicit boundary/new return policy |
| Reservation expiry/abandonment | No expiry state/timer/policy; PENDING abandonment also unresolved | Business policy required |
| Reservation transfer | Reservation identity is non-transferable | Explicitly prohibited |
| Standalone Reservation release | Only cancellation owns release authority and reason | Not ratified |
| Manual FIFO override | FIFO identity is immutable and no permission/field exists | Explicitly prohibited in V1 |
| Caller-selected supply split | Supply consumption order is ratified and deterministic | Explicitly prohibited |
| Allocation override outside reallocation | Only complete authorized reallocation is supported | Intentional service boundary |
| Lot-condition change | Model rejects it until an audited Inventory command exists | Ratified audit requirement, implementation absent |
| Adjustment/reversal posting | Enum and `inventory.adjust` exist, but service rejects posting until approval workflow/thresholds exist | Business policy required |
| Multi-stage transfer/in-transit workflow | Only atomic ledger TRANSFER exists | Broader workflow/approval contract required |
| Cash on Pickup, cash/card POS, partial/split payments | Payment is one full M-Pesa Payment | Explicit V1 non-goal |
| Public Order/evidence/processing/cancellation/fulfillment APIs | No phase authorized routes or UI | Intentional exposure boundary |

## 6. Confirmed Defects

### D1 — Configured public routes reference missing templates

The configured views for `/about/`, `/faq/`, `/branches/`, `/blog/`, `/blog/article/`, `/reviews/`
and `/contact/` render template paths that do not exist. A direct route diagnostic raised
`TemplateDoesNotExist` for each. This is outside the READY lifecycle but is a current repository
defect and an existing-suite coverage gap. No file was added or route changed by this audit.

No confirmed defect was found in the implemented READY confirmation, processing, supply,
cancellation or fulfillment rules.

## 7. Architectural Risks

1. **PostgreSQL behavior is unverified.** SQLite ignores `SELECT ... FOR UPDATE`; all concurrency
   claims remain provisional until the six retained tests execute on PostgreSQL.
2. **Hard-coded SQLite configuration.** `config/settings.py` has no environment-selectable
   PostgreSQL configuration and neither `psycopg` nor `psycopg2` is installed.
3. **Concurrent first-use idempotency across different lock roots.** Most commands check a unique
   key, lock the target/root, then recheck. Same-key requests aimed at different Orders, Payments or
   disjoint Inventory Items do not share that row lock and may surface a database uniqueness error
   rather than the intended changed-input validation. No PostgreSQL test covers cross-target key
   collision.
4. **Cross-domain key collision policy is not uniform.** Supply intentionally shares its parent key
   across its composed Inventory/Reservation/Allocation/Supply records. Other commands reject only
   selected domain collisions. UUID uniqueness is per table, not repository-wide. This is safe for
   current generated keys but should remain explicit in future command contracts.
5. **Initial status-event creation is not service-exclusive at model level.** Ordinary manager
   creation can append additional `previous=None -> PENDING` Order or Payment events. Admin add is
   disabled and no route exposes this, but the model guard is weaker than later transition guards.
6. **Service flags are internal conventions, not a database security boundary.** Raw SQL, a base
   `QuerySet`, or knowingly supplying private save flags can bypass Python guards. Database CHECKs
   protect local arithmetic, but cross-row truth still depends on service discipline.
7. **Master-data provisioning is incomplete.** Inventory admin is read-only and no governed
   Inventory Item/Location/Lot creation service exists. Tests create them directly; production
   provisioning requires a separately controlled process.
8. **Current development database is intentionally empty.** Catalog-backed routes fail with missing
   table errors until migrations are applied. This is an environment state, not migration drift,
   but the repository is not immediately runnable as a populated site.
9. **Capability-document/runtime mismatch.** The broad permission catalogue names many future
   capabilities not installed in Django. Customer/Product admin currently uses Django default model
   permissions; dashboard access checks `is_staff`, not `dashboard.view`. The future authorization
   contract explicitly says it is specification-only, so this is a future integration risk rather
   than authority for inventing permissions now.
10. **Catalog mutation governance remains narrower than domain services.** ProductSaleUnit changes
    and Customer/Product CRUD use admin/model validation rather than command idempotency/audit
    records. Existing Order snapshots preserve history, but future operational policy may require
    governed commands.

## 8. Historical/Stale Material

- `docs/architecture/state-machines.md` and `docs/architecture/operations.md` are explicitly marked
  superseded for V1. Their New/Under Review/Accepted/Completed/Delivered states, Cash on Pickup and
  Branch/detailed Fulfillment flows are not current runtime authority.
- `docs/contracts/checkout.md`, `order-management.md`, `order-tracking.md`, `pos.md`, delivery,
  Procurement and Production contracts are historical/future specifications where marked. They do
  not authorize models or commands.
- Phase 2–4 audits describe frontend executable specifications and mock projections, not backend
  completion. Unrouted mock templates contain Cash/Card, Branch, Delivery and old status language;
  these are not queried by current domain services.
- Phase 1D and early 1E audits truthfully describe their stage at the time but their “unavailable”
  lists are superseded by later Phase 1F/1G implementation audits.
- The original Order contract §19 describes confirmation as one transaction. Ratified Phase 1F
  decision F04 and its audit are newer authority: accepted verification is one durable transaction,
  followed by one all-or-nothing domain confirmation transaction.
- The Phase 1G audit is explicitly historical; Phase 1G-Final resolves its PROCESSING gate.
- Both Phase 1E decision gates and the Phase 1E-E supply gate are resolved and retained as decision
  history. No business gate for implemented READY processing remains open.
- `docs/architecture/permissions.md` is a broad canonical future catalogue. Only the permissions
  listed in §10 below are installed/used by current Phase 1 runtime.

## 9. Idempotency Audit

| Mutation | Identity/fingerprint | Retry behavior | Changed reuse / collision | Rollback identity |
|---|---|---|---|---|
| `create_pending_order` | unique `Order.creation_idempotency_key`; request reconstructed from persisted aggregate | returns matching Order | mismatch rejected; cross-target concurrent first use unverified | whole creation rolls back, so key is reusable after failure |
| `submit_payment_evidence` | none by design | creates another immutable evidence record | repeated claims allowed | evidence insert rolls back atomically |
| `record_rejected_verification_attempt` | unique attempt key; field comparison, no stored fingerprint | returns matching rejection | changed input rejected | failed insert leaves no key |
| `verify_payment_and_confirm_order` | unique attempt key + SHA-256 over Order, Payment, evidence, reference, actor, correlation, reason; UUIDv5 children | retries accepted failure or validates complete success | changed same-key rejected; provider reference independently unique | APPROVED identity persists; all later domain effects roll back together |
| `post_inventory_movement` | unique movement key + full request SHA-256 | returns matching movement | changed fingerprint rejected; recheck after Item locks | movement, lines and Positions roll back together |
| Commitment creation | unique creation key; matching event/fields | returns matching Commitment | changed input rejected | caller transaction owns rollback |
| Initial Reservation/Allocation | unique Reservation and operation key + source fingerprint | returns matching result | changed fingerprint rejected | caller confirmation transaction owns rollback |
| Reallocation | unique operation key + complete source fingerprint | returns appended replacement lines | changed reuse rejected | caller atomic transaction owns rollback |
| READY supply | same key/fingerprint across Supply Event and composed ISSUE/Reservation operation | returns matching Supply Event | changed fingerprint/cross-operation collision rejected | ISSUE, consumption and counters roll back together |
| PROCESSING | unique OrderStatusEvent key + exact field comparison | returns prior successful command without another event | changed reuse or different key after success rejected | Order and event roll back together |
| Cancellation | parent Order event key; deterministic UUIDv5 child keys | validates and returns completed cancellation | changed reuse/collisions rejected | releases, counters, Order and events roll back together |
| Fulfillment completion | unique completion key + SHA-256; derived Order-event key | returns matching completion | changed reuse or existing Order-event collision rejected | completion, Order and event roll back together |

The principal inconsistency is representation: some commands persist SHA-256 fingerprints, while
Order creation, rejected verification, PROCESSING and cancellation compare persisted fields. This
does not presently change same-process semantics, but it makes cross-target concurrent collision
handling and audit uniformity uneven.

## 10. Permission Audit

Current consequential service permissions are:

| Mutation/read | Required authority | Active staff enforced? | Superuser semantics | Explicit grant model |
|---|---|---:|---|---|
| Ecommerce PENDING creation | none | No; guest-capable | n/a | Intentional public service boundary, not exposed by HTTP |
| POS PENDING creation | `pos.process_sale` | Yes | Normal `has_perm()` | Custom permission created by RunPython migration |
| Ecommerce evidence | none | No | n/a | Untrusted submission; currently no endpoint |
| POS evidence | `pos.process_sale` | Yes | Normal | Same custom permission |
| Staff evidence/rejected verification | `payments.verify` | Yes | Normal | Native custom model permission |
| READY confirmation | `payments.verify` + `commitments.allocate` | Yes | Normal | Both required |
| Inventory read admin | `inventory.view` | Admin framework also requires staff | Normal | Native custom permission |
| Receipt | `inventory.receive` | Yes | Normal | Native custom permission |
| Issue/supply | `inventory.release` | Yes | Normal | Native custom permission |
| Transfer | `inventory.transfer` | Yes | Normal | Native custom permission |
| FIFO/internal supply read | `commitments.view` | Yes | Normal | Native custom permission |
| Initial allocation/reallocation | `commitments.allocate` | Yes | Normal | Native custom permission |
| PROCESSING | `orders.process` | Yes | Normal | Native custom permission |
| Cancellation | `orders.cancel` | Yes | Normal | Native custom permission |
| Fulfillment completion/read admin | `fulfillment.complete` | Yes | Normal | Only Fulfillment permission; default permissions disabled |
| Order read admin | `orders.view` | Yes/admin staff | Normal | Native custom permission |
| Customer/Catalog admin CRUD | Django default add/change/view permissions | Django admin requires active staff | Normal | Broad `customers.manage`/`products.manage` catalogue names are not installed |
| Empty staff dashboard pages | authenticated `is_staff` | Active status is enforced by Django authentication backend/session behavior, view checks staff | Superusers normally staff | Does not use planned `dashboard.view` |

No runtime domain service authorizes by role name, username, department, Branch or frontend
visibility. Direct and group Django grants work; active superusers inherit permissions normally.
The richer role/scope/delegation/separation-of-duties system is documentation-only.

## 11. Transaction & Locking Audit

| Operation | Atomic boundary and lock order | Rows not locked / observations |
|---|---|---|
| Order creation | one atomic block; matching Order key, optional Customer; Catalog rows read | No common lock for two first requests with same key and no Customer |
| Evidence | one atomic block; Payment | Evidence history is append-only and intentionally repeatable |
| Confirmation acceptance | atomic; Payment → Order | Evidence read, not locked; immutable |
| Confirmation domain commit | atomic; Payment → Order → Order Lines → Inventory Items sorted UUID → eligible Positions sorted PK → nested FIFO Commitments/Reservations/Allocations | Product/Catalog snapshots already immutable on Order; accepted attempt is outside this rollback boundary by ratification |
| Inventory movement | atomic; existing key → Items sorted → Lots sorted → Locations sorted → Positions sorted composite identity | Unique-key race across disjoint Item pools remains unverified |
| Reservation/allocation | caller-owned atomic; Item → FIFO Commitments → Positions → Reservations → Allocations, stable ordering | Public misuse without outer transaction is rejected |
| Reallocation | caller-owned atomic; Item → Positions → Reservations → Allocations | Same stable Item supply-pool root |
| Supply | atomic; Item → Commitment → Order Line → Positions → Reservation → Allocations; nested ISSUE reacquires Item then locks Lot/Location/Positions | Order is read through Commitment but not row-locked; supply does not change Order status |
| PROCESSING | atomic; Order → Items sorted → Commitments/Lines → Positions sorted → Reservations → Allocations | Payment is validated but not locked; it is immutable after confirmation |
| Cancellation | atomic; Order → Items sorted → Commitments/Lines → Positions sorted → Reservations/Allocations; nested release follows Item/Position/Reservation/Allocation | Payment read only; supplied stock is outside release path |
| Fulfillment | atomic; Order → Commitments → Lines → Reservations | Allocations are checked but not explicitly locked; prior Commitment/Reservation locks serialize current supply service ordering |

No immediate lock-order cycle was found among current services: operations that lock Order before
Item do not later wait on a lock held by a service that also waits for Order; supply locks Item but
does not lock/update Order. Nevertheless, only PostgreSQL execution can validate blocking,
deadlocks and visibility under real `READ COMMITTED` behavior.

## 12. PostgreSQL Verification Gap

`apps/orders/test_postgresql_concurrency.py` contains six `TransactionTestCase` tests guarded by
`connection.vendor == "postgresql"`:

1. `test_two_confirmations_cannot_reserve_the_same_supply` — one physical pool cannot confirm two
   competing Orders beyond capacity.
2. `test_supply_and_cancellation_serialize_without_quantity_corruption` — supply/cancellation leave
   exact supplied+cancelled and zero-outstanding equations.
3. `test_two_processing_requests_with_same_key_are_one_transition` — equivalent concurrent retries
   create one PROCESSING event.
4. `test_two_processing_requests_with_different_keys_have_one_winner` — only one different-key
   transition succeeds.
5. `test_processing_and_cancellation_serialize_without_corruption` — competing lifecycle commands
   serialize to a valid CANCELLED result.
6. `test_two_completion_retries_with_same_key_are_one_completion` — concurrent equivalent
   completion creates one completion and one FULFILLED event.

SQLite cannot prove these because its locking model does not implement PostgreSQL row-level
`SELECT FOR UPDATE` behavior. The repository currently hard-codes SQLite, has no PostgreSQL
settings variant, contains no PostgreSQL environment/CI configuration, and has no installed
`psycopg`/`psycopg2` driver.

Execution requires an isolated supported PostgreSQL server/database, a least-privilege test user
allowed to create/drop the Django test database (or a precreated test database), an installed
supported psycopg driver, environment-driven Django database settings, migrated schema, and the
same six tests run without their skip condition. Results must include deadlock/time-out diagnostics
and may not be inferred from SQLite.

## 13. Migration Audit

- Project migration files: 15 across Accounts, Customers, Products, Orders, Payments, Inventory,
  Commitments and Fulfillment.
- `showmigrations --plan` resolved one linear dependency plan plus Django built-ins; the untouched
  development database correctly showed every migration unapplied.
- `makemigrations --check --dry-run`: **No changes detected**.
- A clean isolated database applied the complete graph during each test run.
- No `RunSQL`, destructive field/model removal or rename exists.
- The only `RunPython` is reversible `orders.0002_pos_process_sale_permission`, which creates the
  synthetic `pos.process_sale` permission/content type.
- Later migrations are additive or metadata/choice alterations. Historical migrations were not
  rewritten or squashed.
- `db.sqlite3` remained exactly 0 bytes before and after audit commands.

## 14. Test Audit

Commands and results:

- Focused lifecycle stack: `manage.py test apps.orders.test_processing
  apps.orders.test_lifecycle apps.payments.test_confirmation apps.commitments.test_supply
  apps.inventory.test_reservations apps.inventory.test_availability` — **86/86 passed**.
- Implemented domains: Accounts, Customers, Products, Orders, Payments, Inventory, Commitments and
  Fulfillment — **235 discovered; 229 passed; 6 PostgreSQL-only skipped**.
- Full suite: **251 discovered; 245 passed; 6 PostgreSQL-only skipped**.
- `manage.py check` — passed with no issues (also executed by every test run).
- `manage.py check --deploy` — failed as expected for current non-production configuration with
  `payments.E001` plus Django security warnings W004, W008 and W009.
- `makemigrations --check --dry-run` — no changes detected.
- `git diff --check` — passed; existing LF→CRLF notices only.

The suite does not test the seven configured missing-template routes, cross-target concurrent
idempotency-key reuse, or the production deployment configuration.

## 15. Security & Privacy Audit

- Raw M-Pesa messages use `EncryptedTextField` with Fernet/MultiFernet and are decrypted only on
  model loading. No application logger/print path includes evidence.
- Evidence admin omits `submitted_message` and exposes only a `message_present` boolean. It is
  read-only and requires `payments.verify`.
- `PaymentEvidence.__str__` contains only its UUID. Payment/provider references are not exposed by
  public Order/Payment pages, which are empty states.
- Customer-safe availability contains only sale-unit count, calculation time and coverage. FIFO,
  Location, Lot, Position, Reservation and Allocation identities are absent.
- Order/Payment/Inventory/Commitment/Fulfillment admin registrations are read-only and permission
  gated. Internal actors, correlations and reasons remain admin/internal facts.
- No public route returns persisted Orders, Payments, Commitments, Reservations, Allocations or
  audit records. Customer tracking is not implemented.
- Production cannot safely handle real evidence until explicit
  `PAYMENT_EVIDENCE_ENCRYPTION_KEYS` are configured. The development SECRET_KEY-derived fallback is
  intentionally rejected by the deploy check.
- Deployment also requires a strong SECRET_KEY, HTTPS redirect/proxy configuration and an owner
  decision before HSTS. These are technical deployment blockers, not new business rules.

## 16. Documentation/Contract Audit

Current authority by domain:

| Domain | Current authoritative record |
|---|---|
| Cross-domain V1 | `docs/architecture/v1-business-contract.md` |
| Customer, Order, Payment, minimal Fulfillment | `docs/architecture/order-customer-payment-contract.md`, refined by Phase 1F and Phase 1G-Final ratifications |
| Inventory, Availability, Commitment, Reservation, Allocation, Supply | `docs/architecture/availability-commitment-contract.md`, including AC01–AC28 and resolved Phase 1E-E D01–D14 |
| CONFIRMED→PROCESSING | `docs/reviews/phase-1g-processing-decision-gate.md` as ratified/implemented, plus Phase 1G-Final audit |
| Implementation evidence | Phase 1D, 1E-A through 1E-E, 1F, historical 1G and Phase 1G-Final audits in chronological order |

No current READY business decision gate remains open. Open decisions include Production capacity
and partial-release costing, adjustment/approval thresholds, Payment-evidence retention, pending
Order abandonment, tracking security, and any future Delivery/return/refund policy.

Implementation status is mostly synchronized in the Phase 1 audit chain. The main documentation
risk is that broad Phase 2–4 UI/authorization/capability material remains present and sometimes uses
“canonical” language despite being explicitly future or superseded elsewhere. The Phase 1G audit
also retains a historical sentence about unresolved PROCESSING authority; its header/opening and
Phase 1G-Final clearly establish the newer rule.

## 17. Current Architecture Map

```text
accounts.User ───────────────┐
                            │ actor + Django permissions
customers.Customer ─┐       │
                    ├──> orders.Order (PENDING) ──> payments.Payment (PENDING)
products.Catalog ───┘                 │                       │
                                     │     evidence + accepted verification
inventory Items/Lots/Positions ─> READY Availability          │
                 │                   │                         │
                 └──────── confirmation orchestrator <────────┘
                                      │
                                      ├──> Commitment (FIFO entitlement)
                                      ├──> Reservation (aggregate physical partition)
                                      ├──> Source Allocations (hidden location/lot split)
                                      └──> Order + Payment CONFIRMED

CONFIRMED Order ──explicit orders.process──> PROCESSING Order
       │                                         │
       ├──────── supply may occur here ──────────┤
       │          └─> Allocation consumption
       │              + Reservation/Commitment counters
       │              + Inventory ISSUE
       │
       ├── orders.cancel ──> release remaining supply ──> CANCELLED
       └── PROCESSING + all supplied ──> FulfillmentCompletion ──> FULFILLED
```

The actual system is not a strict `Supply -> Processing` pipeline: supply is valid on either side
of the explicit PROCESSING transition. Payment confirmation orchestrates Commitment and
Inventory-owned Reservation/Allocation creation; Payment does not own them.

## 18. Remaining Work

### A. Verification-only

- Configure PostgreSQL and execute all six concurrency tests.
- Exercise cross-target same-key collision races and capture database exception semantics.
- Run deployment checks with real secrets/TLS configuration in the target environment.

### B. Already-ratified but not implemented

- A governed staff Customer search/select boundary using ratified customer permissions remains
  absent outside Django admin.
- Audited Lot-condition change is required by the Inventory contract but has no command.
- The V1 direction for external/manual receipts includes lot-specific cost/source information; the
  minimum current receipt ledger does not implement costing.
- Public/customer READY availability projection exists as code but is not wired to an endpoint/UI.

These items still require phase authorization before implementation even where their high-level
business direction is ratified.

### C. Business decisions required

- Production-capacity facts, locks, required-date eligibility, reservation/release and shortfall
  handling for PRE_ORDER/mixed confirmation.
- Partial Production release costing and allocation of Batch expenses.
- Adjustment/reversal thresholds, approvers and separation of duties.
- Payment-evidence retention/deletion policy.
- Pending Order expiry/abandonment policy.
- Customer tracking authentication, rate limits and non-enumerable responses.
- Delivery, return, refund and any cancellation-return policy.

### D. Explicitly deferred

PRE_ORDER supply, Production, detailed Delivery, tracking, returns, refunds, discounts,
promotions, taxes, delivery charges, Cash on Pickup, cash/card settlement, split payments, generic
UOM, Branch assignment, manual FIFO override, standalone Reservation release and automatic expiry.

### E. Technical debt / risks

- Repair or retire the seven missing-template routes and add route smoke coverage.
- Add environment-driven database configuration and PostgreSQL driver/CI service.
- Make idempotency collision behavior uniform across different target aggregates.
- Decide whether initial PENDING event creation needs a stricter service-only guard.
- Clearly label installed versus future permissions in the broad capability catalogue.
- Establish governed Inventory master-data provisioning before operational deployment.
- Configure production encryption keys, SECRET_KEY and HTTPS controls.

## 19. Recommended Next Actions

1. Do not begin another product phase yet.
2. First create a technical verification environment using PostgreSQL and run the retained six-test
   concurrency suite unchanged.
3. Separately authorize a narrow non-business hardening pass for the confirmed missing-template
   routes, production settings and route smoke coverage.
4. Review the cross-target idempotency and initial-event risks; decide whether they require a
   ratified technical hardening change before production.
5. Only then choose a product phase after the owner resolves its business decisions and explicitly
   authorizes scope.

## 20. Recommended Next Phase

The safest immediate “phase” is a **verification and deployment-hardening gate**, not a new product
capability. It has no authority to change business rules: its purpose is PostgreSQL proof,
production configuration, route integrity and closure of the technical risks above.

After that gate, the strongest candidate for owner consideration is a separately ratified
**Production-capacity and PRE_ORDER contract/implementation phase** because PRE_ORDER and mixed
Order modes already exist at PENDING creation but cannot progress. It must not start until the owner
decides capacity authority, locking/reservation facts, required-date behavior, release/shortfall
handling and partial-release costing. Alternatives are a customer-tracking security phase, an
Inventory adjustment/condition-governance phase, or a minimal Delivery phase; each has independent
policy dependencies and none is automatically authorized by this audit.

## 21. Explicit Non-Goals of This Audit

This audit added no model, migration, service, permission, route, UI, fixture, seed data, test or
runtime behavior. It did not repair missing routes, configure PostgreSQL, configure secrets, invent
PRE_ORDER capacity, broaden permissions, expose internal data or reinterpret historical frontend
specifications as current business authority.

## Final Status Declaration

- **COMPLETE:** Phase 1G-Final READY-domain implementation, including explicit PROCESSING,
  cancellation and minimal fulfillment, is complete within ratified scope.
- **VERIFIED:** Model/service behavior, migration graph and 245 executable tests are verified in the
  configured SQLite environment; migration drift and ordinary Django checks are clean.
- **IMPLEMENTED BUT UNVERIFIED:** PostgreSQL row-lock/concurrency behavior for confirmation, supply,
  cancellation, processing and completion.
- **BLOCKED:** production deployment is blocked by PostgreSQL infrastructure/proof and explicit
  evidence-encryption/security configuration; seven peripheral public routes are broken by missing
  templates.
- **REQUIRES EXPLICIT OWNER RATIFICATION:** Production-capacity/PRE_ORDER details, partial-release
  costing, adjustment approvals, evidence retention, pending abandonment, tracking security,
  Delivery, returns/refunds and selection of any next product phase.
