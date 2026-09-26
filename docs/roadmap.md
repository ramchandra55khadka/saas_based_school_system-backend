# Known gaps & roadmap

> Split out of the top-level [`README.md`](../README.md). This is a **historical
> record**: entries were written as they were found, and some items listed as open
> have since been fixed (for example leave approve/reject is now restricted to
> `IsAdminOrHOD`, and `reports/*` now binds its tenant via `TenantAPIView`).
> Verify against the code before relying on any item.

## Known gaps & roadmap

Everything below was **verified by running the code** (Django test client against a throwaway test
database, plus `manage.py check` / `manage.py test`), not inferred from reading alone.

### Fixed on 2026-09-21

| # | Was | Fix |
|---|---|---|
| **A** | 🔴 Every `TenantViewSet` endpoint returned `401` — tenant API unusable | `TenantRequiredMixin` now hooks `perform_authentication()` (runs after JWT validation) instead of `dispatch()`; pinned by `apps/core/tests.py::TenantAuthenticationTests` |
| **B** | 🟠 `super_admin` got `403` from `IsAdminOrHOD` / `IsTenantAdmin` | `is_super_admin()` short-circuit added to `IsTenantAdmin`, `IsAdminOrHOD`, `IsAdminOrHODOrTeacher`, `IsAdminOrHodUserManagement`; super admin acts tenant-scoped via `?tenant_id=` |
| **C** | 🟠 `create-tenant` committed rows then 500'd (`KeyError: tenant_name`) | `SignupSerializer` now validates uniqueness up-front, wraps creation in `transaction.atomic`, and overrides `to_representation()` to render the `(tenant, admin_user)` pair |
| **D** | 🟠 `subscription` serializers referenced non-existent fields (`max_users`, `get_plan_display`, `auto_renew`, …) | Rewritten to match the actual `Plan`/`Subscription` models; subscription writes make `plan` the only client-supplied field |
| **F** | 🟡 Any authenticated user could approve/reject leave | `approve`/`reject` actions now require `IsAdminOrHOD` |
| **G** | 🟡 `manage.py test` discovered 0 tests; stale tests | `apps/__init__.py` added; all three stale test files rewritten — **61 tests, all passing** |
| **I** | 🟡 `.env` inert; `SECRET_KEY` hardcoded | `settings.py` reads `DJANGO_*` / `DB_*` / `SUPERADMIN_*` via `python-decouple` (env → `.env` → in-code default); `bootstrap_superadmin` command added |
| **M** | ⚪ Role checks read the global `User.role` | All views now use tenant-scoped `get_membership_role(user, request.tenant)`; `IsAccountant` wired into fee writes |
| **R** | 🏷️ Naming | `accounts` app → **`user_account`**, `User` → **`UserAccount`**; `RoleChoices` moved to `user_account/constants.py` (still re-exported from `models.py`). All 13 apps now own a `constants.py` |

Two additional latent bugs surfaced and were fixed once the 401 wall came down:

- `TenantQuerysetMixin`'s `User` branch filtered on the non-existent
  `tenantmembership__tenant` reverse relation (`FieldError`) — now `memberships__tenant`.
- `UserManagementViewSet` had no base `queryset`, so the mixin chain raised DRF's
  *"should either include a queryset attribute"* assertion on every request.
- `LeaveRequestViewSet.perform_create()` never set `tenant` → `IntegrityError: NOT NULL constraint
  failed: teachers_leaverequest.tenant_id` whenever a teacher created a leave request.
- `LeaveRequestSerializer` required `teacher` on input even though the view injects it (and
  `SubscriptionSerializer` similarly required `tenant`/`end_date`) — now `read_only_fields`.

### Renaming `accounts` → `user_account` (existing databases)

Renaming a Django app **changes the app label**, so an existing database needs explicit care: 17 FK
constraints across `academics`, `communication`, `students`, `teachers`, `django_admin_log` and
`token_blacklist` point at `accounts_user`. The tables must be **renamed, never dropped** —
Postgres keeps those FKs valid through a rename, whereas a `DROP` would cascade them away and
`migrate` would not recreate them (those migrations are already recorded as applied).

The steps used (single transaction, run as the DB superuser):

