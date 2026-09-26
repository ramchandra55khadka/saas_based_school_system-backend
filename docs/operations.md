# Operations — setup, configuration, testing, deployment

> Split out of the top-level [`README.md`](../README.md) so it can stay focused on
> business logic. All commands and settings are preserved here.

## Getting started

### Prerequisites

- **Python 3.13+** (`pyproject.toml` declares `requires-python = ">=3.13"`, `.python-version` is `3.13`).
- **[uv](https://docs.astral.sh/uv/)** (recommended) — or plain `pip`.
- **PostgreSQL 14+** running locally — the configured backend. See [Database](#database).

### 1. Install dependencies

```bash
cd school_saas-backend

# recommended (uv reads pyproject.toml + uv.lock)
uv sync

# --- or, pip fallback ---
python3.13 -m venv .venv
source .venv/bin/activate
pip install django djangorestframework djangorestframework-simplejwt \
            django-cors-headers python-decouple loguru pyjwt pillow
```

> ℹ️ The repo contains **two** virtual environments. Use **`.venv`** — that is the uv-managed one
> with Django installed. The plain `venv/` directory only contains `pip` and is unusable.

### 2. Provision PostgreSQL and apply migrations

```bash
# one-time local setup (see the Database section below for details & alternatives)
psql -h 127.0.0.1 -U postgres -c "CREATE USER school_saas WITH PASSWORD 'school_saas';"
psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE school_saas OWNER school_saas;"
psql -h 127.0.0.1 -U postgres -c "ALTER USER school_saas CREATEDB;"

# connection settings are read from the repo-root `.env` (see the Database section below);
# export DB_* variables here only if you prefer environment variables over .env
uv run python manage.py migrate
```

All eight model-bearing apps already ship migrations (`academics` has two — `0001_initial` and
`0002_initial` — and `communication` has two, the second adding `Announcement`, `Message` and
`Notification`). `core` and `reports` have no migrations because they contain no concrete models.
The custom `user_account.UserAccount` model means `migrate` must run before any auth operation.

### 3. Verify

```bash
uv run python manage.py check      # → "System check identified no issues (0 silenced)."
```

### 4. Run the development server

```bash
uv run python manage.py runserver
```

- API root: `http://127.0.0.1:8000/api/`
- Django admin: `http://127.0.0.1:8000/admin/`

### 5. Smoke-test the auth flow

```bash
# log in and keep the cookies (replace credentials with a real user)
curl -i -c cookies.txt -X POST http://127.0.0.1:8000/api/accounts/login/ \
     -H 'Content-Type: application/json' \
     -d '{"email":"admin1@example.com","password":"pass12345"}'

# authenticated request using the stored cookie
curl -b cookies.txt http://127.0.0.1:8000/api/accounts/me/
```

`/api/accounts/me/` is a good health check: it returns the caller's profile plus every
tenant membership.

### Database

The project uses **PostgreSQL** via psycopg 3 (`psycopg[binary]`, added 2026-09-21 — it was
SQLite before). Connection settings are read from environment variables with development
defaults:

| Env var | Default | Meaning |
|---|---|---|
| `DB_NAME` | `school_saas` | database name |
| `DB_USER` | `school_saas` | role name |
| `DB_PASSWORD` | `school_saas` | role password |
| `DB_HOST` | `127.0.0.1` | server host |
| `DB_PORT` | `5432` | server port |

One-time local setup (adjust to your Postgres install; on Linux the `postgres` superuser usually
requires the `postgres` OS user or a password):

```bash
psql -h 127.0.0.1 -U postgres -c "CREATE USER school_saas WITH PASSWORD 'school_saas';"
psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE school_saas OWNER school_saas;"
# needed so `manage.py test` can create/destroy the test database:
psql -h 127.0.0.1 -U postgres -c "ALTER USER school_saas CREATEDB;"
```

Connection settings are read from the **`.env`** file in the repo root via `python-decouple`, with
this resolution order:

1. real environment variable (`DB_NAME`, …) — wins for CI, cron and secrets,
2. `.env` in the repo root,
3. built-in code defaults (`school_saas` / `school_saas` @ `127.0.0.1:5432`).

```ini
# .env
DB_NAME=school_saas
DB_USER=school_saas
DB_PASSWORD=school_saas
DB_HOST=127.0.0.1
DB_PORT=5432
```

> ⚠️ **Historical gotcha:** before the `.env` wiring, running the server with no `DB_*` variables
> made psycopg fall back to a Unix-socket connection as your OS user, producing a confusing
> `role "ramchandra" does not exist` error. That failure mode is now only reachable if you delete
> `.env` *and* unset the variables *and* the in-code defaults don't match your machine.

### Default database state

A freshly migrated `school_saas` database contains **schema only — 0 users, 0 tenants, 0 plans**.
You must create a super admin and a first school before any endpoint is usable (next section).

---

## Bootstrapping a super admin

Platform access is the `UserAccount.is_superuser` flag — there is **no `super_admin` role** — so the
super admin is the one account not created through the API (school admins are created together with
their tenant).

`.env` holds `SUPERADMIN_USERNAME` / `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD`, and a management
command reads them:

```bash
uv run python manage.py bootstrap_superadmin
```

It creates the account if missing, promotes `is_staff` + `is_superuser`, and never duplicates an
existing user. Useful flags: `--username`, `--email`, `--password`, `--force-password` (reset the
password on an existing account).

> Want a ready-made school right away? `python manage.py seed_demo` creates a demo tenant on the
> **Free plan** with one login per core role plus sample data. It never touches the platform super
> admin — that is what `bootstrap_superadmin` is for.

### Creating the first school

Log in as the super admin — no `active_tenant_id` claim is issued (by design) — then create the
school *and* its first admin in one call:

```bash
curl -b cookies.txt -X POST http://localhost:8000/api/accounts/superadmin/create-tenant/ \
  -H 'Content-Type: application/json' \
  -d '{"tenant_name":"Demo School","org_code":"DEMO-001",
       "admin_username":"admin1","admin_email":"admin1@example.com",
       "admin_password":"pass12345"}'
```

Shell fallback:

```python
from apps.tenants.models import Tenant
from apps.user_account.models import UserAccount, TenantMembership, RoleChoices

t = Tenant.objects.create(tenant_name="Demo School", org_code="DEMO-001")

admin = UserAccount.objects.create_user(
    username="admin1", email="admin1@example.com",
    password="pass12345",
    first_name="School", last_name="Admin",
)
TenantMembership.objects.create(user=admin, tenant=t, role=RoleChoices.ADMIN, is_active=True)
```

`create_user` takes **no `role`** — the role is granted by the `TenantMembership` above, which is
the only authoritative source.

---

## Configuration reference

### `config/settings.py` — key values as they exist today

| Setting | Current value | Note |
|---|---|---|
| `BASE_DIR` | project root | apps live in `BASE_DIR/apps/` as `apps.<name>` |
| `SECRET_KEY` | from `DJANGO_SECRET_KEY` (`.env`) — insecure dev fallback in code | set a real value in production |
| `DEBUG` | from `DJANGO_DEBUG` (`.env`) → `True` in dev | |
| `ALLOWED_HOSTS` | from `DJANGO_ALLOWED_HOSTS` (`.env`) → `localhost`, `127.0.0.1` | |
| `AUTH_USER_MODEL` | `user_account.UserAccount` | custom user model |
| `ROOT_URLCONF` | `config.urls` | |
| `DATABASES` | PostgreSQL → `school_saas` via psycopg 3; five `DB_*` knobs resolved env → `.env` → in-code default | |
| `LANGUAGE_CODE` / `TIME_ZONE` | `en-us` / `UTC` | `USE_TZ = True` |
| `STATIC_URL` | `static/` | |
| `DEFAULT_AUTO_FIELD` | `BigAutoField` | |
| `JWT_ACCESS_COOKIE` | `"access"` | custom setting consumed by the middleware and auth views |
| `JWT_REFRESH_COOKIE` | `"refresh"` | |
| `SIMPLE_JWT.ACCESS_TOKEN_LIFETIME` | 60 minutes | |
| `SIMPLE_JWT.REFRESH_TOKEN_LIFETIME` | 7 days | |

### DRF configuration

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}
```

Not configured (and therefore unavailable today): pagination, throttling, a default renderer/parser
beyond DRF's defaults, schema generation, and `rest_framework_simplejwt.token_blacklist`.

### `.env` (git-ignored)

```ini
# Django settings (DJANGO_-prefixed so a shell's generic `DEBUG` can never collide)
DJANGO_SECRET_KEY=django-insecure-…          # replace in production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=school_saas
DB_USER=school_saas
DB_PASSWORD=school_saas
DB_HOST=127.0.0.1
DB_PORT=5432

# Superadmin credentials (still read by nothing — Bug O)
SUPERADMIN_USERNAME=superadmin
SUPERADMIN_EMAIL=superadmin@example.com
SUPERADMIN_PASSWORD=…
```

`settings.py` reads the `DJANGO_*` and `DB_*` keys through `python-decouple` (Bug I fixed on
2026-09-21): real environment variable → `.env` → in-code default. Variable names are
`DJANGO_`-prefixed on purpose — a bare `DEBUG` is exported by some shells/tools (e.g.
`DEBUG=release`) and would collide through `os.environ`, which decouple checks before `.env`.

### Missing media configuration

`Tenant.logo` (`ImageField`) and `StudentDocument.file` (`FileField`) upload to
`school_logos/` and `student_documents/%Y/%m/` under `MEDIA_ROOT = BASE_DIR / 'media'`
(`MEDIA_URL = 'media/'`); in development `config/urls.py` serves them when `DEBUG` is on.
In production the reverse proxy (or an object store) must serve the media directory —
see [Production deployment](#production-deployment).

### CORS

CORS is wired: `corsheaders` is in `INSTALLED_APPS` and `CorsMiddleware` sits right after
WhiteNoise in `MIDDLEWARE`, with `CORS_ALLOW_CREDENTIALS = True` (required for cookie auth).
Allowed origins are env-driven via `CORS_ALLOWED_ORIGINS` (default
`http://localhost:3000,http://127.0.0.1:3000`), mirrored by `CSRF_TRUSTED_ORIGINS`.

---

## Testing

### Current state — verified

| Command | Result |
|---|---|
| `manage.py test` (no labels — **what CI runs**) | **`Ran 61 tests … OK`** |

The suite was rewritten on **2026-09-21** to pin the Bug A fix and the tenancy guarantees. Layout:
`apps/__init__.py` now exists, so plain `manage.py test` discovers everything.

| File | Covers |
|---|---|
| `apps/core/tests.py` | `BaseTenantAPITestCase` (2 schools + super admin + admin/hod/teacher/student/parent/accountant), Bug A auth regression, tenant isolation (list scope, cross-tenant 404s, `?tenant_id=` abuse), super-admin platform access, subscription lifecycle, leave approve/reject permission matrix, **parent role read/write surface** |
| `apps/user_account/tests.py` | super-admin tenant onboarding (`create-tenant`, Bug B), duplicate-field 400s, JWT cookie login, `/me/` |
| `apps/academics/tests.py` | subject CRUD scoping, `ReferenceDataViewSet` read-vs-write enforcement, cross-tenant invisibility, **timetable role scoping (teacher → own periods, student → own section, admin → all)** |

Tests drive the **real** stack end to end: login via `POST /api/accounts/login/` → the `HttpOnly`
cookie is promoted to an `Authorization` header by `accounts.middleware.CustomJWTMiddleware` →
SimpleJWT validates it → `TenantRequiredMixin` resolves `request.tenant` from the token claim. No
shortcuts around middleware or authentication.

### What the suite covers (and why)

- **Bug A regression** — a valid cookie must reach tenant endpoints; an anonymous request must
  still be `401`; a token without the `active_tenant_id` claim gets a clear `400`.
- **Tenant isolation** — school A's admin never sees school B's rows (list and detail), rows
  created are stamped with the caller's tenant, and `?tenant_id=` cannot be abused by non-super
  admins.
- **Super-admin platform access** — via `?tenant_id=` for tenant-scoped views, and
  `SchoolProfileViewSet` lists all schools.
- **Leave workflow permissions** — a teacher/student cannot approve or reject (Bug F); cross-tenant
  admins cannot either; the approving admin is recorded.
- **Billing-adjacent invariants** — plan CRUD is super-admin-only; subscriptions are readable only
  within the tenant.

### Remaining test coverage gaps

Test files exist for `core`, `user_account`, `academics`. **Still untested:** `tenants`, `students`,
`teachers` (beyond the leave workflow), `fees`, `communication`, `reports` — in particular the
`FeePayment.save()` invoice-status recalculation and `receipt_number` uniqueness are worth pinning
next.

---

## CI/CD

`.github/workflows/deploy.yml` — runs on `push` and `pull_request` to `main`:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'      # ⚠️ project requires >= 3.13
      - run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - run: uv sync
      - run: uv run python manage.py migrate
      - run: uv run python manage.py test
```

Observations:

- The workflow is named `deploy.yml` but **only tests — there is no deploy step** (fine for now;
  rename it or add a deploy job when you have a target).
- `python-version: '3.13'` now matches `requires-python = ">=3.13"`.
- The workflow provisions a **`postgres:16` service** and wires the `DB_*` variables, so `migrate`
  and `test` run against a real PostgreSQL — matching production.
- `uv run python manage.py test` runs the real suite (61 tests) — a red CI badge now actually
  means the app is broken.

---

## Production deployment

The stack is deployment-ready with boring, standard tooling. Copy
[`.env.example`](../.env.example) to `.env`, fill in real values, then:

```bash
# 1. one-time platform admin (idempotent — safe on every deploy)
uv run python manage.py bootstrap_superadmin

# 2. schema + collected static files (WhiteNoise serves them)
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput

# 3. application server (behind nginx/caddy terminating TLS)
uv run gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

Environment checklist (all read via `python-decouple`; real env vars win over `.env`):

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | **Generate a fresh random key** for every deployment |
| `DJANGO_DEBUG=False` | Switches on the whole hardening block + secure JWT cookies |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts your proxy forwards |
| `DJANGO_SSL_REDIRECT` | `True` unless the proxy already redirects HTTP→HTTPS |
| `DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT` | PostgreSQL connection |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Only for split deployments (not needed behind the Next proxy) |
| `SUPERADMIN_USERNAME/EMAIL/PASSWORD` | Consumed by `bootstrap_superadmin` |

What `DJANGO_DEBUG=False` switches on automatically: HSTS (1 year, include-subdomains, preload),
`SECURE_SSL_REDIRECT`, secure session/CSRF cookies, `SECURE_PROXY_SSL_HEADER` (nginx/caddy
TLS termination), nosniff, `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, and `Secure`
on the JWT cookies. Verify with:

```bash
DJANGO_DEBUG=False DJANGO_SECRET_KEY=<real-key> uv run python manage.py check --deploy
# -> System check identified no issues (0 silenced).
```

Operational notes:

- **TLS**: run gunicorn bound to localhost and let nginx/caddy terminate TLS (the proxy must set
  `X-Forwarded-Proto: https`).
- **Backups**: `pg_dump school_saas` on a schedule; media is on disk (`MEDIA_ROOT`) — include it
  or move to S3-compatible storage later.
- **Logs**: the JWT-debug noise is `DEBUG`-only; production logging comes from gunicorn/Django's
  standard request logging.
- **Refresh tokens**: logout and rotation both blacklist (see
  [Fixed → Production hardening](roadmap.md#production-hardening-2026-09-21)) — no extra infra
  needed for revocation.

---

