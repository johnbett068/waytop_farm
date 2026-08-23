# WayTop Farm - Post-Phase-1G Hardening Audit

Audit date: 21 August 2026
Scope: technical verification and hardening only

## 1. Executive Summary

Environment-driven PostgreSQL and production-security configuration has been added without changing
the ratified READY lifecycle. A production-shaped environment now passes Django's deployment check
with zero findings, while local development remains usable and explicitly non-deployable. The
focused, implemented-domain and full SQLite suites pass.

PostgreSQL verification is complete. The retained concurrency module and the full suite passed on
a disposable, localhost-only PostgreSQL 18.4 cluster using SCRAM authentication and a dedicated
non-superuser test role. The explicit test database was distinct from the control database, was
empty after teardown, and the disposable cluster was removed. See section 23 for the final record.

The seven missing-template routes were investigated but not changed. Each is a configured render
stub with no template or authoritative content in the repository, so creating a page would require
content/business decisions rather than an unambiguous technical repair.

## 2. Baseline State

Before this pass, settings directly selected SQLite and had no PostgreSQL variant. There was no
Docker/Compose configuration, CI PostgreSQL service, test-settings module, psycopg dependency or
documented database environment contract. The prior full suite discovered 251 tests: 245 passed and
six PostgreSQL-only tests skipped. Normal Django check and migration drift were clean. Deployment
was blocked by `payments.E001`, `security.W004`, `security.W008` and `security.W009`. Seven public
routes raised `TemplateDoesNotExist`.

The pre-change focused technical baseline (`apps.payments.tests`, `apps.orders.tests`,
`apps.inventory.tests`, `apps.commitments.tests`) passed 6/6. The pre-change full suite reproduced
the prior result: 251 discovered, 245 passed, six skipped.

## 3. PostgreSQL Environment

- Windows services `postgresql-x64-18` and pgAgent are running.
- PostgreSQL 18 `psql` and `pg_isready` are installed; `127.0.0.1:5432` accepts connections.
- Docker is not installed, and the repository has no Compose or CI database service.
- No `PG*` credential variables, password file or repository credential was found.
- Passwordless connection attempts as the current user and as `postgres` both failed with
  `fe_sendauth: no password supplied`.
- The declared `psycopg[binary]` dependency is installed in the current virtual environment as
  psycopg 3.3.4.

`WAYTOP_DATABASE_BACKEND=postgresql` now selects PostgreSQL. Runtime and optional isolated test
database names, host, port, user, password and SSL mode are external inputs. The configuration
rejects missing database, user or password values and never points to or mutates `db.sqlite3`.
`psycopg[binary]` is declared in `requirements.txt`.

## 4. PostgreSQL Concurrency Results

The six retained `TransactionTestCase` tests were not executed on PostgreSQL and remain unchanged:

1. competing confirmations for one supply pool;
2. supply versus cancellation serialization;
3. same-key concurrent PROCESSING requests;
4. different-key concurrent PROCESSING requests;
5. PROCESSING versus cancellation serialization;
6. same-key concurrent fulfillment completion.

They were skipped six times by the SQLite vendor guard in the implemented-domain and full suites.
A valid run still requires a supplied test credential plus either a least-privilege role with test
database create/drop rights or a precreated isolated database owned by that role. No production
database may be used.

## 5. Deployment Check Findings

| Finding | Cause | Resolution/status |
|---|---|---|
| `payments.E001` | Production requires explicit Fernet key material. | Check preserved. External `PAYMENT_EVIDENCE_ENCRYPTION_KEYS` is documented; no key was committed. |
| `security.W004` | No production HSTS duration. | Production default is 31,536,000 seconds; development remains zero. |
| `security.W008` | HTTPS redirect was disabled. | Enabled by default when `WAYTOP_DEBUG=false`. |
| `security.W009` | Development SECRET_KEY fallback is intentionally weak. | Production now rejects absent, short, low-diversity and `django-insecure-` keys. |

The ordinary local environment deliberately fails `check --deploy`: it is a development
configuration and reports the encryption-key error plus W004, W008, W009, W012, W016 and W018. An
ephemeral production-shaped check with external test-only values passed with zero issues. Those
values were process-local and were not written to the repository.

## 6. Security Configuration Changes

- Added strict environment parsing for booleans and non-negative security durations.
- Namespaced the mode switch as `WAYTOP_DEBUG` to avoid collision with host tooling's `DEBUG` value.
- Required a strong, externally supplied production `SECRET_KEY` while retaining the deliberate
  development fallback.
- Made secure session cookies, secure CSRF cookies, HTTPS redirect and one-year HSTS production
  defaults.
