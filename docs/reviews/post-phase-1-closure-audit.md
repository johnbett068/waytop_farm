# Post-Phase-1 Closure Audit

Audit date: 21 August 2026
Scope: repository state after the completed PostgreSQL verification gate

## 1. Executive Summary

The service-layer READY lifecycle is technically complete and PostgreSQL verified for its ratified
scope:

`PENDING -> CONFIRMED -> PROCESSING -> FULFILLED`

The only ratified cancellation transitions are:

- `CONFIRMED -> CANCELLED`
- `PROCESSING -> CANCELLED`

The directive's proposed `PENDING -> CANCELLED` path is not authoritative. Both the current Order
contract and `cancel_ready_order()` expressly prohibit it. PENDING abandonment/expiry remains an
owner decision and must not be represented as cancellation.

The lifecycle preserves the separation between commercial demand, financial truth, customer
entitlement and physical stock. Confirmation creates complete READY Commitments, Reservations and
Source Allocations but does not change on-hand stock. Supply alone posts an immutable ISSUE and
reduces on-hand. Cancellation releases only unsupplied Reservations/Allocations, preserves issued
stock and the confirmed Payment, and does not invent a refund or return.

PostgreSQL 18.4 executed all six retained concurrency tests and the complete 258-test suite with no
skip, failure or error. Two genuine locking defects were exposed and repaired without changing
business semantics. The READY lifecycle therefore has no known verified correctness defect.

Phase 1 nevertheless closes with technical debt outside the proven state path: PostgreSQL is not
yet a repository CI gate; cross-root concurrent idempotency-key collision behavior is not uniformly
tested; initial PENDING event creation has a weaker service-only guard than later transitions; and
seven configured public routes point to absent templates. Production also requires real external
secrets, database/TLS configuration and an operational provisioning process. The correct final gate
is **B**, not because READY behavior is incomplete, but because hardening remains before production.

## 2. Implemented Capabilities

| Capability | Implemented boundary | Verification status |
|---|---|---|
| Accounts and staff authentication | UUID Django User, hashed passwords, active/staff checks, groups and native permissions | Model, authentication, CSRF and access tests passed |
| Customer foundation | UUID Customer, normalized Kenyan E.164 phone, lowercase email, reusable protected addresses, explicit attachment only | Positive/negative model and admin tests passed |
| Persistent Catalog | Product, Sale Unit, effective immutable Price history and customer-safe public projection | Model, pricing, route and projection tests passed |
| PENDING Order creation | One Ecommerce/POS aggregate with immutable snapshots, server pricing, full Payment and initial history | Atomicity, validation, permissions and idempotency tests passed |
| Payment evidence | Repeatable append-only evidence; encrypted raw message; source-specific authorization | Encryption-at-rest, duplicates, immutability, admin and leakage tests passed |
| Rejected verification | Authorized immutable rejection history | Permission and idempotency tests passed |
| READY confirmation | Durable accepted verification followed by all-or-nothing Payment/Order/Commitment/Reservation/Allocation commit | Domain rollback tests and competing-confirmation PostgreSQL test passed |
| Inventory ledger | Receipt, ISSUE and transfer movements with immutable lines and lockable Stock Positions | Ledger, rollback, idempotency and negative-stock tests passed |
| READY Availability | Eligible on-hand less ACTIVE remaining Reservations, converted by floor to aggregate sale units | Eligibility, precision, provider-failure and redaction tests passed |
| Commitment/FIFO | One Commitment per line, immutable priority and exact commercial/base equations | Constraint, FIFO, immutability and permission tests passed |
| Reservation and Allocation | Exact aggregate Reservation plus complete deterministic source allocation and reallocation history | Quantity, eligibility, split-source, FIFO and rollback tests passed |
| READY supply | Whole-sale-unit partial/full supply, atomic ISSUE and Reservation/Allocation consumption | Supply equations, source ordering, rollback and PostgreSQL cancellation-race test passed |
| PROCESSING | Explicit CONFIRMED-to-PROCESSING service with no financial or supply mutation | Permission, invariant, rollback, idempotency and two PostgreSQL race tests passed |
| Cancellation | CONFIRMED/PROCESSING READY cancellation and release of only remaining entitlement | Partial/full supply, rollback, idempotency and two PostgreSQL race tests passed |
| Minimal fulfillment | One immutable completion after complete supply; PROCESSING-to-FULFILLED | Invariant, permission, rollback, idempotency and PostgreSQL retry test passed |
| Read-only operational admin | Order, Payment, Inventory, Commitment, Allocation and Fulfillment facts permission-gated and non-writable | Admin permission and mutation tests passed |
| Environment hardening | Environment-selected SQLite/PostgreSQL, isolated test DB, external production secrets and secure defaults | Environment tests and production-shaped deploy check passed |