```sql
ALTER TABLE accounts_user RENAME TO user_account_useraccount;
ALTER TABLE accounts_tenantmembership RENAME TO user_account_tenantmembership;
ALTER TABLE accounts_user_groups RENAME TO user_account_useraccount_groups;
ALTER TABLE accounts_user_user_permissions RENAME TO user_account_useraccount_user_permissions;

ALTER SEQUENCE accounts_user_id_seq RENAME TO user_account_useraccount_id_seq;
ALTER SEQUENCE accounts_tenantmembership_id_seq RENAME TO user_account_tenantmembership_id_seq;
ALTER SEQUENCE accounts_user_groups_id_seq RENAME TO user_account_useraccount_groups_id_seq;
ALTER SEQUENCE accounts_user_user_permissions_id_seq RENAME TO user_account_useraccount_user_permissions_id_seq;

-- stale authz rows for the old label (old codenames were add_user/add_tenantmembership)
DELETE FROM auth_group_permissions WHERE permission_id IN (
  SELECT id FROM auth_permission WHERE content_type_id IN (
    SELECT id FROM django_content_type WHERE app_label = 'accounts'));
DELETE FROM user_account_useraccount_user_permissions WHERE permission_id IN (
  SELECT id FROM auth_permission WHERE content_type_id IN (
    SELECT id FROM django_content_type WHERE app_label = 'accounts'));
DELETE FROM auth_permission WHERE content_type_id IN (
  SELECT id FROM django_content_type WHERE app_label = 'accounts');
DELETE FROM django_content_type WHERE app_label = 'accounts';
DELETE FROM django_migrations WHERE app = 'accounts';
```

Then, because `academics.0002_initial` declares `user_account.0001_initial` as a parent while those
tables already exist:

```bash
# record the initial migration as applied (its tables were just renamed into place)
psql -d school_saas -c "INSERT INTO django_migrations (app, name, applied)
                        VALUES ('user_account','0001_initial', now())"
python manage.py migrate          # applies user_profile / staff / library

# the old global `role` column is gone from the model; drop it or every INSERT fails
psql -d school_saas -c "ALTER TABLE user_account_useraccount DROP COLUMN role"
# platform access is now is_superuser, so promote the existing super admin
psql -d school_saas -c "UPDATE user_account_useraccount
                        SET is_superuser = true, is_staff = true WHERE username = 'superadmin'"
```

Verify with `python manage.py makemigrations --check --dry-run` (must print *No changes detected*)
and `python manage.py test`.

### Production hardening (2026-09-21)