- Kept HSTS subdomain and preload choices explicit because enabling either safely depends on the
  owner's deployed DNS/TLS estate.
- Centralized parsing of external Payment evidence encryption keys without generating, logging or
  committing key material.

## 7. Route Integrity Findings

| URL | View | Referenced template | Exists | Finding |
|---|---|---|---|---|
| `/about/` | `apps.core.views.about` | `core/about.html` | No | Configured render stub; no authoritative page content. |
| `/faq/` | `apps.core.views.faq` | `core/faq.html` | No | Configured render stub; no authoritative questions/answers. |
| `/branches/` | `apps.branches.views.branches` | `branches/branches.html` | No | Branch content/data would require business decisions. |
| `/blog/` | `apps.blog.views.blog` | `blog/blog.html` | No | Scaffold only; no authoritative articles or index design. |
| `/blog/article/` | `apps.blog.views.article` | `blog/article.html` | No | Scaffold only; no article source or selection contract. |
| `/reviews/` | `apps.reviews.views.reviews` | `reviews/reviews.html` | No | Review content/moderation behavior is undefined. |
| `/contact/` | `apps.contact.views.contact` | `contact/contact.html` | No | Contact page content/form behavior is undefined. |

All URLconfs are included at runtime, but the apps contain only render stubs and no corresponding
templates, tests, persisted content, or unambiguous alternative template paths. They are best
classified as incomplete scaffolding rather than simple path mistakes.

## 8. Route Fixes, if any

None. Placeholder customer pages were not created, routes were not silently removed, and no content
or business behavior was invented. Owner content/product decisions are required to implement or
retire these routes.

## 9. Files Added

- `config/environment.py`
- `config/test_environment.py`
- `docs/deployment-configuration.md`
- `docs/reviews/post-phase-1g-hardening-audit.md`

## 10. Files Changed

- `config/settings.py`
- `requirements.txt`

Only changes made by this pass are listed; the working tree contains earlier Phase 1 work that was
preserved.

## 11. Files Removed

None.

## 12. Migrations

No model or schema change was required, so no migration was created or altered. Clean temporary
test databases applied the complete migration graph. The zero-byte development `db.sqlite3`
remained zero bytes.

## 13. Tests

- Configuration tests: 5/5 passed.
- Focused READY lifecycle suite: 86/86 passed.
- Implemented domains: 235 discovered; 229 passed; six PostgreSQL-only skipped.
- Full suite: 258 discovered; 252 passed; six PostgreSQL-only skipped.
- PostgreSQL: zero tests executed on PostgreSQL; no result claimed.

No existing test was removed, weakened or changed.

## 14. Django Checks

- `manage.py check`: passed, zero issues.
- Production-shaped `manage.py check --deploy`: passed, zero issues.
- Unconfigured local `manage.py check --deploy`: intentionally failed with `payments.E001` and
  W004, W008, W009, W012, W016 and W018, proving local fallback settings are not silently treated
  as deployable.

## 15. Migration Drift

`manage.py makemigrations --check --dry-run` reported `No changes detected`. The focused,
implemented-domain and full suites each built clean isolated test databases successfully.

## 16. PostgreSQL Status (Historical Pre-verification State)

Infrastructure support is implemented but runtime verification is blocked. Exact remaining needs:

1. supply an external PostgreSQL test credential;
2. grant that role test database create/drop rights, or precreate an isolated owned test database;
3. set the documented `POSTGRES_*` and `WAYTOP_DATABASE_BACKEND` variables;
4. run the six-test concurrency module, relevant concurrency/domain suite and full suite.

The running server alone is insufficient because it correctly rejects unauthenticated access.

## 17. Security/Privacy Verification

The hardening changes affect settings selection only. Existing permission and domain suites passed,
including active-staff checks, superuser semantics, Django permission grants, read-only admin
boundaries, internal audit history and customer-safe projections. Payment evidence remains stored
through the encrypted field; production still cannot start safely without external encryption keys.
No raw evidence, secret, internal allocation, FIFO source, provider reference or customer-private
projection was exposed.

## 18. Remaining Technical Gaps

- PostgreSQL concurrency behavior is still unverified.
- The target deployment must supply real secret values, hostnames and TLS/HSTS choices through its
  secret/configuration system, then repeat `check --deploy` there.
- Seven public scaffolding routes remain broken until the owner authorizes content implementation or
  route retirement.
- No repository CI service currently performs PostgreSQL verification.

## 19. Business Decisions Explicitly NOT Changed