These are domain/service capabilities. There are deliberately no HTTP command endpoints for Order
creation, evidence, confirmation, Inventory posting, allocation, supply, cancellation, processing
or fulfillment. Existing public Order pages render honest unavailable states; staff dashboard pages
are staff-only empty projections. Service completion must not be confused with a released product
workflow.

## 3. READY Lifecycle

### 3.1 Verified state machine

```text
PENDING --verify payment and atomically establish READY promise--> CONFIRMED
CONFIRMED --start fulfillment work-------------------------------> PROCESSING
PROCESSING --after complete physical supply----------------------> FULFILLED
CONFIRMED --------------------------------------------------------> CANCELLED
PROCESSING -------------------------------------------------------> CANCELLED
```

There is no generic status-write command. Direct instance, queryset, bulk and admin mutation paths
are guarded, and each transition validates its aggregate again under locks.

### 3.2 PENDING creation

- **Authority:** guest-capable for Ecommerce; POS requires authenticated active staff with
  `pos.process_sale`.
- **Prerequisites:** valid channel/fulfillment/contact/address combination; active published
  Product and active Sale Unit; effective server-selected ProductPrice; positive integer quantity;
  PRE_ORDER requires a required date; total must be positive KES.
- **Transaction and locks:** one `transaction.atomic()` block. A same-key existing Order is locked;
  an explicitly attached Customer is locked before creation. Catalog facts are reselected and
  snapshotted.
- **Idempotency:** globally unique creation key; an exact retry returns the same aggregate and
  changed reuse is rejected.
- **Audit:** initial Order and Payment PENDING events plus immutable contact/address and line facts.
- **Side effects:** creates Order, lines, snapshots and one full PENDING M-Pesa Payment. It creates no
  Commitment, Reservation, Allocation or Inventory movement. Confirmed/outstanding line quantities
  remain zero and on-hand is unchanged.
- **Rollback/customer visibility:** any validation or insert failure removes the entire aggregate.
  No live checkout endpoint currently calls the service.
- **PostgreSQL status:** exercised by the full PostgreSQL suite; concurrent first use of one creation
  key against disjoint roots is not a retained concurrency scenario.

### 3.3 Payment evidence and verification

- **Evidence authority:** Ecommerce submission is untrusted/public; POS requires
  `pos.process_sale`; staff submission requires `payments.verify`.
- **Evidence transaction:** locks the PENDING Payment and appends one immutable evidence record.
  Duplicate claims are intentionally retained and evidence has no idempotency key.
- **Rejection authority/history:** active staff with `payments.verify`; same-key exact retries return
  one immutable REJECTED attempt and changed reuse is rejected. Payment and Order remain PENDING.
- **Acceptance:** active staff must hold both `payments.verify` and `commitments.allocate`. The first
  owned transaction locks Payment then Order and durably appends the APPROVED attempt. This is the
  ratified Phase 1F F04 behavior and supersedes older documents that describe every fact as one
  transaction.
- **Privacy:** raw submitted messages are encrypted with Fernet/MultiFernet, omitted from strings,
  logs, public views and admin fields. A claimed reference is not the canonical provider reference.

### 3.4 PENDING to CONFIRMED

- **Authority:** authenticated active staff with both `payments.verify` and
  `commitments.allocate`; standard Django superuser permission semantics are retained.
- **Prerequisites:** matching PENDING Order/Payment/evidence; READY-only non-empty lines; KES totals
  agree; M-Pesa reference is normalized and not already confirmed elsewhere; compatible active
  Inventory Item per Product; sufficient locked aggregate READY availability.
