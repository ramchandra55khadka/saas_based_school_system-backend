# Data model — field reference

> Split out of the top-level [`README.md`](../README.md) so it can stay focused on
> business logic. Field-level tables and their historical notes are preserved here.

## Data model

30 concrete models across 8 model-bearing apps (`core` holds only abstract bases, `reports` has no
models at all), plus 2 abstract bases.
Every `tenant` FK below is `on_delete=CASCADE`.

### Abstract bases — `core.models` and `utils.abstract_model`

Two modules hold the shared bases. `utils/abstract_model.py` is the generic, project-agnostic
layer; `core.models` composes it with the tenancy FK.

| Model | Module | Purpose |
|---|---|---|
| `AbstractActiveModel` | `utils.abstract_model` | `is_active` BooleanField, default `True` |
| `AbstractUUID` | `utils.abstract_model` | `uuid` UUIDField — `default=uuid.uuid4`, `unique`, `db_index`, `editable=False` |
| `AbstractTimeStampedModel` | `utils.abstract_model` | `created_at` (`default=now`, `db_index`) + `updated_at` (`auto_now`, `db_index`) — the shared timestamps base |
| `AbstractCreatedByModifiedBy` | `utils.abstract_model` | `created_by` / `modified_by` FKs → `AUTH_USER_MODEL`, nullable, `SET_NULL` |
| `AbstractTenantModel` | `core.models` | extends `AbstractUUID` and adds `tenant` FK to `Tenant` with `related_name='%(class)s_records'` |

Timestamps are consolidated on a single `updated_at` (`auto_now`) everywhere. Mix
`AbstractTenantModel` + `AbstractTimeStampedModel` for normal tenant data; models that need no `updated_at`
column take `AbstractTenantModel` directly. Non-tenant models (`Tenant`, `UserProfile`, `Plan`,
and `Department`) mix in `utils.abstract_model.AbstractTimeStampedModel`; communication rows are
tenant-owned and use `AbstractTenantModel`.
(`AbstractCreatedAtModifiedAt` was folded into `AbstractTimeStampedModel` — the old dead `modified_at`
field became an auto-maintained `updated_at`.)

#### `AbstractTimeStampedModel`

```python
class AbstractTimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=now, db_index=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True
```

Both columns are indexed and `editable=False` (never rendered in forms/serializers as writable).
`created_at` uses `default=now`, **not** `auto_now_add`, so a data migration can supply historical
values. `updated_at` is `auto_now` — always refreshed on save (old rows that carried a NULL
`modified_at` were backfilled from `created_at` in the `…_modified_at_…_and_more` → `…updated_at`
rename migrations).

Inherited by: `communication.StudentPost`, `TeacherAnnouncement`, `Announcement`, `Message`,
`Notification`; `subscription.Plan`; `tenants.Tenant`, `tenants.Department`;
`user_profile.UserProfile`.

#### `AbstractCreatedByModifiedBy`

```python
class AbstractCreatedByModifiedBy(models.Model):
    created_by = models.ForeignKey(User, editable=False, blank=True, null=True,
                                   related_name='created_%(app_label)s_%(class)s',
                                   on_delete=models.SET_NULL)
    modified_by = models.ForeignKey(User, editable=False, blank=True, null=True,
                                    related_name='modified_%(app_label)s_%(class)s',
                                    on_delete=models.SET_NULL)

    class Meta:
        abstract = True
```

`User` is `AUTH_USER_MODEL` (`user_account.UserAccount`) — the FK uses the lazy string target
because `utils/abstract_model.py` is imported while the app registry is still loading, so
`get_user_model()` at module level would raise `AppRegistryNotReady`.

The reverse accessors embed `%(app_label)s_%(class)s` (`created_students_student`,
`modified_fees_studentinvoice`, …) so every model gets a collision-free name. Both fields are
nullable/`SET_NULL` and are **not** auto-populated — set them explicitly (typically from
`request.user`) where the audit trail matters. No model adopts this base yet.

#### `AbstractTenantModel` / `AbstractTimeStampedModel`

Mix `AbstractTenantModel` + `AbstractTimeStampedModel` for normal tenant data; `AbstractTenantModel` alone when you don't
want timestamps (this is what `communication` uses, paired with `AbstractCreatedAtModifiedAt`).