No lifecycle state, Payment semantic, Commitment/FIFO rule, Availability calculation, Reservation,
Allocation, Supply, cancellation, PROCESSING or Fulfillment rule changed. No Production,
PRE_ORDER behavior, refund, return, discount, promotion, tax, Delivery, tracking, new permission or
customer-facing capability was added. No new product phase was started.

## 20. Final Readiness Assessment (Superseded by Section 23)

**Option A - PostgreSQL verification complete.** The retained concurrency module and full suite
passed on an isolated disposable PostgreSQL environment. Deployment still requires
owner-controlled real secrets/TLS configuration, and the seven route decisions remain outside
technical authority.

## 21. Final PostgreSQL Verification Attempt (Historical; Superseded by Section 23)

Gate attempt date: 21 August 2026

- **PostgreSQL version:** PostgreSQL 18.4 on the local Windows service
  `postgresql-x64-18`.
- **Connection status:** `127.0.0.1:5432` is accepting connections. Passwordless connections as
  the current operating-system user and as `postgres` both failed with
  `fe_sendauth: no password supplied`.
- **Isolation method:** the repository supports an explicit `POSTGRES_TEST_DB` or Django's derived
  `test_<POSTGRES_DB>` database. No database was created because no authorized credential or test
  role is configured.
- **Driver:** the already-declared `psycopg[binary]>=3.2,<4` dependency was installed without
  changing the dependency contract; installed psycopg version is 3.3.4.
- **Six concurrency tests:** not executed on PostgreSQL. All six remain unchanged; no pass, failure,
  or PostgreSQL verification result is claimed.
- **Full PostgreSQL suite:** not run because an authenticated isolated database connection could
  not be established.
- **PostgreSQL migrations:** not applied because no authorized isolated database could be created
  or accessed.
- **Django check, deployment check, and migration drift on PostgreSQL:** not run for the same
  authentication blocker. The previously recorded SQLite and production-shaped configuration
  checks remain valid but do not substitute for PostgreSQL execution.
- **Technical fixes:** installed the declared driver in the project virtual environment. No
  application, test, migration, lifecycle, or business-rule change was made.
- **Remaining infrastructure requirement:** provide an externally configured credential for an
  authorized least-privilege PostgreSQL test role with create/drop test-database rights, or provide
  an isolated precreated test database owned by that role. Configure the documented environment
  variable names without recording their values in the repository.

**Historical attempt outcome:** PostgreSQL verification was blocked pending owner/environment
action; this blocker was subsequently closed in section 23.

## 22. Broader Technical Verification and Hardening

Verification date: 21 August 2026

### Scope completed

The repository-side review covered PostgreSQL configuration and the six retained concurrency
tests; migration/test-database behavior; transaction and row-lock ordering; service idempotency;
ORM mutation guards; domain permissions and active-staff checks; Payment-evidence encryption and
exposure; deployment settings; route integrity; migration drift; and lifecycle regression quality.
Live PostgreSQL execution remained unavailable because no authenticated test role/database was
provided.

### Technical defects fixed

1. The staff-branded login view accepted valid credentials for an active non-staff `User`. Login
   now rejects non-staff identities with the same generic failure presentation, and the profile
   route independently enforces active staff access.
2. Payment evidence could use the development SECRET_KEY-derived Fernet key under a production
   settings selection if an operator skipped `check --deploy`. Production encryption now fails
   closed at the field boundary unless explicit rotatable keys are configured. Django tests retain
   the explicitly permitted development fallback despite the test runner's later `DEBUG=False`
   override.
3. Explicit PostgreSQL configuration allowed `POSTGRES_TEST_DB` to equal `POSTGRES_DB`. That unsafe
   configuration is now rejected before Django can create, migrate or destroy a database.
4. Production `ALLOWED_HOSTS` could silently fall back to local-only values, preserve surrounding
   whitespace, or accept `*`. Production now requires an explicit non-wildcard list; development
   retains the local defaults.
5. PostgreSQL documentation now distinguishes Django-managed `CREATEDB` verification from an
   owner-precreated least-privilege database reused with `--keepdb`.

No model, migration, lifecycle service or business rule changed.

### Transaction, locking and idempotency findings

- No non-test `QuerySet.update()`, `bulk_create()` or `bulk_update()` bypass was found against
  protected Order, Payment, Commitment, Stock Position, Reservation, Allocation, movement or
  fulfillment-history models. Their default managers reject bulk mutation; instance writes are
  guarded by their owning service flags and database constraints.
- Consequential service boundaries consistently require authenticated active staff plus native
  Django permissions. No role-name, username, department or frontend-visibility authorization was
  found.
