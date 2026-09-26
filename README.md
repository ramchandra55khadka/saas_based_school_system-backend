# School SaaS — Backend

> Shared-schema, same-domain multi-tenant SaaS

Django 5.2 + DRF backend for a **multi-tenant School Management SaaS**. One deployment and one
database serve many schools (*tenants*). This file is the business-logic core; field-level schemas,
endpoint tables, setup and the bug log live in [`docs/`](docs/).

| Deep dive | Contents |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Stack, repo layout, request/tenant flow, middleware, response envelope |
| [`docs/data-model.md`](docs/data-model.md) | All 30 models, field tables, abstract bases |
| [`docs/api-reference.md`](docs/api-reference.md) | Every endpoint: method, permission, behaviour |
| [`docs/operations.md`](docs/operations.md) | Setup, `.env`, config, testing, CI/CD, deployment |
| [`docs/roadmap.md`](docs/roadmap.md) | Bug post-mortems (A–Q) and open items |

---

## 1. Business model

A **platform** (the SaaS operator, modelled as `UserAccount.is_superuser` with no tenant
membership) sells subscriptions to independent **schools** (tenants).

- **`Plan`** — `name`, `price`, `duration_days`, `max_students`, `features[]`. Super-admin managed;
  every authenticated user can read the catalogue.
- **`Subscription`** — ties a tenant to a plan. `perform_create` derives `start_date = now`,
  `end_date = start + plan.duration_days`, `is_active = True`; changing the plan on renewal
  **recomputes** `end_date`. `tenant`/`start_date`/`end_date` are read-only in serializers.
- **`UserAccount`** + **`UserProfile`** — one identity (email/password) and one shared personal
  profile. Their place in a school is a **`TenantMembership`**, the pivot that carries exactly one
  **role**: `admin, principal, hod, teacher, student, parent, librarian, accountant, staff`.
- One account may hold memberships in many schools with different roles. The JWT embeds an
  `active_tenant_id`, so a single login operates in exactly one school at a time.
- **Tenant creation is one super-admin transaction** — `Tenant` + first `admin` account +
  membership are created together, so a school can never exist without an owner
  (`POST /api/accounts/superadmin/create-tenant/`).

## 2. How tenancy works

One shared schema; isolation is enforced in application code.

1. **Auth is cookie-based JWT.** `POST /api/accounts/login/` validates email + password, embeds
   `active_tenant_id` (omitted for super admins) and sets `access` + `refresh` HttpOnly cookies.
   `CustomJWTMiddleware` only copies the cookie into the `Authorization` header; SimpleJWT does the
   real authentication.
2. **Tenant binding is per-view.** `TenantRequiredMixin.perform_authentication()` resolves
   `request.tenant` from the JWT claim *after* token validation and *before* permission checks.
   Super admins skip resolution — `request.tenant` stays unset and views branch on that.
3. **Querysets fail closed.** `TenantQuerysetMixin.get_queryset()` returns `.none()` when no tenant
   is bound, filters `tenant=tenant` on tenant-owned models and `memberships__tenant` on
   `UserAccount`. A missing tenant can never leak another school's rows.
4. **`tenant` is never client-supplied.** It is a read-only serializer field everywhere;
   `perform_create()` stamps `serializer.save(tenant=request.tenant)`.
5. **Cross-tenant references are validated in models.** `ensure_same_tenant()` in `clean()` rejects
   e.g. a `Teacher` whose `Staff` record or `primary_subject` belongs to another school.

## 3. How access control works

Every role check is **tenant-scoped**: `HasTenantRole` requires an *active membership with that
role in the request's tenant*, so an `admin` in school A has no admin rights in school B. Super
admins pass most checks via `allow_super_admin=True`.

| Permission class | Membership role | Used for |
|---|---|---|
| `IsSuperAdmin` | — (platform flag) | create-tenant, plan writes |
| `IsTenantAdmin` / `IsAdminOrSuperAdmin` | `admin`, `principal` | school profile/settings, subscriptions |
| `IsFinanceManager` | `admin`, `principal`, `accountant` | every finance write |
| `IsAdminOrHOD` | `admin`, `principal`, `hod` | academic reference data, students, exams, documents, promotions, teacher records, announcements, reports |
| `IsAdminOrHODOrTeacher` | the above **+ `teacher`** | student attendance & exam-result entry |
| `IsTeacher` | `teacher` | creating a leave request |
| `IsAdminOrHodUserManagement` | `admin`/`principal`/`hod` | user CRUD; object-level, an HOD only manages `teacher`/`student` members |

