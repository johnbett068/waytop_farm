# WayTop Farm deployment and verification configuration

This document describes technical environment configuration only. It does not authorize or change
business behavior.

## Local development

Local development defaults to `DEBUG=True`, SQLite at `db.sqlite3`, non-secure local cookies and a
development-only SECRET_KEY fallback. Raw Payment evidence still uses encrypted storage; in local
development/tests only, its fallback key is derived from the development SECRET_KEY.

Do not use those fallbacks for production or real Payment evidence.

## Production security

Production must provide environment values rather than repository secrets:

| Variable | Requirement |
|---|---|
| `WAYTOP_DEBUG` | Set to `false`. The namespaced variable avoids collisions with host tooling that also defines `DEBUG`. |
| `SECRET_KEY` | External random value, at least 50 characters, at least five distinct characters, and not prefixed `django-insecure-`. |
| `ALLOWED_HOSTS` | Required comma-separated deployed hostnames. Production rejects an empty value or `*`. |
| `PAYMENT_EVIDENCE_ENCRYPTION_KEYS` | One or more comma-separated URL-safe Fernet keys. The first encrypts; all configured keys decrypt for rotation. |
| `SECURE_SSL_REDIRECT` | Defaults to true when `WAYTOP_DEBUG=false`; override only when an audited upstream layer provides the equivalent redirect. |
| `SESSION_COOKIE_SECURE` | Defaults to true when `WAYTOP_DEBUG=false`. |
| `CSRF_COOKIE_SECURE` | Defaults to true when `WAYTOP_DEBUG=false`. |
| `SECURE_HSTS_SECONDS` | Defaults to 31536000 when `WAYTOP_DEBUG=false`; reduce or disable only as an explicit deployment decision. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Optional; defaults false. Enable only when every subdomain is HTTPS-ready. |
| `SECURE_HSTS_PRELOAD` | Optional; defaults false. Enable only after owner-controlled preload review. |

Never commit generated values. A deployment secret manager should inject them at process start.
Run `python manage.py check --deploy` with the production environment before release.

## PostgreSQL test configuration

Install dependencies from `requirements.txt`, then provide:

| Variable | Requirement |
|---|---|
| `WAYTOP_DATABASE_BACKEND` | `postgresql` |
| `POSTGRES_DB` | Connection database used by Django to establish the test run. |
| `POSTGRES_TEST_DB` | Optional explicit isolated test database name; otherwise Django derives `test_<POSTGRES_DB>`. |
| `POSTGRES_USER` | Least-privilege test role. |
| `POSTGRES_PASSWORD` | External credential; never commit it. |
| `POSTGRES_HOST` | Defaults to `127.0.0.1`. |
| `POSTGRES_PORT` | Defaults to `5432`. |
| `POSTGRES_SSLMODE` | Optional libpq SSL mode appropriate to the environment. |

`POSTGRES_TEST_DB` must differ from `POSTGRES_DB`. The role must be able to create/drop Django's
test database. Alternatively, an explicitly named isolated database may be precreated with the
ownership/permissions Django requires and retained by running tests with `--keepdb`. Never point
this configuration at a production database.

Run the nine retained tests first:

```powershell
python manage.py test apps.orders.test_postgresql_concurrency --verbosity 2
```

## Continuous PostgreSQL verification

The GitHub Actions PostgreSQL workflow requires the repository secret `POSTGRES_TEST_PASSWORD`.
It uses separate control and test database names, PostgreSQL lock/statement timeouts, and never
falls back to SQLite for concurrency evidence. Configure the secret before making the job a
required check; the job intentionally fails when it is absent.

For a precreated least-privilege database, append `--keepdb` so Django reuses rather than attempts
to create or destroy it. The database must be disposable and contain no production data.

The two supported privilege shapes are:

- **Django-managed disposable database:** a login role that can connect to the PostgreSQL
  maintenance database and has `CREATEDB`; Django creates and drops `POSTGRES_TEST_DB`.
- **Owner-precreated disposable database:** a login role that can connect to the maintenance
  database, owns (or has equivalent schema/DML/sequence privileges on) `POSTGRES_TEST_DB`, and is
  invoked with `--keepdb`. `CREATEDB` is not required because Django detects and reuses the existing
  database. The owner is responsible for disposal after verification.

In both cases, the role needs no access to production data and `POSTGRES_TEST_DB` must never name a
production or development database.

Then run the implemented-domain and full suites. A PostgreSQL result is valid only when the test
output shows all six tests executed without the SQLite skip reason.