### `tenants`

**`Tenant`** — *one row per school.* `Meta.verbose_name = 'School'`, ordering by `tenant_name`.

| Field | Type | Notes |
|---|---|---|
| `tenant_id` | UUID | **PK**, `default=uuid.uuid4`, `editable=False` |
| `tenant_name` | CharField(255) | **unique** |
| `org_code` | CharField(100) | **unique** — organisation/registration code |
| `address` | TextField | blank |
| `phone` | CharField(20) | blank |
| `email` | EmailField | blank |
| `website` | URLField | blank |
| `logo` | ImageField | `upload_to='school_logos/'`, nullable |
| `established_year` | PositiveIntegerField | nullable |
| `is_active` | BooleanField | default `True` |
| `created_at` | DateTimeField | from `AbstractCreatedAtModifiedAt` — `default=now`, `db_index`, `editable=False` |
| `modified_at` | DateTimeField | from `AbstractCreatedAtModifiedAt` — nullable, `db_index`, `editable=False` |

**`SchoolSettings`** — per-school configuration, `OneToOneField(Tenant, related_name='settings')`.

| Field | Choices | Default |
|---|---|---|
| `academic_year_format` | free text, e.g. `2026-2027` | `'YYYY-YYYY'` |
| `grading_system` | `percentage`, `gpa`, `letter` | `percentage` |
| `attendance_type` | `daily`, `period` | `daily` |
| `timezone` | free text | `'Asia/Kathmandu'` |

### `user_account`

**`RoleChoices`** (TextChoices) — the *per-school* role vocabulary. Nine members: `admin`,
`principal`, `hod`, `teacher`, `student`, `parent`, `librarian`, `accountant`, `staff`.
There is deliberately **no `super_admin`**: platform access is the `is_superuser` flag, because a
super admin belongs to no tenant and therefore holds no membership. Defined in
`user_account/constants.py` and re-exported from `models.py`.

**`UserAccount`** extends `AbstractUser` — the `AUTH_USER_MODEL`
(`user_account.UserAccount`). Shared across all tenants; it carries **no role of its own**.

| Field | Type | Notes |
|---|---|---|
| `uuid` | UUIDField | auto (`uuid.uuid4`), unique + indexed — stable public identifier |
| `username` | CharField(300) | unique |
| `email` | EmailField | unique — **the login identifier** |
| `phone` | CharField(20) | blank |
| `email_is_verified` / `phone_is_verified` | BooleanField | default `False`; flipped by the verification flows, read-only on the API |

There are **no** `first_name` / `last_name` columns: personal details live on
`user_profile.UserProfile` (OneToOne, `user.profile`), and `get_full_name()` /
`get_short_name()` are overridden to read from it (falling back to the username
when no profile row exists).

Methods: `is_super_admin()` (→ `is_superuser`) and `role_for_tenant(tenant)` (→ the role from the
matching active `TenantMembership`, or `None`). Ordering is `['username']`. `has_usable_password()`
always returns `False`: Django's password-reset machinery treats these accounts as passwordless,
while the login endpoint still verifies the stored hash through `ModelBackend` (which never
consults this flag).

### UUID identity (`utils/abstract_model.py`)

Every model except `Tenant` (whose PK `tenant_id` already is a UUID) carries a `uuid`
UUIDField — auto-generated `uuid4`, `unique` + indexed, `editable=False`. Tenant-scoped models
get it through `core.models.AbstractTenantModel` (mixed with `utils.abstract_model.AbstractTimeStampedModel`), which inherits
`utils.abstract_model.AbstractUUID`; standalone models (`UserProfile`, `TenantMembership`,
`Department`, `SchoolSettings`, `Plan`, `Subscription`) inherit the mixin directly. The
`utils.migrations.AddUUIDField` operation keeps `makemigrations` output backfill-safe: it adds
the column nullable, assigns one distinct uuid per existing row, then applies `NOT NULL` +
unique.

**`TenantMembership`** — links a user to a school with a role; the single source of truth for
authorization.

| Field | Type | Notes |
|---|---|---|
| `user` | FK → `UserAccount` | `related_name='memberships'` |
| `tenant` | FK → `Tenant` | `related_name='memberships'` |
| `role` | CharField(30) | one of `RoleChoices` |
| `is_active` | BooleanField | default `True` |
| `joined_at` | DateTimeField | `auto_now_add` |