- Current lock roots and stable ordering remain coherent: confirmation uses Payment, Order, Lines,
  sorted Items and Positions; physical Inventory operations use sorted Items, Lots, Locations and
  Positions; supply uses Item before Commitment and physical partitions; processing/cancellation
  use Order before sorted Items and stable dependent rows. Supply does not acquire the Order row,
  so the reviewed Order/Item interaction does not form an immediate reverse lock cycle.
- The concurrency tests use a thread barrier and independent database connections, contain no
  arbitrary sleeps, and permit unexpected database/locking exceptions to fail rather than
  relabeling them as domain rejection. Their assertions were not changed.
- Same-key and changed-key behavior, rollback equations and immutable audit histories have broad
  SQLite coverage. Concurrent first use of an Order creation key and same-key Inventory commands
  over disjoint Item pools remain PostgreSQL-only risks; no speculative fix was made without the
  database execution needed to validate exception and visibility behavior.

### Security and route findings

Focused access/encryption/configuration regression: 50/50 passed. Raw Payment evidence remains
absent from public views, model strings and authorized admin rendering. Internal FIFO, Position,
Reservation and Allocation facts remain unavailable through customer/public views.

The About, FAQ, Branches, Blog, Blog Article, Reviews and Contact routes still reference absent
templates. No authoritative content, alternate template or route-retirement decision exists, so
they remain documented content/product decision gates and were not changed.

### Verification results

- Focused security/configuration: 50/50 passed.
- Focused lifecycle: 86/86 passed.
- Implemented domains: 237 discovered; 231 passed; six PostgreSQL-only skipped.
- Full suite: 258 discovered; 252 passed; six PostgreSQL-only skipped.
- Explicit concurrency module on SQLite: six discovered; six skipped with the retained PostgreSQL
  vendor guard. No PostgreSQL result is claimed.
- Normal Django check: passed with zero findings.
- Production-shaped deployment check: passed with zero findings.
- Migration drift: no changes detected.
- Clean SQLite migration graph: passed in fresh test databases.
- `git diff --check`: passed, with line-ending notices only.
- Development `db.sqlite3`: remained zero bytes.

### Files changed in this broader pass

- `apps/accounts/views.py`
- `apps/accounts/tests.py`
- `apps/payments/fields.py`
- `apps/payments/tests.py`
- `config/environment.py`
- `config/settings.py`
- `config/test_environment.py`
- `docs/deployment-configuration.md`
- `docs/reviews/post-phase-1g-hardening-audit.md`

Files added: none. Files removed: none. Migrations created: none.

### Remaining blockers and exact next action

The PostgreSQL access blocker described above was closed by the authorized disposable-cluster
verification recorded in section 23. The remaining deployment-secret/TLS and route-content choices
are deployment or product-owner actions, not blockers to the PostgreSQL verification gate.

## 23. PostgreSQL Verification Completion

Completion date: 21 August 2026

### Environment and isolation

- PostgreSQL 18.4 with psycopg 3.3.4.
- Disposable, localhost-only cluster using SCRAM authentication.
- Dedicated role `waytop_test`: login, `CREATEDB`, non-superuser, no role creation and no
  replication privileges.
- Control database `waytop_verify_control` and explicit test database `waytop_verify_test` were
  distinct.
- Generated credentials remained process-local and were not printed, persisted in the repository
  or reused from a production environment.
- The isolated test database count was zero after teardown. The server was stopped and its
  disposable data directory removed.

### Defects exposed and repaired

PostgreSQL correctly rejected `FOR UPDATE` against nullable outer joins in the pending-order
idempotency lookup. The lookup now locks the `Order` row without joining its optional snapshot
relations; snapshots are loaded lazily when needed.

The supply/cancellation race then exposed a real deadlock because the commitment query's joined
`Order` was also being locked. Its `select_for_update()` is now scoped to the `Commitment` row with
`of=("self",)`, preserving read joins and the documented lock order. Neither repair changes business
rules, permissions, state-machine policy or expected test behavior.

### Runtime results

- Retained PostgreSQL concurrency module: 6/6 passed, zero skips, failures or errors.
- Full PostgreSQL suite: 258/258 passed, zero skips, failures or errors.
- Complete migration graph applied successfully to clean PostgreSQL test databases.
- Normal Django system check: zero findings.
- Production-shaped deployment check: zero findings.
- Migration drift: no changes detected.
- Dependency check: no broken requirements.
- `git diff --check`: passed (line-ending notices only).
- Development `db.sqlite3`: zero bytes.

**Final gate: PostgreSQL verification complete - all required tests passed.**