On top of class permissions, viewsets row-scope via `get_membership_role()`: a teacher sees only
their own profile/attendance/leave, a student only their own profile/attendance/results/invoices,
timetables resolve to the caller's own periods or section, `AnnouncementViewSet` filters by
`target_audience` (`all` + the caller's audience; leadership sees everything), and
`MessageViewSet`/`NotificationViewSet` expose only rows addressed to or from the caller.

## 4. Key business rules

- **Plan features are the module switchboard.** `Plan.features` is a writable list of
  `FeatureKey` strings (super admin only). `HasFeatureAccess` re-reads them on every request, so a
  grant or revocation applies immediately; a missing feature returns `403`.
- **Invoice status is derived, never client-supplied.** `FeePayment.save()` recomputes the parent
  `StudentInvoice.status` (`unpaid → partial → paid` from total paid vs `total_amount`); the field
  is read-only in serializers. Invoices expose computed `amount_paid`, `balance_due`, `payments[]`.
- **Bulk invoicing** — `POST /api/fees/invoices/generate-class-invoices/` (admin/principal) requires
  `class_id`, `academic_year_id`, `title`, `due_date`; sums every `FeeStructure` for that class +
  year, returns `400` when the total is 0, otherwise `bulk_create`s one invoice per student.
- **Report cards are computed on the fly** — `GET /api/students/exams/{id}/report-card/{student_id}/`
  aggregates `ExamResult` rows into `total_obtained`, `total_max`, `percentage` (2 dp) and a
  per-subject grade list; a `student` may only request their own id (`403` otherwise).
- **Leave lifecycle** — `teacher` is auto-resolved from the caller's `Staff`/`Teacher` chain and
  never accepted from the payload (`ValidationError` with no teaching record); `approve`/`reject`
  (admin/principal/HOD) stamp `approved_by` and `responded_at`. Promotions stamp `promoted_by` and
  are admin/principal/HOD-only.
- **Fee writes are finance-office territory** — fee types, structures, invoices, payments, refunds,
  discounts, expenses and payroll are admin/principal/`accountant`, matching the three roles the
  frontend shows the Fees page to, while reads stay open to every member. Independently the whole
  finance API is feature-gated, so a plan without `finance` yields `403` everywhere. Duplicate
  names return a clean `400` via per-tenant `validate_*`.
- **Announcements have audiences, messages have recipients** — `mark-read` on a message is guarded
  to the recipient (`403` otherwise).
- **Departments are the school's own pick-list** — admin/principal/HOD writes, open reads (the staff
  form and teacher onboarding list them), `tenant` filled from the JWT, and
  `unique_together = ('tenant', 'name')` so two schools can each have their own "Science".
- **`Staff` ↔ `Teacher` split** — `Staff` is the generic employment record (designation, employee_id,
  department); `Teacher` is the teaching-specific record (license, primary subject, homeroom, weekly
  periods) hanging off it. Identity lives on `UserProfile`, employment on `Staff`.
- **Atomic onboarding** — `POST /api/{staff,students,teachers}/…/onboard/` create account, profile,
  membership and the domain row in one transaction from one payload, with the role derived
  (designation), fixed (`student`) or pinned (`teacher`), always checked against `grantable_roles()`.
  Class/section/department/subject must belong to the school, and the students action enforces the
  plan's `max_students` before writing (admin/HOD only). Any failure leaves nothing behind.

## 5. Quick start

```bash
uv sync && cp .env.example .env      # fill in DB_* credentials
uv run python manage.py migrate
uv run python manage.py seed_demo    # demo school on the Free plan
uv run python manage.py bootstrap_superadmin
uv run python manage.py runserver
```

Then `POST /api/accounts/login/` (JWT cookies are set for you) and `GET /api/accounts/me/` to list
memberships. Full setup in [`docs/operations.md`](docs/operations.md).

## 6. Known gaps

`Class.max_students` is stored but not enforced · no parent↔student link, so parents get
tenant-wide reads for invoices and timetable · media served by Django in development only ·
`/api/parents/` is registered twice in `config/urls.py` (harmless duplicate). Tracked in
[`docs/roadmap.md`](docs/roadmap.md).