`unique_together = ('user', 'tenant')`; ordering `['-joined_at']`.

### `user_profile`

**`UserProfile`** — personal information for a `UserAccount` (OneToOne, `related_name='profile'`):
`first_name`, `last_name`, `phone`, `gender`, `date_of_birth`, `nationality`, `address`,
`profile_image`, `created_at`, `updated_at`. **Not tenant-scoped by design.** Tenant scope comes
from `TenantMembership` plus the role/domain records (`Student`, `Parent`, `Staff`, `Teacher`).
Adding a `tenant` FK here would duplicate `TenantMembership.tenant` and the role-record tenant and
would require keeping three tenant values in sync.

Timestamps come from `AbstractTimeStampedModel` (plus `AbstractUUID`). The old `modified_at` column
was renamed to auto-maintained `updated_at` in migrations.

### `staff`

**`Staff`** (`AbstractTenantModel` + `AbstractTimeStampedModel`) — OneToOne to `UserProfile` (`related_name='staff'`) plus
`designation`, `employee_id`, `department` FK → `tenants.Department` (`SET_NULL`), `qualification`,
`specialization`, `date_of_joining`, `is_active`. `designation` ∈ `principal`, `teacher`,
`librarian`, `accountant`, `admin`, `support`, `other` (**default**). `qualification` is a
choice field ∈ `plus_two`, `diploma`, `bachelor`, `master`, `mphil`, `phd`, `other`. `clean()`
requires the account's membership role to suit the chosen `designation` — the mapping is
`staff/constants.py::DESIGNATION_ALLOWED_ROLES`. Unique: `(tenant, employee_id)` when
`employee_id` is non-empty.

`staff/constants.py` keeps `STAFF_TYPE_*` aliases for the old names (`STAFF_TYPE_CHOICES =
DESIGNATION_CHOICES`) so imports that have not migrated yet keep working.

### `library`

**`LibraryMember`** — borrower record: `member_type` (`student`/`staff`), OneToOne to
`students.Student` **or** `staff.Staff`, `card_number`, `is_active`. `clean()` enforces
exactly one of the two FKs. Unique: `(tenant, card_number)`.

**`BookCategory`** — `name`, `description`. Unique per `(tenant, name)`.

**`Book`** — `title`, `isbn`, `category` FK (`SET_NULL`), `authors`, `publisher`, `published_year`.

**`BookCopy`** — `book` FK (`related_name='copies'`), `accession_number`, `status`
(`available`/`issued`/`lost`/`damaged`, default `available`). Unique:
`(tenant, accession_number)`.

**`BookIssue`** — `member` FK, `book_copy` FK, `issued_by` FK → `staff.Staff` (`SET_NULL`),
`issued_at`, `due_date`, `returned_at`, `fine_amount`, `status` (`issued`/`returned`/`lost`).
`clean()` requires `returned_at` once the status is `returned`.

### `subscription`

**`Plan`** — a purchasable tier.

| Field | Type | Notes |
|---|---|---|
| `name` | CharField(100) | display name |
| `price` | Decimal(10,2) | |
| `duration_days` | PositiveIntegerField | default `30` — drives `Subscription.end_date` |
| `max_students` | PositiveIntegerField | default `100` |
| `is_active` | BooleanField | default `True` |
| `created_at` | DateTimeField | `auto_now_add` |

**`Subscription`** — one per school (`OneToOneField(Tenant, related_name='subscription')`).

| Field | Type | Notes |
|---|---|---|
| `plan` | FK → `Plan` | `on_delete=PROTECT` |
| `start_date` | DateTimeField | `auto_now_add` |
| `end_date` | DateTimeField | computed on create/update from `plan.duration_days` |
| `is_active` | BooleanField | default `True` |
| `days_remaining` | property | `max(0, (end_date - now).days)` |

### `academics`

