# Technology, repository layout & architecture

> Split out of the top-level [`README.md`](../README.md) so it can stay focused on
> business logic. Content preserved from the original README; sections that used to
> be anchors in README.md now live in this file.

## Tech stack

| Layer | Choice | Version |
|---|---|---|
| Language | Python | `>= 3.13` (`.python-version` = `3.13`) |
| Framework | Django | `>= 5.2.7` |
| API | Django REST Framework | `>= 3.16.1` |
| Auth | djangorestframework-simplejwt + pyjwt | `>= 5.5.1` / `>= 2.10.1` |
| CORS | django-cors-headers *(declared, not yet wired)* | `>= 4.7.0` |
| Config | python-decouple (reads `.env` in `settings.py`) | `>= 3.8` |
| Logging | loguru | `>= 0.7.3` |
| Images | pillow | `>= 11.0.0` |
| Database | PostgreSQL (psycopg 3) | `psycopg[binary] >= 3.2` |
| Packaging | uv (`pyproject.toml` + `uv.lock`) | — |

`pyproject.toml` declares the project as `name = "school-saas"`, `version = "0.1.0"`,
`description = "Multi-tenant SaaS School Management System"`, `requires-python = ">=3.13"`.

---

## Repository layout

```
school_saas-backend/
├── manage.py                  # Django entry point (DJANGO_SETTINGS_MODULE=config.settings)
├── pyproject.toml             # project metadata + dependencies (uv)
├── uv.lock                    # locked dependency graph
├── .python-version            # 3.13
├── .env                       # local secrets/overrides (git-ignored)
├── db.sqlite3                 # development database (git-ignored)
├── flow.md                    # request/tenant-flow notes (partially aspirational — see Known gaps)
├── architecture.png / image.png
├── .github/workflows/deploy.yml
│
├── config/                    # ← Django project package
│   ├── settings.py            # INSTALLED_APPS, MIDDLEWARE, REST_FRAMEWORK, SIMPLE_JWT
│   ├── urls.py                # root URLConf: /admin/ + /api/<app>/
│   ├── asgi.py
│   └── wsgi.py
│
└── apps/                      # ← all business apps live here (a Python package)
    ├── core/                  # shared abstractions — no models of its own
    │   ├── models.py          #   AbstractTenantModel (abstract)
    │   ├── mixins.py          #   TenantViewSet, TenantRequiredMixin, TenantQuerysetMixin
    │   └── permissions.py     #   every role permission class
    ├── tenants/               # Tenant, SchoolSettings, Department
    ├── user_account/          # UserAccount, TenantMembership, auth views, CustomJWTMiddleware
    ├── user_profile/          # UserProfile (personal info for any account)
    ├── staff/                 # Staff (principal/teacher/librarian/accountant/admin/support)
    ├── subscription/          # Plan, Subscription
    ├── academics/             # AcademicYear, Class, Section, Subject, TeacherAssignment, TimetableEntry
    ├── library/               # LibraryMember, BookCategory, Book, BookCopy, BookIssue
    ├── students/              # Student, StudentDocument, StudentAttendance, Exam, ExamResult, StudentPromotion
    ├── parents/               # Parent, StudentGuardian
    ├── teachers/              # Teacher, TeacherAttendance, LeaveRequest
    ├── fees/                  # FeeType, FeeStructure, StudentInvoice, FeePayment
    ├── communication/         # StudentPost, TeacherAnnouncement, Announcement, Message, Notification
    └── reports/               # no models — read-only aggregation APIViews
```

> **Namespacing:** apps are registered and imported as `apps.<name>` (e.g. `apps.students`) —
> `INSTALLED_APPS`, the root URLconf and every internal import use that path, so nothing puts
> `apps/` on `sys.path`. Each `apps/<name>/apps.py` sets `name = 'apps.<name>'` with an explicit
> `label = '<name>'`, so models, migrations and `AUTH_USER_MODEL = 'user_account.UserAccount'`
> keep their short labels. This means test labels are `apps.user_account` rather than
> `user_account` (plain `manage.py test` auto-discovers everything and needs no labels).

`settings.py` sets `AUTH_USER_MODEL = 'user_account.UserAccount'`, so the custom user model must be in place
before the first `migrate`.

---

## Architecture

### Tenancy model

This is a **shared-schema, same-domain** multi-tenancy design:

| Concern | Implementation |
|---|---|
| Tenant identity | `tenants.Tenant` — UUID primary key (`tenant_id`), unique `tenant_name` + `org_code` |
| Row ownership | every tenant-owned model inherits `core.models.AbstractTenantModel` (+ `utils.abstract_model.AbstractTimeStampedModel`) → a `tenant` FK |
| User → tenant link | `accounts.TenantMembership` (user, tenant, role, is_active), unique per pair |
| Active tenant per request | the `active_tenant_id` JWT claim, resolved into `request.tenant` |
| Enforcement | `TenantQuerysetMixin` filters `queryset` by `request.tenant`; `perform_create()` stamps it |