Delivered as part of the production-readiness pass — see
[Production deployment](operations.md#production-deployment) for the operational checklist:

| Was | Fix |
|---|---|
| 🟠 **H** CORS "not wired" | Already wired in code (`corsheaders` app + middleware + allow-credentials); origins are now **env-driven** (`CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`) instead of hardcoded |
| 🟠 **K** logout never revoked the refresh token | `rest_framework_simplejwt.token_blacklist` enabled; **logout blacklists the refresh token**; refresh **rotates** (`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`) so a stolen refresh token dies on first reuse. Access lifetime shortened to 30 min. Pinned by `SecurityHardeningTests` |
| 🟡 **J** no media configuration | `MEDIA_URL`/`MEDIA_ROOT` added and served under `DEBUG`; WhiteNoise + `STATIC_ROOT` added for static |
| ⚪ **O** manual super-admin bootstrap | `python manage.py bootstrap_superadmin` reads `SUPERADMIN_*` from the environment; idempotent (`--force-password` to rotate). Pinned by tests |
| 🔴 **E** reports 500s | Reports views were moved onto `TenantAPIView` + `require_tenant()` (earlier pass); runtime-verified: all four report endpoints answer from the demo data |
| — No security hardening at all | `check --deploy`-clean production block gated on `DEBUG=False`: HSTS (1y, preload), SSL redirect (`DJANGO_SSL_REDIRECT`), `SECURE_PROXY_SSL_HEADER`, secure session/CSRF cookies, nosniff, `Referrer-Policy`, `X_FRAME_OPTIONS=DENY`; **JWT cookies get `Secure` automatically outside DEBUG** |
| — Per-request token logs in production | middleware debug logs now run only when `DEBUG=True` |
| — CI tested on Python 3.11 with no database | workflow pinned to **3.13**, gained a **`postgres:16` service** + `DB_*` env, `migrate --noinput`, `test --noinput` |

Dependencies added: `gunicorn` (WSGI server) and `whitenoise` (static files).
A committed **`.env.example`** documents every deployment variable.

### Still open

| # | Severity | Issue |
|---|---|---|
| **S** | 🟠 High (user action) | The committed `.env` still carries the auto-generated `django-insecure-…` SECRET_KEY. Generate a real one (`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`) before deploying — with a proper key, `check --deploy` is **clean** (verified) |
| **L** | ⚪ Low | `subscription/signals.py` is empty and never registered |
| **N** | ⚪ Low | `flow.md` documents middleware (`JWTAuthenticationMiddleware`, `TenantMiddleware`) that does not exist |
| **P** | ⚪ Low | Working tree holds an uncommitted layout migration (old flat apps deleted, `apps/`+`config/` untracked) |
| **Q** | ✅ Fixed | Pagination is enabled globally with `StandardResultsSetPagination`; frontend `useList` unwraps `{results}` so screens still receive arrays |

---

### A. FIXED (was Critical) - every `TenantViewSet` endpoint returned `401`

**Symptom (before the fix).** With a valid, freshly-logged-in cookie, every tenant-scoped endpoint
returned `401 {"detail": "Authentication required"}` - regardless of role (admin, hod, teacher,
student, even super admin):

```
GET /api/academics/classes/                     -> 401
GET /api/academics/academic-years/              -> 401
GET /api/students/profiles/                     -> 401
GET /api/teachers/profiles/                     -> 401
GET /api/fees/invoices/                         -> 401
GET /api/communication/notifications/           -> 401
GET /api/accounts/user-management/              -> 401
GET /api/subscription/subscriptions/            -> 401
```

Meanwhile the non-`TenantViewSet` controls all worked: `GET /api/accounts/me/` -> `200`,
`GET /api/tenants/profile/` -> `200`, `GET /api/subscription/plans/` -> `200`.

**Root cause - `apps/core/mixins.py`.**

`TenantRequiredMixin` was **first** in the MRO and defined `dispatch()`, so it *replaced*
`APIView.dispatch()` as the entry point:

```python
class TenantRequiredMixin:
    def dispatch(self, request, *args, **kwargs):        # <- the bug
        if not request.user.is_authenticated:            # runs BEFORE DRF auth
            return JsonResponse({"detail": "Authentication required"}, status=401)
```

Two consequences, both fatal:

1. `APIView.dispatch()` normally calls `initialize_request()` (wrapping the raw Django
   `HttpRequest` in a DRF `Request`), then `initial()` -> `perform_authentication()` ->
   sets `request.user`. Because the mixin wrapped `super().dispatch(...)`, **all of that happened
   after the check**.
2. At check time `request` was the **raw Django `HttpRequest`**, whose `.user` comes from
   `AuthenticationMiddleware` + sessions. There is no session (auth is JWT-in-cookie), so
   `request.user` was `AnonymousUser` -> `is_authenticated` is `False` -> `401`.

The JWT *was* present and valid - `CustomJWTMiddleware` logs `Copied JWT to Authorization header`
on these very requests. The token was simply never consulted, and `request.tenant` was therefore
never set either (which is also why Bug E happened).

**Fix (applied).** The mixin no longer touches `dispatch()`. Tenant resolution moved into
`perform_authentication()`, which DRF runs *after* the JWT is validated but *before*
`check_permissions()`:

```python
class TenantRequiredMixin:
    def perform_authentication(self, request):
        super().perform_authentication(request)   # authenticates -> sets request.user
        self.resolve_tenant(request)              # request.tenant from the JWT claim
```

`resolve_tenant()` keeps the same semantics: public paths are skipped, anonymous requests raise
`NotAuthenticated`, super admins are platform-level (they may target a school with `?tenant_id=`),
and everyone else needs the `active_tenant_id` claim - a missing or invalid claim raises a clean
`ValidationError` instead of a silent fallback.

**Regression coverage:** `apps/core/tests.py::TenantAuthenticationTests` - anonymous -> 401, valid
cookie -> 200, token without the claim -> 400 `Tenant context missing`. Pinned end to end through
the real cookie -> middleware -> JWT -> mixin chain.

---

### B. FIXED (was High) - `super_admin` was locked out of most management endpoints

`IsSuperAdmin` used to get a shortcut in `IsAdminOrSuperAdmin` only. The other composite classes
(`IsAdminOrHOD`, `IsAdminOrHODOrTeacher`, `IsTenantAdmin`) looked **only** for `TenantMembership`
rows with `role in ('admin', 'hod', ...)`. A super admin has no such membership, so they were
denied - making the explicit super-admin branch in `SchoolProfileViewSet.get_queryset()`
unreachable code.

**Fix (applied).** A shared `is_super_admin(user)` helper in `utils/permissions.py` short-circuits
at the top of every composite permission class, and `TenantRequiredMixin.resolve_tenant()` lets a
super admin act on a specific school by passing `?tenant_id=<uuid>`. A tenant admin passing the
same query param is ignored - the test suite proves both directions.

**Regression coverage:** `apps/core/tests.py::SuperAdminAccessTests` - the super admin lists all
schools' profiles, creates rows in a target school via `?tenant_id=`, sees nothing on tenant-scoped
lists without a tenant context, and lists a school's users (its admin + teacher, never the other
school's).

---

### C. FIXED (was High) - super-admin tenant creation committed, then 500'd

`POST /api/accounts/superadmin/create-tenant/` with a valid super-admin cookie used to return:

```
-> KeyError: Got KeyError when attempting to get a value for field `tenant_name`
   on serializer `SignupSerializer`.
Tenant "Beta" created? True      # <- side effects already committed
```

`SignupSerializer.create()` returned a plain dict, but the serializer declared flat fields - DRF
then failed to render the response *after* the rows were committed, and the operation was not even
wrapped in a transaction.

**Fix (applied) - `apps/user_account/serializers.py`:**

- `to_representation()` now renders the created `(tenant, admin_user)` pair as a nested payload.
- `create()` is wrapped in `@transaction.atomic` - a failure rolls everything back.
- Uniqueness is validated up-front (`tenant_name`, `org_code`, `slug`, `admin_email` within the new tenant context,
  all case-insensitive where applicable), so duplicate submissions are clean `400`s, never half-committed writes.

**Regression coverage:** `apps/user_account/tests.py::TenantOnboardingTests` - happy path (tenant +
admin + membership created, response describes them), duplicate org code / tenant name / admin email
-> `400` with nothing persisted, and a tenant admin is `403`-ed from the endpoint.

---

### D. FIXED (was High) - `subscription` serializers referenced fields that don't exist

Both serializers declared fields absent from the models (`get_plan_display`, `description`,
`max_users`, `auto_renew`, `is_expired`, `created_at`, `updated_at`), which raises
`ImproperlyConfigured`/`FieldError` the moment a `Plan` row exists. They only appeared to work
while the table was empty.

**Fix (applied) - `apps/subscription/serializers.py`:** aligned with the real models -

- `PlanSerializer`: `id, name, price, duration_days, max_students, is_active, created_at`.
- `SubscriptionSerializer`: enriched read model with `plan_name`, `plan_price`,
  `plan_duration_days` and the model's own `days_remaining`; `tenant`, `start_date`, `end_date`
  are `read_only` (the view computes them from the plan's duration), leaving `plan` as the only
  client-supplied field.

**Regression coverage:** `apps/core/tests.py::SubscriptionTests` - plan CRUD (super admin only),
`active-plans` readable by any authenticated user, and a subscription created for school A via
`?tenant_id=` is visible to A's admin (with correct `plan_price`/`days_remaining`) and invisible to
B's admin.

---

### E. 🟠 High — `/api/reports/*` raise `AttributeError` on `request.tenant`

```
GET /api/reports/demographics/  -> AttributeError: 'Request' object has no attribute 'tenant'
GET /api/reports/attendance/    -> AttributeError: 'Request' object has no attribute 'tenant'
```

All four report views do `tenant = request.tenant`, but `request.tenant` is **only ever assigned in
`TenantRequiredMixin.dispatch()`**. `reports/views.py` uses bare `APIView`s, which never run that
mixin, so the attribute does not exist. (Even once Bug A is fixed, this stays broken — the report
views inherit nothing.)

**Fix options:** resolve the tenant inside each report view from
`request.auth.payload["active_tenant_id"]` (or a shared `TenantAPIView` base), or — the robust
option — promote tenant resolution into a **global middleware** so *every* request gets
`request.tenant`, which is what the original `flow.md` design intended.

---

### F through Q - remaining items

**F. ~~Leave approve/reject are under-permissioned~~ - FIXED.**
`LeaveRequestViewSet.get_permissions()` returned `[IsAuthenticated()]` for any action that was not
`create`/`update`/`partial_update`/`destroy`, so the `approve`/`reject` `@action`s were open to any
authenticated user - including a student approving their own leave. Both actions now require
`IsAdminOrHOD` (pinned by `LeaveWorkflowTests` in `apps/core/tests.py`).

**G. ~~Tests are not discovered and stale~~ - FIXED.** `apps/__init__.py` added, stale test files
rewritten - 61 tests, all green. See [Testing](operations.md#testing).

**H. CORS is not configured.** `django-cors-headers` is a dependency but is absent from
`INSTALLED_APPS`/`MIDDLEWARE`; no `CORS_ALLOWED_ORIGINS` or `CORS_ALLOW_CREDENTIALS`. A cookie-based
frontend on another origin cannot call the API. Since auth uses cookies,
`CORS_ALLOW_CREDENTIALS = True` is required - `CORS_ALLOW_ALL_ORIGINS` alone would not work.

**I. FIXED — `.env` was inert.** `python-decouple` is now imported in `settings.py`;
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` and the five `DB_*` knobs resolve
env → `.env` → in-code default. Names are `DJANGO_`-prefixed because a bare `DEBUG` exists in many
shells (e.g. `DEBUG=release`) and decouple checks `os.environ` before `.env`. The committed
insecure key is now only a fallback — production must still supply a real secret and `DEBUG=False`.

**J. No media configuration.** `Tenant.logo` and `StudentDocument.file` are upload fields, but
`MEDIA_URL`/`MEDIA_ROOT` are undefined and `config/urls.py` never serves media, so uploads have no
storage location and no URL.

**K. Logout is client-side only.** `LogoutView` deletes the cookies but the refresh token stays
valid for its full 7 days. There is no `token_blacklist` app and no `BlacklistMixin`, so a stolen
refresh token cannot be revoked. `rest_framework_simplejwt` is also missing from `INSTALLED_APPS`.

**L. `subscription/signals.py` is empty** and `SubscriptionConfig` has no `ready()` hook, so it is
never imported. It is a placeholder for future signals (e.g. enforcing `Plan.max_students`).

**M. FIXED — role checks are now tenant-scoped.** `students/views.py`, `fees/views.py`,
`teachers/views.py`, `communication/views.py` and `academics/views.py` all resolve the caller's
role with `get_membership_role(user, request.tenant)` (`utils/permissions.py`), so a user who belongs
to **two schools with different roles** now gets the correct role for the school they are addressing.
`IsAccountant` is wired into the fee write path, so the `accountant` role is no longer dead code.

**N. `flow.md` is out of date.** It documents `JWTAuthenticationMiddleware` and
`tenants/middleware.py::TenantMiddleware`; neither exists. The implemented design is the per-view
mixin - which is precisely why Bugs A and E existed. Promoting tenant resolution to middleware
would reconcile the doc with the code and fix E.

**O. Demo seeding is Free-plan only.** `seed_demo` creates a demo tenant on the Free plan (migration-created, price 0, ~10 students) with one login per core role and sample data for the Free-plan feature set. It deliberately does not create the platform super admin — `bootstrap_superadmin` (reads `SUPERADMIN_*` from `.env`) does that, and the superadmin `create-tenant` endpoint adds paid schools.

**P. Uncommitted layout migration.** `git status` in the backend shows the old flat layout
(`accounts/`, `tenants/`, `school_saas/`, `main.py`, ...) as deleted-unstaged while the new `apps/`
and `config/` directories are untracked (`??`). Nothing is lost, but the working tree does not
match any commit. Commit the restructure to keep history usable.

**Q. Pagination.** Fixed: `REST_FRAMEWORK` now uses `utils.paginations.StandardResultsSetPagination`
(page size 20, client `page_size` capped at 100). The frontend `useList` accepts both paginated
responses and legacy arrays, so existing screens continue to render arrays while the API avoids
returning entire large tables.

### Suggested order of work (remaining)

| Priority | Item | Why next |
|---|---|---|
| 1 | **S** — generate a real `SECRET_KEY` in `.env` | The last `check --deploy` warning; required before any real deployment |
| 2 | **P** — commit the restructure | History usability |
| 3 | **L**, **N** — hygiene | Quality, not blockers |

### How these findings were verified

```bash
cd school_saas-backend

.venv/bin/python manage.py check                    # -> 0 issues
.venv/bin/python manage.py showmigrations           # -> all apps [X]
.venv/bin/python manage.py test                     # -> Ran 61 tests, all OK
```

The original audit ran the app against a **throwaway test database** (Postgres
`test_school_saas`, created/destroyed by the test runner) and logged in as super_admin / admin /
hod / teacher / student via
`POST /api/auth/login/`, probing every endpoint in the tables above. The same scenarios are now
 codified as the permanent test suite in `apps/core/tests.py`, `apps/user_account/tests.py` and
`apps/academics/tests.py`.

---