- **Transaction and locks:** after durable acceptance, one separate all-or-nothing domain
  transaction locks Payment, Order, Order Lines, sorted Inventory Items, eligible Stock Positions,
  FIFO Commitments and the Reservation/Allocation pool in stable order.
- **Idempotency:** approved attempt stores a SHA-256 request fingerprint under a unique key; child
  facts use deterministic UUIDv5 keys. Exact retries validate and return the completed result;
  changed reuse is rejected.
- **Audit:** APPROVED attempt, Commitment creation events, Reservation and Allocation operations,
  Payment PENDING-to-CONFIRMED event and Order PENDING-to-CONFIRMED event share actor/correlation
  identity.
- **Side effects:** one Commitment, one exact Reservation and complete Source Allocation per line;
  line confirmed/outstanding become ordered quantity; Payment receives canonical reference,
  verifier and time; Order becomes CONFIRMED.
- **Deliberately unchanged:** StockPosition on-hand, Inventory movement ledger, Product/Catalog,
  customer profile and required commercial quantities.
- **Rollback:** any domain failure rolls back every confirmation/supply-promise fact while retaining
  the truthful APPROVED attempt. A same-key retry can complete after the problem is corrected.
- **Customer visibility:** the service returns the Order only and never internal source data. No
  customer confirmation/tracking projection is wired to it.
- **PostgreSQL status:** competing confirmations were proved unable to over-reserve one supply pool.

### 3.5 CONFIRMED to PROCESSING

- **Authority:** authenticated active staff with `orders.process` and a non-empty reason.
- **Prerequisites:** CONFIRMED Order and Payment; READY-only lines; exactly matching Commitments,
  Reservations and Allocation history; all quantity/state equations valid. Partial supply is valid.
- **Transaction and locks:** Order, sorted Items, Commitments/Lines, sorted Positions,
  Reservations and Allocations are locked and revalidated in one atomic block.
- **Idempotency/audit:** unique Order-event key and exact input comparison; same-key retry produces
  one transition, changed reuse is rejected; immutable CONFIRMED-to-PROCESSING event is appended.
- **Side effects:** only Order status changes. Payment, line quantities, Commitments, Reservations,
  Allocations, Stock Positions and movement history are deliberately unchanged.
- **Rollback/customer visibility:** event failure restores CONFIRMED. No public processing command
  or tracking surface exists.
- **PostgreSQL status:** same-key retries create one transition; different keys have one winner.

### 3.6 Supply while CONFIRMED or PROCESSING

- **Authority:** authenticated active staff with `inventory.release`.
- **Prerequisites:** READY ACTIVE Commitment belonging to a CONFIRMED/PROCESSING Order with confirmed
  Payment; positive whole-sale-unit quantity not exceeding outstanding; ACTIVE Reservation and
  sufficient eligible Allocation/Position quantity.
- **Transaction and locks:** Inventory Item first, then only the Commitment row from its joined
  query, Order Line, stable Stock Positions, Reservation and Allocations. The composed Inventory
  ISSUE participates in the same transaction.
- **Idempotency/audit:** one request fingerprint/key coordinates immutable Supply Event, ISSUE,
  Reservation event, Allocation operation/consumption and updated counters.
- **Side effects:** ISSUE decreases on-hand; selected Allocations and Reservation are consumed in
  deterministic allocation creation order; Commitment supplied increases/outstanding decreases;
  Order Line outstanding decreases. Full supply produces SATISFIED/CONSUMED.
- **Deliberately unchanged:** Payment and Order status, committed/confirmed/ordered quantities and
  other Customers' public data.
- **Rollback:** insufficient or ineligible stock, invalid split or any late failure restores the
  entire movement and every counter.
- **PostgreSQL status:** supply and cancellation serialize without quantity corruption.

### 3.7 PROCESSING to FULFILLED

- **Authority:** authenticated active staff with `fulfillment.complete`.
- **Prerequisites:** PROCESSING READY Order, CONFIRMED Payment, every line and Commitment outstanding
  zero, all Commitments SATISFIED, all Reservations CONSUMED and no active Allocation remainder.