Because it is shared-schema, isolation is **application-level**. Any new tenant-owned model must
inherit `AbstractTenantModel` (+ `AbstractTimeStampedModel`) and be exposed through `TenantViewSet` (or filter on
`request.tenant` manually) — otherwise it will leak across schools.

### Authentication & tenant resolution flow

```
 Browser (HttpOnly cookies: access, refresh)
        │
        ▼
 [ CustomJWTMiddleware ]  apps/user_account/middleware.py
   ├─ reads request.COOKIES["access"]  (name from settings.JWT_ACCESS_COOKIE)
   ├─ if no Authorization header → request.META["HTTP_AUTHORIZATION"] = "Bearer <token>"
   └─ logs presence/short prefix via loguru (debug)
        │
        ▼
 [ DRF JWTAuthentication ]  (REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES)
   ├─ validates the Bearer token → request.user
   └─ keeps the decoded token on request.auth  (payload readable)
        │
        ▼
 [ TenantViewSet.dispatch ]  apps/core/mixins.py → TenantRequiredMixin
   ├─ path in PUBLIC_PATHS ("/api/auth/login/", "/api/auth/super-user/login/",
   │  "/api/auth/refresh/", "/api/auth/logout/",
   │  "/superadmin/create-tenant/", "/admin/", "/static/", "/media/") → skip tenant binding
   ├─ not authenticated → 401 {"detail": "Authentication required"}
   ├─ user.is_super_admin() → skip tenant binding (no request.tenant)
   ├─ no request.auth → 401 {"message": "Invalid token"}
   ├─ payload lacks "active_tenant_id" → 400 {"message": "Tenant context missing"}
   └─ Tenant.objects.get(tenant_id=UUID(claim)) → request.tenant
        │
        ▼
 [ TenantQuerysetMixin.get_queryset ]
   ├─ no request.tenant → qs.none()          (fail closed)
   ├─ model is User  → qs.filter(tenantmembership__tenant=tenant)
   └─ model has .tenant → qs.filter(tenant=tenant)
        │
        ▼
 [ perform_create ] → serializer.save(tenant=request.tenant)
        │
        ▼
   tenant-isolated JSON response
```

> **Historical note — Bug A (fixed):** this mixin previously hooked into `dispatch()`, which ran
> *before* DRF authentication, so every tenant-scoped endpoint answered
> `401 {"detail": "Authentication required"}` for every role. Tenant resolution has since moved
> into `perform_authentication()` (shown above). Full post-mortem in
> [`docs/roadmap.md`](roadmap.md#a-fixed-was-critical---every-tenantviewset-endpoint-returned-401).

### Middleware stack (`config/settings.py`)

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Must be directly after SecurityMiddleware (whitenoise docs).
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom: copy JWT from cookie to Authorization header (so DRF SimpleJWT works)
    'apps.user_account.middleware.CustomJWTMiddleware',
]
```

### Design notes

- **`CustomJWTMiddleware` deliberately does not authenticate.** It only copies the cookie into the
  `Authorization` header so the standard DRF SimpleJWT authenticator can do the work. This keeps
  DRF's permission/authentication pipeline intact (no hand-rolled token decoding in middleware).
- **Tenant binding is per-view, not global.** `TenantRequiredMixin` resolves the tenant in
  `perform_authentication()`, so views built on `TenantViewSet` (and `TenantAPIView` for plain
  `APIView`s, e.g. `reports/`) get `request.tenant` before permission checks run.
- **Super admins bypass tenancy.** `is_super_admin()` returns before tenant resolution, so
  `request.tenant` is unset for them; views that need tenant data must branch on this
  (`SchoolProfileViewSet` does; others don't).
- **Fail-closed query mixin.** A missing tenant yields `.none()`, never the full table.

`flow.md` describes a `JWTAuthenticationMiddleware` and a `tenants/middleware.py::TenantMiddleware`
that are **historical design notes only — neither file exists today.** The implemented behaviour is
the per-view mixin shown above.

### Response envelope

Convention across the codebase (not globally enforced by a renderer):

- DRF default for CRUD viewsets — a bare array or object.
- `{"status": "success", "data": ...}` for custom actions (`/me/`, report card, assigned classes, timetable).
- `{"message": "..."}` with 401/400 for tenant/auth failures from `TenantRequiredMixin`.
- `{"error": "..."}` for validation problems in report/bulk endpoints.

---

