# API reference

> Split out of the top-level [`README.md`](../README.md) so it can stay focused on
> business logic. Endpoint tables are preserved here.

## API reference

All routes are registered in `config/urls.py`:

| Base path | Included URLConf |
|---|---|
| `/admin/` | Django admin |
| `/api/accounts/` | `apps.user_account.urls` |
| `/api/user-profile/` | `apps.user_profile.urls` |
| `/api/staff/` | `apps.staff.urls` |
| `/api/parents/` | `apps.parents.urls` *(registered twice in `config/urls.py` — harmless)* |
| `/api/subscription/` | `apps.subscription.urls` |
| `/api/academics/` | `apps.academics.urls` |
| `/api/communication/` | `apps.communication.urls` |
| `/api/students/` | `apps.students.urls` |
| `/api/teachers/` | `apps.teachers.urls` |
| `/api/library/` | `apps.library.urls` |
| `/api/tenants/` | `apps.tenants.urls` |
| `/api/fees/` | `apps.fees.urls` |
| `/api/reports/` | `apps.reports.urls` |

### Global conventions

- **Auth is cookie-based.** Log in once; the browser then sends `access` + `refresh` automatically.
  `curl`/mobile clients must send the cookie themselves or set `Authorization: Bearer <access>`;
  `CustomJWTMiddleware` honours an existing `Authorization` header and only falls back to the cookie.
- **Trailing slashes are required** — all routers are DRF `DefaultRouter`s.
- **CRUD verbs** on every registered route: `GET` list, `POST` create, `GET {id}/`, `PUT`/`PATCH {id}/`, `DELETE {id}/`.
- **No pagination is configured** (`REST_FRAMEWORK` sets no `DEFAULT_PAGINATION_CLASS`), so list
  endpoints return a bare JSON array — not `{count, next, previous, results}`.
- **Permissions are global by default:** `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`, so every
  endpoint requires login unless it overrides `permission_classes` (only the auth endpoints do).
- `tenant` is a **read-only** serializer field everywhere — it is never accepted from the client,
  it is always derived from `request.tenant`.

### `user_account` — `/api/accounts/`