- **Transaction and locks:** Order, Commitments, Order Lines and Reservations are locked and
  revalidated in one atomic block.
- **Idempotency/audit:** completion fingerprint/key plus derived Order-event key; exact retries return
  one completion, changed reuse is rejected. One immutable FulfillmentCompletion and
  PROCESSING-to-FULFILLED event are written.
- **Side effects:** only completion history and Order status. No additional Inventory movement,
  Delivery job, driver, route, Payment or quantity mutation occurs.
- **Rollback/customer visibility:** completion/event failure restores PROCESSING. No public
  fulfillment/tracking projection exists.
- **PostgreSQL status:** concurrent same-key completion retries produce one completion and event.

### 3.8 CONFIRMED/PROCESSING to CANCELLED

- **Authority:** authenticated active staff with `orders.cancel` and a non-empty reason.
- **Prerequisites:** CONFIRMED or PROCESSING READY Order with truthful CONFIRMED Payment and complete
  Commitment/Reservation/Allocation structure. PENDING, FULFILLED and already unrelated terminal
  requests are rejected.
- **Transaction and locks:** Order, sorted Items, Commitments/Lines, sorted Positions, Reservations
  and Allocations are locked. Release and lifecycle writes share one atomic transaction.
- **Idempotency/audit:** parent Order-event key and deterministic child keys; exact retry validates
  the completed aggregate, while changed reuse/cross-operation collisions are rejected. Allocation,
  Reservation, Commitment and Order histories are appended.
- **Side effects:** remaining Allocation and Reservation quantities become released; remaining
  Commitment quantity moves from outstanding to cancelled; line outstanding becomes zero; Order
  becomes CANCELLED.
- **Deliberately unchanged:** issued/on-hand stock, supplied quantities, ordered/confirmed
  quantities, historical movements and the CONFIRMED Payment. No refund or return is implied.
- **Rollback/customer visibility:** any late failure restores all releases, counters and status.
  The status is customer-safe in principle, but no authenticated tracking surface exists.
- **PostgreSQL status:** supply/cancellation and processing/cancellation both serialize to valid
  equations and terminal state.

## 4. Financial Integrity

V1 has exactly one full Payment per Order, fixed to KES and M-Pesa; amount equals the immutable Order
total. There are no split, partial, cash/card, refund or void facts. PENDING requires null
confirmation metadata; CONFIRMED requires provider reference, verifier and time. A conditional
database uniqueness constraint on `(method, provider_reference)` prevents confirmed reference
reuse across Payments.

Evidence is append-only untrusted input. Duplicate evidence is expected and does not reserve a
provider reference or imply confirmation. Raw messages are encrypted before persistence, decrypted
only through the model field and omitted from public/admin rendering. Rejected and accepted attempts
are immutable, authorized and independently auditable.

Confirmation deliberately has two transaction boundaries: durable acceptance, then the complete
READY domain commit. This makes a failed downstream confirmation truthful and retryable rather than
erasing an approved staff decision. The domain transaction itself is atomic: no partial Payment,
Order, line, Commitment, Reservation or Allocation success survives. Confirmation keys are
fingerprinted; canonical provider-reference uniqueness is separately database-enforced.

Cancellation does not reverse the confirmed Payment. Refund policy and refund accounting are
absent by design, so operators must not interpret CANCELLED as refunded.

## 5. Inventory Integrity

Immutable InventoryMovement headers and lines are the authoritative quantity ledger. StockPosition
is the transactionally maintained, row-lockable concurrency projection and must be rebuildable from
the ledger. Position identity is unique by Item, Location and Lot; on-hand is non-negative
`Decimal(32,3)` and carries a version. Direct Position/movement CRUD and bulk writes are blocked;
database checks prevent negative balances even if Python validation is bypassed.

Implemented movement commands are RECEIPT, ISSUE and TRANSFER. Receipt increases a destination;
ISSUE decreases a source; transfer decreases and increases explicit positions atomically.
ADJUSTMENT_IN, ADJUSTMENT_OUT and REVERSAL exist as schema vocabulary but posting is unavailable
until approval policy is ratified. Lot-condition change likewise requires an audited command that
does not yet exist.