| Model | Key fields | Constraints |
|---|---|---|
| **`AcademicYear`** | `name`, `start_date`, `end_date`, `is_current` | `unique_together = (tenant, name)`, ordering `-start_date` |
| **`Class`** | `name` (e.g. "Grade 10"), `numeric_name` (ordering) | `unique_together = (tenant, name)`, ordering `numeric_name` |
| **`Section`** | `name` (A/B/C), `school_class` FK → `Class` | `unique_together = (school_class, name)` |
| **`Subject`** | `name`, `code`, `credit_hours`, `is_optional` | `unique_together = (tenant, code)` |
| **`TeacherAssignment`** | `teacher` FK → `User`, `subject`, `section`, `academic_year` | `unique_together = (teacher, subject, section, academic_year)` |
| **`TimetableEntry`** | `section`, `subject`, `teacher` FK → `User`, `academic_year`, `day_of_week`, `period_number`, `start_time`, `end_time` | `unique_together = (section, day_of_week, period_number, academic_year)` |

`day_of_week` choices: `monday … saturday` (six days).

Relations to note:

- `Class` ← `Section` is `related_name='sections'`.
- `Student.school_class` / `.section` point at `academics.Class` / `academics.Section` via string references, so `students` depends on `academics` at migration level.
- `Student.user_profile` is an O2O to the tenant-neutral `user_profile.UserProfile`; the tenant scope comes from `Student.tenant` plus the account's `TenantMembership`. `parents.Parent`/`StudentGuardian` import `students.models` directly, so `parents` depends on both `students` and `user_profile`.
- `TeacherAssignment.teacher` and `TimetableEntry.teacher` are FKs to **`User`**, not `teachers.Teacher` — a teacher is any user with a membership whose role is `teacher`/`hod`/`principal`.

### `students`

**`Student`** (`AbstractTenantModel` + `AbstractTimeStampedModel`) — student-specific information linked to a `UserProfile`
(OneToOne, `related_name='student'`). Identity fields (`date_of_birth`, `address`) live on the
profile; this model keeps only the school-side record.

| Model | Key fields | Notes |
|---|---|---|
| **`Student`** | `user_profile` **O2O** → `user_profile.UserProfile` (`related_name='student'`), `school_class` FK (`SET_NULL`, nullable, `related_name='profile_students'`), `section` FK (`SET_NULL`, nullable, `related_name='profile_students'`), `roll_number` (PositiveIntegerField, nullable), `admission_date`, `blood_group` | ordering `['school_class', 'section', 'roll_number']`; unique `(tenant, school_class, section, roll_number)` where `roll_number` is not null; `clean()` requires an active `student` membership |
| **`StudentDocument`** | `student` FK (`related_name='documents'`), `document_type`, `title`, `file` | `file` → `upload_to='student_documents/%Y/%m/'` |
| **`StudentAttendance`** | `student`, `academic_year`, `section`, `date`, `status`, `remarks` | `unique_together = (student, date)` |
| **`Exam`** | `name`, `exam_type`, `academic_year`, `start_date`, `end_date`, `description` | ordering `-start_date` |
| **`ExamResult`** | `exam`, `student`, `subject`, `marks_obtained`, `max_marks`, `grade`, `remarks` | `unique_together = (exam, student, subject)` |
| **`StudentPromotion`** | `student`, `from_class`, `to_class`, `from_academic_year`, `to_academic_year`, `promoted_by` FK → `User` (`SET_NULL`), `remarks` | set automatically from the request user |

Choice sets:

- `StudentDocument.document_type`: `birth_certificate`, `transfer_certificate`, `marksheet`, `photo`, `other`
- `StudentAttendance.status`: `present`, `absent`, `late`, `excused`
- `Exam.exam_type`: `unit_test`, `midterm`, `final`, `other`

### `parents`

| Model | Key fields | Notes |
|---|---|---|
| **`Parent`** | `user_profile` **O2O** → `user_profile.UserProfile` (`related_name='parent'`), `occupation`, `emergency_contact` | `clean()` requires an active `parent` membership |
| **`StudentGuardian`** | `student` FK → `students.Student` (`related_name='guardians'`), `parent` FK → `Parent` (`related_name='wards'`), `relation`, `is_primary` | unique `(student, parent)`; `clean()` keeps both ends in the same tenant |

Choice sets:

- `StudentGuardian.relation`: `father`, `mother`, `guardian`, `other`

### `teachers`