| Method | Endpoint | Permission | Behaviour |
|---|---|---|---|
| `POST` | `/api/accounts/login/` | public | Validates **`email` + `password`** credentials, mints a refresh token, embeds `active_tenant_id` (from the user's first active membership; **omitted** for super admins), returns `{message, access_token, refresh_token}` **and** sets `access` + `refresh` HttpOnly cookies. Unknown email, wrong password or inactive account → `401`. |
| `POST` | `/api/accounts/token/refresh/` | public (refresh cookie) | Reads the `refresh` cookie, returns `{message, access_token}` and re-sets the `access` cookie. `401` if the cookie is missing/invalid. |
| `POST` | `/api/accounts/logout/` | authenticated | Deletes both JWT cookies and returns `{message: "Logout successful"}`. Does **not** revoke the refresh token server-side. |
| `GET` | `/api/accounts/me/` | authenticated | `{status, data}` where `data` is the profile plus every membership (tenant, tenant_name, role, role_display, is_active, joined_at). |
| `POST` | `/api/accounts/superadmin/create-tenant/` | `IsSuperAdmin` | Creates a `Tenant` **and** its first `admin` user **and** the `TenantMembership` in one transaction. Body: `tenant_name`, `org_code`, `address?`, `admin_username`, `admin_email`, `admin_password`. |
| `GET/POST/PUT/PATCH/DELETE` | `/api/accounts/user-management/` | `IsAdminOrHodUserManagement` | Tenant-scoped user CRUD. List is filtered by `tenantmembership__tenant`. Admin may create `hod/teacher/student/parent/accountant`; HOD only `teacher/student`; creating a user also creates the membership. `password` is write-only. |

### `subscription` — `/api/subscription/`

| Method | Endpoint | Permission | Behaviour |
|---|---|---|---|
| `GET/POST/PUT/PATCH/DELETE` | `/api/subscription/plans/` | read: authenticated · write: `IsSuperAdmin` | Manage subscription tiers. |
| `GET/POST/PUT/PATCH/DELETE` | `/api/subscription/subscriptions/` | `IsAdminOrSuperAdmin` | Tenant-scoped (`TenantViewSet`). Create auto-computes `end_date = now + plan.duration_days`; changing the plan recalculates it. |
| `GET` | `/api/subscription/active-plans/` | authenticated | Read-only list of plans ordered by `price`. |

> Subscription serializers are aligned with the models (Bug D, fixed): `PlanSerializer` exposes
> `id, name, price, duration_days, max_students, is_active, created_at`;
> `SubscriptionSerializer` adds computed `plan_name`, `plan_price`, `plan_duration_days` and the
> model's `days_remaining`, with `tenant`/`start_date`/`end_date` read-only (computed by the view).

### `academics` — `/api/academics/`

**Reference data is readable by every authenticated member of the tenant; only admin/HOD can
write.** Teachers need classes/sections/subjects/years to fill their forms (mark attendance, enter
results) and students need them to label their own timetable, so the read side is deliberately open
(`ReferenceDataViewSet` in `academics/views.py` — `get_permissions()` returns `IsAdminOrHOD` only
for `create`/`update`/`partial_update`/`destroy`).

| Endpoint | Model | Read | Write | Role scoping |
|---|---|---|---|---|
| `/api/academics/academic-years/` | `AcademicYear` | any member | admin/HOD | tenant |
| `/api/academics/classes/` | `Class` | any member | admin/HOD | tenant |
| `/api/academics/sections/` | `Section` | any member | admin/HOD | tenant |
| `/api/academics/subjects/` | `Subject` | any member | admin/HOD | tenant |
| `/api/academics/teacher-assignments/` | `TeacherAssignment` | any member | admin/HOD | tenant |
| `/api/academics/timetable/` | `TimetableEntry` | any member | admin/HOD | **teacher → own periods (`teacher=user`); student → own section (`section__students__user=user`)** |

> The `timetable` scoping is what makes the teacher and student timetable screens work. There is no
> parent↔student link in the schema, so a parent gets the tenant-wide read (same simplification as
> `fees` — see [`docs/roadmap.md`](roadmap.md)).

### `students` — `/api/students/`

| Endpoint | Read | Write | Role scoping |
|---|---|---|---|
| `/api/students/profiles/` | authenticated | `IsAdminOrHOD` | a `student` only sees their own record (`Student.user_profile.user_account`) |
| `/api/students/documents/` | `IsAdminOrHOD` | `IsAdminOrHOD` | admin/HOD only, both read and write |
| `/api/students/attendance/` | authenticated | `IsAdminOrHODOrTeacher` | a `student` only sees their own records |
| `/api/students/exams/` | authenticated | `IsAdminOrHOD` | — |
| `/api/students/results/` | authenticated | `IsAdminOrHODOrTeacher` | a `student` only sees their own results |
| `/api/students/promotions/` | `IsAdminOrHOD` | `IsAdminOrHOD` | `promoted_by` is set automatically |

**Extra action — report card**

```
GET /api/students/exams/{exam_id}/report-card/{student_id}/
```

Any authenticated user; a `student` may only request their own `student_id` (otherwise `403`).
Returns `{status, data}` with `exam_name`, `exam_type`, `student_name`, `roll_number`, `class`,
`section`, a `results[]` array (`subject`, `marks_obtained`, `max_marks`, `grade`, `remarks`),
`total_obtained`, `total_max`, and `percentage` (rounded to 2 dp, only when `total_max > 0`).
`404` when the student has no results in that exam.

### `parents` — `/api/parents/`

| Endpoint | Read | Write | Role scoping |
|---|---|---|---|
| `/api/parents/parents/` | authenticated | `IsAuthenticated` | tenant-scoped via `TenantViewSet` |
| `/api/parents/guardians/` | authenticated | `IsAuthenticated` | tenant-scoped via `TenantViewSet` |

### `teachers` — `/api/teachers/`

| Endpoint | Read | Write | Role scoping |
|---|---|---|---|
| `/api/teachers/profiles/` | authenticated | `IsAdminOrHOD` | a `teacher` only sees own profile |
| `/api/teachers/attendance/` | authenticated | `IsAdminOrHOD` | a `teacher` only sees own attendance |
| `/api/teachers/leave-requests/` | authenticated | create: `IsTeacher` · update/delete/approve/reject: `IsAdminOrHOD` | a `teacher` only sees own requests |

**Extra actions**

| Method | Endpoint | Permission | Returns |
|---|---|---|---|
| `GET` | `/api/teachers/profiles/{id}/assigned-classes/` | authenticated | `{status, data}` — `TeacherAssignment`s (with subject / section / academic year) for that teacher |
| `GET` | `/api/teachers/profiles/{id}/timetable/` | authenticated | `{status, data}` — that teacher's `TimetableEntry`s |
| `POST` | `/api/teachers/leave-requests/{id}/approve/` | `IsAdminOrHOD` | sets `status='approved'`, `approved_by=request.user`, `responded_at=now` |
| `POST` | `/api/teachers/leave-requests/{id}/reject/` | `IsAdminOrHOD` | sets `status='rejected'`, `approved_by=request.user`, `responded_at=now` |

`POST /api/teachers/leave-requests/` takes no `teacher` field: `perform_create()` resolves it from
`request.user.teacher_profile` and raises a `ValidationError` ("No teacher profile found for this
user.") if the user has none.

### `fees` — `/api/fees/`

| Endpoint | Read | Write | Role scoping |
|---|---|---|---|
| `/api/fees/fee-types/` | authenticated | `IsAdminOrSuperAdmin` | — |
| `/api/fees/fee-structures/` | authenticated | `IsAdminOrSuperAdmin` | — |
| `/api/fees/invoices/` | authenticated | `IsAdminOrSuperAdmin` | a `student` only sees own invoices; a `parent` currently sees **all** tenant invoices (no parent↔student link exists yet) |
| `/api/fees/payments/` | authenticated | `IsAdminOrSuperAdmin` | a `student` only sees payments on their own invoices |

**Extra action — bulk invoicing**

```
POST /api/fees/invoices/generate-class-invoices/
```

`IsAdminOrSuperAdmin`. Body: `class_id`, `academic_year_id`, `title`, `due_date` (all required,
otherwise `400`). Sums every `FeeStructure` for that class + year; if the total is `0` it returns
`400` ("No fee structure found..."). Otherwise it `bulk_create`s one `StudentInvoice` per student in
the class and returns `{status, message: "Generated N invoices."}`.

Invoice payloads include computed `amount_paid`, `balance_due` and the nested `payments[]`; the
`status` field is read-only because `FeePayment.save()` maintains it.

### `communication` — `/api/communication/`

| Endpoint | Read | Write | Scoping |
|---|---|---|---|
| `/api/communication/student-posts/` | authenticated | student role only | `student` is linked server-side to the caller's own `Student` record (never a client id); edit/delete limited to the author or admin/principal/HOD |
| `/api/communication/teacher-announcements/` | authenticated | `teacher`/`hod`/`principal` | `teacher` is linked server-side to the caller's own `Teacher` record; edit/delete limited to the author or admin/principal/HOD |
| `/api/communication/announcements/` | authenticated | `IsAdminOrHOD` | read list is filtered by `target_audience` for non-admin roles |
| `/api/communication/messages/` | authenticated | authenticated | only messages the user sent or received; `sender` forced to `request.user` |
| `/api/communication/notifications/` | authenticated | authenticated | only the user's own notifications |

**Announcement audience filter** — `admin`/`hod`/`super_admin` see everything; `teacher` sees
`all` + `teachers`; `student` sees `all` + `students`; `parent` sees `all` + `parents`.

**Extra actions**

| Method | Endpoint | Behaviour |
|---|---|---|
| `POST` | `/api/communication/messages/{id}/mark-read/` | sets `is_read=True` if the caller is the recipient, else `403` |
| `POST` | `/api/communication/notifications/{id}/mark-read/` | sets `is_read=True` |

### `tenants` — `/api/tenants/`

| Endpoint | Permission | Methods | Behaviour |
|---|---|---|---|
| `/api/tenants/profile/` | `IsAuthenticated + IsTenantAdmin` | `GET, PUT, PATCH, HEAD, OPTIONS` | Super admins see **all** schools; a tenant admin sees only their own (`filter(tenant_id=tenant.tenant_id)`). `GET {id}/` uses `TenantDetailSerializer` and adds the subscription summary. |
| `/api/tenants/settings/` | `IsAuthenticated + IsTenantAdmin` | `GET, PUT, PATCH, HEAD, OPTIONS` | `SchoolSettings` for `request.tenant` only. |

Both are read/update only — `http_method_names` excludes `POST` and `DELETE`, so a school cannot be
created or destroyed here (creation happens through `/api/accounts/superadmin/create-tenant/`).

### `reports` — `/api/reports/`

All four are plain `APIView`s (no router).

| Method | Endpoint | Permission | Required query params | Returns |
|---|---|---|---|---|
| `GET` | `/api/reports/attendance/` | `IsAuthenticated + IsAdminOrHOD` | `academic_year_id` | `{students: {total_records, present, absent}, teachers: {total_records, present, absent}}` |
| `GET` | `/api/reports/fees/` | `IsAuthenticated + IsAdminOrSuperAdmin` | `academic_year_id` | `{total_billed, total_invoices, paid_invoices, unpaid_invoices, partial_invoices}` |
| `GET` | `/api/reports/exams/` | `IsAuthenticated + IsAdminOrHOD` | `exam_id` | `{subject_averages: [{subject__name, avg_obtained}], total_results}` |
| `GET` | `/api/reports/demographics/` | `IsAuthenticated + IsAdminOrHOD` | — | `{total_students, total_teachers, class_distribution: [{school_class__name, count}]}` |

A missing required query param returns `400 {"error": "<param> is required"}`.

All four extend `TenantAPIView`, so `request.tenant` is resolved in
`perform_authentication()` (Bug E fix — see [`docs/roadmap.md`](roadmap.md)) and every query is
filtered by the caller's tenant.

### `staff` — `/api/staff/`

| Endpoint | Read | Write | Role scoping |
|---|---|---|---|
| `/api/staff/staff/` | authenticated | authenticated | tenant-scoped via `TenantViewSet`; the generic employment record (`Staff`) for every school employee |

### `library` — `/api/library/`

All five are plain tenant-scoped CRUD (`TenantViewSet`, any authenticated member reads/writes):

`/api/library/members/`, `/api/library/categories/`, `/api/library/books/`,
`/api/library/copies/`, `/api/library/issues/` — `LibraryMember`, `BookCategory`, `Book`,
`BookCopy`, `BookIssue` respectively.

---