READY eligibility requires active compatible Item, active saleable Location, active SALEABLE Lot,
non-expired lot on the Africa/Nairobi business date and positive on-hand. Availability is:

`eligible on-hand - ACTIVE Reservation remaining`

then floor-divided by the current Sale Unit base quantity. Allocation partitions a Reservation and
is not deducted a second time. Missing/unhealthy providers return unavailable, while truly empty
Inventory returns zero. The public value contains count, calculation time and coverage only.

Reservation, initial/replacement Allocation, confirmation and cancellation do **not** change
on-hand. Supply changes on-hand only through the correlated ISSUE. Cancellation releases only
unconsumed entitlement and never returns already issued stock. Reallocation appends release and new
source lines; it does not rewrite history.

## 6. Commitment Integrity

Each Order Line has at most one Commitment, and confirmation requires exactly one for every READY
line. Its immutable facts are ordered commercial quantity, snapshotted base quantity per sale unit,
total base quantity, Product/Item/line identity, supply mode, confirmation time, FIFO sequence and
creation audit identity.

Both commercial and base quantities enforce:

`committed = supplied + cancelled + outstanding`

Reservation and each Source Allocation enforce:

`initial = consumed + released + remaining`

Supply is restricted to positive whole sale units. Supplied/cancelled never decrease, outstanding
never exceeds committed, SATISFIED means zero outstanding with zero cancelled, and CANCELLED
preserves supplied history while moving the remainder to cancelled. Required date is null for READY;
PRE_ORDER copies the Order required date but is not confirmable.

Customer-entitlement FIFO sorts by `confirmed_at`, then database-generated sequence, within
compatible Inventory Item and supply mode. Required date does not promote a later entitlement and
there is no override permission. Physical source selection is separate: expiry first (null last),
then lot creation time, Location code and stable ID. Supply consumes Allocation lines by creation
order with UUID tie-break and may cross Lots/Locations without caller-selected splitting.

SupplyEvent, CommitmentEvent, ReservationEvent, Allocation operations/consumptions and Inventory
ISSUE retain correlated, immutable source history. Cancellation releases only outstanding READY
facts. PRE_ORDER capacity reservation, supply and expiry are absent.

## 7. PostgreSQL Verification

- PostgreSQL **18.4**
- psycopg **3.3.4**
- Concurrency module: **6/6 passed**
- Full PostgreSQL suite: **258/258 passed**
- Skipped: **0**
- Failed: **0**
- Errors: **0**

The six authoritative scenarios proved:

1. competing confirmations cannot reserve the same physical supply;
2. supply and cancellation serialize without quantity corruption;
3. same-key PROCESSING retries produce one transition;
4. different-key PROCESSING requests have one winner;
5. PROCESSING and cancellation serialize to a valid result; and
6. same-key fulfillment completion retries produce one completion.

PostgreSQL first rejected the pending-order lock because `FOR UPDATE` traversed nullable snapshot
outer joins. Removing the joined snapshot load leaves the same Order-only lock and lazily reads the
immutable snapshots; no input, state or idempotency semantics changed.

The next run exposed a supply/cancellation deadlock because `select_related("order", "order_line")`
caused PostgreSQL to lock the joined Order. Scoping that lock to `of=("self",)` preserves the read
join while locking only Commitment, restoring the intended Item-first supply ordering. No quantity,
permission, FIFO, cancellation or lifecycle rule changed.

The complete migration graph applied to clean PostgreSQL test databases. The isolated control and
test databases were distinct, teardown left zero test databases, and the disposable localhost-only
SCRAM cluster and credentials were removed without logging or committing secrets.

## 8. Security and Deployment

- Production rejects the development SECRET_KEY fallback and requires a strong external key.
- Production requires explicit non-wildcard `ALLOWED_HOSTS`.
- Payment evidence requires one or more external Fernet keys; the first encrypts and all configured
  keys decrypt to support rotation. The deploy check rejects a missing/invalid key.
- Secure session/CSRF cookies, HTTPS redirect and a one-year HSTS default activate when DEBUG is
  false; subdomain/preload choices remain deployment-owner decisions.