| Model | Key fields | Notes |
|---|---|---|
| **`Teacher`** | `staff` FK → `staff.Staff` (`related_name='teachers'`), `teaching_license_number`, `primary_subject` FK → `academics.Subject` (`SET_NULL`, nullable, `related_name='primary_teachers'`), `homeroom_section` FK → `academics.Section` (`SET_NULL`, nullable, `related_name='homeroom_teachers'`), `max_weekly_periods`, `office_hours`, `bio` | ordering `['staff__user_profile__first_name', 'staff__user_profile__last_name']`; `clean()` requires an active teaching membership (`TEACHING_MEMBERSHIP_ROLES`) |
| **`TeacherAttendance`** | `teacher` FK → `Teacher` (`related_name='attendance_records'`), `date`, `status`, `check_in_time`, `check_out_time`, `remarks` | `unique_together = (teacher, date)` |
| **`LeaveRequest`** | `teacher` FK → `Teacher` (`related_name='leave_requests'`), `leave_type`, `start_date`, `end_date`, `reason`, `status`, `approved_by` FK → `User` (`SET_NULL`), `responded_at` | ordering `-created_at` |

> **⚠️ A teacher row is not a credential.** `Teacher.staff` points at a `staff.Staff` row, which in turn
> is the OneToOne to `user_profile.UserProfile` — so `Teacher` holds no identity fields of its own:
> `teacher.staff.user_profile` is the person, and `teacher.staff.employee_id` the employee number.
> A `Staff` row may have several `Teacher` rows (one per tenant), the same way a person can hold more
> than one staff designation.

Choice sets:

- `TeacherAttendance.status`: `present`, `absent`, `late`, `on_leave`
- `LeaveRequest.leave_type`: `sick`, `casual`, `earned`, `maternity`, `other`
- `LeaveRequest.status`: `pending` (default), `approved`, `rejected`

### `fees`

| Model | Key fields | Notes |
|---|---|---|
| **`FeeType`** | `name`, `description` | `unique_together = (tenant, name)` |
| **`FeeStructure`** | `fee_type`, `academic_year`, `school_class`, `amount` Decimal(10,2) | `unique_together = (fee_type, academic_year, school_class)` |
| **`StudentInvoice`** | `student` FK → `students.Student` (`related_name='invoices'`), `title`, `academic_year`, `total_amount`, `due_date`, `status` | `unpaid` / `partial` / `paid` (default `unpaid`) |
| **`FeePayment`** | `invoice` FK (`related_name='payments'`), `amount_paid`, `payment_date` (`auto_now_add`), `payment_method`, `receipt_number`, `transaction_id`, `remarks` | `receipt_number` unique |

Business logic baked into the models:

- `StudentInvoice.amount_paid` — property, sums `payments.amount_paid`.
- `StudentInvoice.balance_due` — property, `total_amount - amount_paid`.
- `FeePayment.save()` — auto-generates `receipt_number` as `REC-<8 hex chars upper>` when blank,
  then **recalculates the parent invoice status**: `paid` when `balance_due <= 0`, `partial` when
  anything has been paid, otherwise left `unpaid`.
- `payment_method` choices: `cash`, `bank_transfer`, `cheque`, `online`.

### `communication`

These five models inherit **`AbstractTenantModel`** only (no timestamps), so they have `tenant`
and their own `created_at` but no `updated_at`.

| Model | Field | Notes |
|---|---|---|
| **`StudentPost`** | `student` FK → `User` (`related_name='student_posts'`), `title`, `content`, `created_at` | `student` set from the request user |
| **`TeacherAnnouncement`** | `teacher` FK → `User` (`related_name='teacher_announcements'`), `title`, `content`, `created_at` | `teacher` set from the request user |
| **`Announcement`** | `sender` FK → `User` (`related_name='announcements_sent'`), `target_audience`, `title`, `body`, `created_at` | ordering `-created_at` |
| **`Message`** | `sender` FK (`related_name='messages_sent'`), `recipient` FK (`related_name='messages_received'`), `subject`, `body`, `is_read`, `created_at` | direct messaging |
| **`Notification`** | `user` FK (`related_name='notifications'`), `title`, `message`, `is_read`, `created_at` | per-user alerts |

`Announcement.target_audience` choices: `all`, `teachers`, `students`, `parents`.

### `reports`

No models and no migrations — it is a pure read layer of four `APIView`s that aggregate data from
`students`, `teachers` and `fees`.

---