- PostgreSQL credentials and optional SSL mode are environment supplied. An explicit test database
  must differ from the connection database.
- Consequential services require authenticated active staff plus explicit Django permissions. No
  role name, username, Branch, department or visible UI substitutes for authority.
- Normal Django superuser permission semantics are preserved; superuser status does not bypass the
  service's active/staff requirements.
- Order, Payment, Inventory, Commitment/Allocation and Fulfillment admin surfaces are read-only and
  capability-gated. Evidence admin shows only message presence, not raw text.
- Public projections expose neither raw evidence/provider references nor Inventory Position,
  Location, Lot, FIFO, Reservation, Allocation, staff or internal audit facts.

The production-shaped deploy check passed, but that proves configuration mechanics, not that a
specific deployment has injected its final secret values, trusted proxy/TLS settings, database
backup/restore plan, reviewed role grants or monitoring. Those remain release-environment actions.
Payment-evidence key rotation and eventual retention/deletion require an operational procedure.

## 9. Route and Template Integrity

### Implemented

- Home and persistent Catalog shop/search/product/category behavior.
- Account login/profile with staff access boundaries.
- Cart and Wishlist prototype-safe empty/persistent-session behavior.
- Order checkout/success/tracking/history routes that intentionally render one honest unavailable
  template and do not fabricate Orders.
- Staff dashboard, Order, Inventory, POS and Production URLs that are staff-only empty projections;
  they do not invoke domain commands or claim backend capability.
- Error pages and shared page-state components.

### Requires product/content decision and is currently a configured defect

| Route | Missing template | Classification |
|---|---|---|
| `/about/` | `core/about.html` | Configured render stub; content or retirement decision required |
| `/faq/` | `core/faq.html` | Configured render stub; authoritative FAQ content or retirement required |
| `/branches/` | `branches/branches.html` | Branch facts/content are not ratified |
| `/blog/` | `blog/blog.html` | Scaffold without authoritative articles/index |
| `/blog/article/` | `blog/article.html` | Scaffold without article identity/content contract |
| `/reviews/` | `reviews/reviews.html` | Scaffold without authoritative review source/policy |
| `/contact/` | `contact/contact.html` | Scaffold without ratified form/content/handling policy |

Requests to these seven routes raise `TemplateDoesNotExist`; this is genuine route-integrity debt,
but the repair choice is not technical. Creating placeholder claims would fabricate content, while
silently removing URLs would make an unratified product decision. Route smoke coverage also omits
them.

### Intentionally unavailable or historical

- Public command-backed checkout, confirmation and authenticated tracking are unavailable.
- Dashboard operational screens are empty projections, not implemented management workflows.
- Detailed Delivery, Procurement and Production templates are historical executable mockups and
  are not runtime domain authority. Their disabled controls and mock language must not be read as
  implemented business behavior.

## 10. Documentation Authority

### Current ratified contracts

1. `docs/architecture/v1-business-contract.md` — cross-domain V1 authority.
2. `docs/architecture/order-customer-payment-contract.md` — Customer, Order, Payment and minimal
   Fulfillment authority, refined by later ratifications.
3. `docs/architecture/availability-commitment-contract.md` — Inventory, Availability, Commitment,
   Reservation, Allocation, Supply, cancellation and concurrency authority (AC01-AC28).
4. `docs/reviews/phase-1e-e-decision-gate.md` — resolved supply decisions D01-D14.
5. `docs/reviews/phase-1g-processing-decision-gate.md` — ratified PROCESSING authority.

### Current implementation/verification evidence

- Phase 1D, 1E-A through 1E-E, 1F and 1G-Final audits, read chronologically.
- `post-phase-1g-system-audit.md` for the broad implementation review.
- `post-phase-1g-hardening-audit.md` section 23 for the final PostgreSQL result; its earlier blocked
  sections are explicitly historical.
- This closure audit is the current Phase-1 status synthesis; it does not supersede business
  contracts.

### Resolved or historical gates

- The Phase 1E and 1E-E decision gates are resolved historical reasoning.
- `phase-1g-audit.md` is explicitly historical; Phase 1G-Final resolves PROCESSING.
- Early phase audits correctly describe what was unavailable at their dates, but their staged status
  lists do not override later implementation evidence.

### Superseded/future material that could mislead

- `architecture/operations.md` and `architecture/state-machines.md` are marked superseded for V1.
- old Checkout, Order Management, Tracking, POS and Delivery contracts are marked future or
  superseded and contain non-V1 states/payment/Branch behavior.
- Phase 2-4 audits and frontend Production/Procurement/Delivery flows/templates are mock/executable
  specifications, not backend completion.
- `contracts/production.md` says Future, but some Production flow/frontend documents lack an equally
  prominent V1 authority marker. Future agents should treat them as historical/planning material
  until a Production contract is ratified.
- `architecture/permissions.md` is a broad future catalogue; only permissions installed and checked
  by current services are runtime authority.

Recommendation: retain historical evidence but add uniform front-matter fields such as
`Authority: CURRENT | SUPERSEDED | FUTURE` and `Superseded by:` during a documentation-only phase.

## 11. Remaining Technical Debt

1. **No PostgreSQL CI gate.** The authoritative run passed, but repository automation does not
   continuously execute PostgreSQL migrations, concurrency tests and the full suite.
2. **Cross-root idempotency races.** Same-key first use aimed at different Orders/Payments or
   disjoint Inventory Items lacks targeted PostgreSQL coverage and may surface a database integrity
   exception instead of normalized changed-input validation.
3. **Non-uniform cross-domain key policy.** Key uniqueness is table-local; commands differ in which
   foreign operation collisions they reject. Current deterministic child keys are safe, but the
   contract should become explicit before adding more commands.
4. **Initial event guard.** Additional `None -> PENDING` status events can be created through an
   ordinary manager even though admin and normal services do not expose that path. Later lifecycle
   writes have stronger service flags.
5. **Service flags are not a database security boundary.** Raw SQL or deliberate use of private
   flags can bypass Python ownership guards; cross-row invariants depend on service discipline.
6. **Inventory operational provisioning.** Runtime services post movements, but governed creation
   of Item/Location/Lot and audited lot-condition change are absent. Tests provision master data
   directly and admin is intentionally read-only.
7. **Route integrity and coverage.** Seven configured routes fail due to missing templates, pending
   the owner decision in section 13; smoke tests do not cover them.
8. **Documentation status consistency.** Future mock documents can be mistaken for current authority
   without uniform markers.

Actual deployment secret injection, TLS/proxy choice, backups, monitoring and permission assignment
are release operations, not repository business debt. Deferred product policies in section 12 are
not mislabeled here as technical debt.

### Test-quality assessment

The tests strongly protect current invariants: direct/bulk mutation rejection, database quantity
constraints, wrong-state and permission negatives, active-staff/superuser behavior, immutable audit
history, duplicate evidence, provider uniqueness, same-key idempotency, rollback at deliberately
injected late failures, source redaction, availability provider errors and real PostgreSQL races.
The concurrency tests use independent connections/barriers rather than SQLite assumptions or
arbitrary sleeps, and unexpected database errors fail the tests.

The material gaps are the cross-target idempotency races, configured missing-template routes,
continuous PostgreSQL execution, and deployment smoke/operational recovery testing. Fulfillment
does not explicitly lock Allocation rows, though it validates them after Commitment/Reservation
locks and current supply ordering; future supply paths should preserve or strengthen this locking
assumption. Some tests necessarily assert private service flags/model guards, but they pair those
details with business-equation and rollback assertions rather than treating implementation shape as
sufficient proof.

## 12. Deferred Business Capabilities

The following are unavailable and must remain so until separately authorized:

- PRE_ORDER availability, confirmation, capacity Reservation, supply and mixed-Order confirmation.
- Production forecasts, Batches, capacity, Releases, loss/shortfall handling and partial-release
  costing.
- Detailed Delivery, driver, route, dispatch, consignment and customer tracking workflows.
- Returns, restocking, refunds, voids and cancellation-to-refund behavior.
- Discounts, promotions, taxes and delivery charges.
- Cash on Pickup, Pay on Delivery, cash/card POS settlement, split/partial payments and automatic
  M-Pesa integration.
- Inventory adjustment/reversal posting until thresholds, approvers and separation of duties exist.
- Automatic Commitment/Reservation expiry and PENDING Order abandonment.
- Customer accounts, automatic Customer matching/merging and order-number-only tracking.
- Branch/location hierarchy and customer-selected stock source.
- Manual FIFO override, caller-selected supply split, standalone Reservation release and divisible
  commercial sale units.
- Deep Procurement and a generic UOM/event-sourcing framework.

## 13. Required Owner Decisions

| Decision ID | Question | Current repository evidence | Documented options | Unavailable until decided |
|---|---|---|---|---|
| P1C-01 | What lockable Production-capacity, eligibility, reservation, release and shortfall contract will support PRE_ORDER? | Availability contract says no provider exists and forbids fabricated capacity | No implementation options are ratified | PRE_ORDER and mixed confirmation/supply |
| P1C-02 | How are Batch-attributable expenses allocated across multiple partial Production Releases? | V1 contract approves lot-specific direction but rejects the single-release formula for multiple releases | No formula options are ratified | Production costing and costed releases |
| P1C-03 | What thresholds, approvers and separation of duties govern Inventory adjustments/reversals and audited lot-condition changes? | Movement vocabulary exists; posting is deliberately rejected and admin is read-only | No threshold/approval options are ratified | Adjustment/reversal and operational condition-change commands |
| P1C-04 | How long is raw Payment evidence retained and how is deletion/legal hold audited? | Evidence is encrypted and append-only; contract explicitly defers duration | No retention periods are ratified | Automated retention/deletion policy |
| P1C-05 | What happens to abandoned PENDING Orders? | PENDING-to-CANCELLED and automatic expiry are prohibited; no current entitlement exists to release | No timeout or disposition options are ratified | Automated abandonment/expiry behavior |
| P1C-06 | What authenticates customer tracking and prevents enumeration? | Order number is expressly not authorization; contract calls for rate limiting and non-enumerable responses | No mechanism is ratified | Customer tracking/history projection |
| P1C-07 | What Delivery, return, restocking and refund policies follow supply/cancellation? | Minimal completion deliberately contains no logistics; cancellation preserves confirmed Payment and issued stock | No detailed options are ratified | Delivery operations, returns, refunds and restocking |
| P1C-08 | Should the seven broken informational routes receive authoritative content or be retired/redirected? | URLs exist, templates/content do not; placeholders are prohibited | Implement authoritative content or retire/redirect are the only repository-evidenced directions; destination/content is undecided | Reliable About, FAQ, Branches, Blog, Reviews and Contact routes |

No READY state, permission or quantity decision remains open. Deployment-secret values, production
hostnames, HSTS preload/subdomains and permission assignments are operational security approvals,
not new product semantics; they still must be completed before release.

## 14. Recommended Next Phase

The smallest sensible next phase is **Phase 1H — Continuous PostgreSQL and Boundary Hardening**.
It should add no business capability and should be explicitly limited to:

1. a disposable PostgreSQL CI job running migrations, the six concurrency tests and full suite;
2. PostgreSQL tests and normalized handling for cross-root/cross-target idempotency-key races;
3. a decision and, if authorized, stronger service-only initial-event enforcement;
4. explicit repository-wide idempotency-key namespace documentation;
5. uniform documentation authority markers; and
6. route smoke coverage plus only the route disposition ratified under P1C-08.

After Phase 1H, the smallest product phase should be selected from an owner-ratified decision above.
Production/PRE_ORDER is the most direct extension of the existing model, but it is not ready to
start until P1C-01 and P1C-02 are resolved. Delivery/returns/refunds must not be bundled into that
phase.

## 15. Final Gate

**B. PHASE 1 CLOSED WITH TECHNICAL DEBT — READY LIFECYCLE VERIFIED BUT HARDENING REMAINS**

The READY service lifecycle is implemented, internally coherent and PostgreSQL verified. No known
verified lifecycle defect requires gate C. Gate A would understate the remaining CI, idempotency,
route, provisioning and documentation hardening recorded above.
