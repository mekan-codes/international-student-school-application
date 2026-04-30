# Project Specification — International Lounge

## 1. Problem statement

International students at the school rely on shared, manually-tracked
systems: a substitute-food program with a small warehouse and a
daily-access locker, a cleaning rotation, borrowed equipment, and an
informal suggestion channel. These are currently managed across
spreadsheets, chat groups, and hallway notes — leading to lost stock,
missed cleaning shifts, and unclear membership status.

The International Lounge centralizes these systems into a single
role-based dashboard.

## 2. Version 1 features

V1 implements only the **substitute food management module**.

| Feature                                     | Admin | Manager | Sub-food Student | Std. Student |
|---------------------------------------------|:-----:|:-------:|:----------------:|:------------:|
| Login by email or student ID                |   ✅   |    ✅   |        ✅         |       ✅      |
| Public student registration                 |   —   |    —   |        ✅         |       ✅      |
| Profile: name, email, phone, privacy        |   ✅   |    ✅   |        ✅         |       ✅      |
| Self-service password change                |   ✅   |    ✅   |        ✅         |       ✅      |
| Admin dashboard                             |   ✅   |    ✅   |        —         |       —      |
| User management (edit students)             |   ✅   |    ✅   |        —         |       —      |
| User management (edit/delete staff)         |   ✅   |    —   |        —         |       —      |
| Promote student → manager                   |   ✅   |    —   |        —         |       —      |
| Demote manager → student                    |   ✅   |    —   |        —         |       —      |
| Reset another user's password               |   ✅   |    —   |        —         |       —      |
| Food item catalog                           |   ✅   |    ✅   |        —         |       —      |
| Warehouse / locker / transfer               |   ✅   |    ✅   |        —         |       —      |
| Shareable Food Log + CSV export             |   ✅   |    ✅   |        —         |       —      |
| Inventory history                           |   ✅   |    ✅   |        —         |       —      |
| Student dashboard (general)                 |   —   |    —   |        ✅         |       ✅      |
| Food availability page                      |   —   |    —   |        ✅         |       —      |

## 3. Roles & access control

### Decorators (server-side)

| Decorator        | Allows                  | Used for                                       |
|------------------|--------------------------|------------------------------------------------|
| `staff_required` | admin OR manager         | Most operational pages                         |
| `admin_required` | admin only               | Promote, demote, reset password                |
| `member_required`| sub-food student         | `/student/food`                                |
| `student_required`| any non-staff user      | Reserved for future student-only pages         |

### Account protection

- Users have an `is_protected` flag. Protected accounts can only be
  modified by themselves through their profile. Even admins cannot delete
  or demote a protected user.
- The seed creates the demo admin (`admin@school.com`) as protected so
  that the system is never left without an admin during demos.

### Last-admin guard

In addition to `is_protected`, demote/delete actions refuse to run if they
would leave the system with zero admins.

### Manager-specific limits

Managers can do almost everything an admin can do, but **cannot** affect
admin or manager rows in any way:

- can't edit, delete, promote, demote any staff;
- can't reset any user's password (admin-only);
- can't create manager accounts (admin-only).

## 4. Authentication

### Login

The login form has a single **Email or Student ID** field plus a password.

Resolution rule:
- if the input contains `@`, look up by `email` (lowercased);
- otherwise look up by `student_id`.

Failed lookups return a generic "Invalid email/student ID or password"
message — no user enumeration.

### Self-service password change (settings page)

Three required fields:
- `current_password`
- `new_password` (≥ 6 chars; must differ from current)
- `confirm_password` (must match `new_password`)

### Admin password reset

Admin opens the *Users* page → clicks the key icon → sets a temporary
password. Old password is never displayed or required. The user is
expected to change it from their own profile after first login.

## 5. Database / data model

### `users`

| Column                | Type        | Notes                                   |
|-----------------------|-------------|-----------------------------------------|
| id                    | INTEGER PK  |                                         |
| name                  | STRING      |                                         |
| student_id            | STRING      | unique; nullable for staff              |
| email                 | STRING      | unique                                  |
| password_hash         | STRING      | werkzeug PBKDF2                         |
| role                  | STRING      | `admin`, `manager`, or `student`        |
| is_sub_food_member    | BOOLEAN     | only meaningful for students            |
| **phone_number**      | STRING      | optional                                |
| **show_phone_number** | BOOLEAN     | privacy toggle                          |
| **is_protected**      | BOOLEAN     | system/developer accounts               |
| created_at            | DATETIME    |                                         |

The bold rows are **new in this iteration**; existing SQLite DBs are
migrated additively at startup (see `app._migrate_schema`).

### `food_items`

| Column                   | Type     | Notes                              |
|--------------------------|----------|------------------------------------|
| id                       | INTEGER PK |                                  |
| name                     | STRING (unique) |                             |
| category                 | STRING   | default `general`                  |
| low_stock_threshold      | INTEGER  | default 0                          |
| is_active                | BOOLEAN  | default true                       |
| warehouse_quantity       | INTEGER  | default 0                          |
| locker_quantity          | INTEGER  | default 0                          |
| **calories_per_serving** | INTEGER  | nullable; renders "Calories not listed" if unset |
| **serving_size**         | STRING   | nullable; free text e.g. "100g" or "1 cup" |
| created_at               | DATETIME |                                    |

Bold rows are **new in this iteration** and are added to existing
SQLite databases by `app._migrate_schema`.

### `inventory_logs`, `distributions`, `distribution_items`

Unchanged — see commit history for full schemas.

## 6. Sidebar navigation by role

The sidebar is intentionally short. The user's account/settings entry
point is **not** a separate nav item — it is the clickable **user chip**
at the bottom of the sidebar (see §6.1).

| Sidebar group     | Admin | Manager | Sub-food Student | Std. Student |
|-------------------|:-----:|:-------:|:----------------:|:------------:|
| Dashboard         |   ✅   |    ✅   |        ✅         |       ✅      |
| Users             |   ✅   |    ✅   |        —         |       —      |
| Food Items        |   ✅   |    ✅   |        —         |       —      |
| Warehouse         |   ✅   |    ✅   |        —         |       —      |
| Locker            |   ✅   |    ✅   |        —         |       —      |
| Transfer Stock    |   ✅   |    ✅   |        —         |       —      |
| Shareable Log     |   ✅   |    ✅   |        —         |       —      |
| Inventory Log     |   ✅   |    ✅   |        —         |       —      |
| Lounge Locker     |   —   |    —   |        ✅         |       —      |
| Coming-soon × 5   |   ✅   |    ✅   |        ✅         |       ✅      |
| **User chip → Settings** (footer) | ✅ | ✅ | ✅ | ✅ |
| Logout (footer)   |   ✅   |    ✅   |        ✅         |       ✅      |

### 6.1 Sidebar footer (clickable user chip)

The user chip shows the avatar (first initial), the user's name, and
either their student ID (students) or email (staff). The whole chip is a
single `<a>` element pointing to `/settings`:

- Hover state: subtle background + border so users see it's clickable.
- Active state: highlighted while the user is on `/settings`.
- A small gear icon on the right reinforces the affordance.
- Logout sits directly beneath it in the same footer area.

This pattern intentionally replaces the previous separate "My Profile"
sidebar item — keeping the navigation list focused on real modules.

## 6.5 Inventory log row (`inventory_logs`)

In addition to the existing fields, every new log row stores the
**post-action** stock snapshot for the affected food item:

| Column                | Type    | Notes                                  |
|-----------------------|---------|----------------------------------------|
| **warehouse_qty_after** | INTEGER | nullable for rows written before V1 polish |
| **locker_qty_after**    | INTEGER | nullable for rows written before V1 polish |

`_log_action(...)` reads these from the FoodItem after callers have
applied the mutation, which is why **callers must mutate the FoodItem
before calling `_log_action`**.

## 7. Food Items page UX

The page shows one row per food item with a clean layout:

- Food (name + serving size), Category, **Calories**, Threshold,
  Warehouse, Locker, Status, Actions.
- The **Warehouse** and **Locker** column headers — and each row's
  Warehouse / Locker quantity cell — are clickable shortcuts to the
  matching inventory page.
- Calories column shows `<n> kcal / serving` when set, or
  `Calories not listed` when null.
- Active/Inactive uses subtle pill badges.
- Items below threshold show a "Low locker stock" warning chip on the
  name cell.
- The Add and Edit modals expose Name, Category, **Calories per serving**
  (optional), **Serving size** (optional), Low-stock threshold, and
  the active/inactive toggle.
- The Add modal also captures **initial warehouse quantity** and
  **initial locker quantity** (both default to 0, must be ≥ 0). Each
  non-zero starting amount is recorded in the inventory history with
  the note `Initial stock on creation`.

### Warehouse / Locker bulk editing

- Both pages render every row as a single `<form>` with one numeric
  input per row (`name="qty_<food_id>"`).
- One **Save changes** button at the bottom posts the entire form to
  `/admin/warehouse/bulk-adjust` or `/admin/locker/bulk-adjust`.
- The handler validates each value as a non-negative integer, then
  applies only the rows whose value actually changed and writes one
  inventory-log entry per change.
- If nothing changed, the user sees a `No changes to save.` toast.
- A small live counter under the table shows how many rows will be
  saved before submission.
- The single-row endpoints (`/admin/warehouse/adjust` and
  `/admin/locker/adjust`) are kept for backward compatibility but the
  UI no longer surfaces them.

### Inventory History

- Filters: **date** (single calendar day) and **user** (dropdown of
  every user who has ever produced a log entry). They combine with AND.
- A *Clear* link resets to "all logs".
- Pagination: 10 rows per page (`PAGE_SIZE`). Renders « First, Previous,
  windowed page list with `…` ellipses around the current page, Next,
  » Last. Page links keep the current filter querystring.
- Columns: Time, User, Action, Food, Qty, From → To, **Wh after**,
  **Lk after**, Note.

## 8. Users page UX

The Users table has a **single Manage button per row**. Clicking it
opens a consolidated modal with the following sections, each rendered
only when the current viewer is allowed to use it:

1. **Profile information** — edit name, email, student ID (students),
   and substitute-food membership flag (students).
2. **Role** (admin only) — promote student → manager, or demote
   manager → student. Shown only when applicable.
3. **Substitute food program** — toggle membership for students.
4. **Password** (admin only) — set a temporary password. The current
   password is never shown.
5. **Danger zone** — delete the user, visually separated and behind a
   `confirm()` dialog. Hidden for self and for admins/managers when the
   viewer is a manager.

Other rules:

- **Protected** users (e.g. seeded admin) show no Manage button — only
  a `Protected` indicator. They can still edit themselves via Profile.
- The system always keeps at least one admin: deleting the last admin
  is refused.
- Managers can never affect admin or manager rows: those rows show no
  Manage button at all.

## 9. Student-facing rules

To keep the student experience friendly, students never see internal
classification labels:

- No role badge ("Student") in the sidebar user chip or profile card.
- No mention of "program subscription", "substitute food membership",
  "limited access", or any internal admin classification.
- Standard students see no food links anywhere; `/student/food` is
  reachable only by sub-food members and silently redirects others.
- Sub-food members see a *Lounge Locker* page (renamed from "Food
  Availability") with name, category, available quantity, calories per
  serving, and serving size when set.
- The student Settings page lists only name, student ID, email, phone
  number, and the edit/password forms — no role row, no membership row.

## 9.1 Settings page (`/settings`)

The Settings page is the single place where any user updates their own
account. It contains three sections:

1. **Profile information** — full name, email.
2. **Phone number / privacy** — optional phone number with a
   `show_phone_number` toggle.
3. **Password** — current + new + confirm password change.

For staff, an "Account details" side card additionally shows the role
badge and joined date for operational context. Students never see role
badges on this page.

The legacy `/profile` URL is preserved as a permanent (`301`) redirect
to `/settings`, so any existing links or bookmarks keep working.

## 9.2 Performance / data structure notes

This is a data structures class project. The few non-trivial routes
carry short comments naming the data structure they use and why:

- **Admin dashboard.** Counts and totals use SQL `COUNT()`/`SUM()`
  aggregates. The low-stock list pushes the comparison into the
  database (`locker_quantity <= low_stock_threshold`) instead of
  loading the whole food table and filtering in Python — analogous to
  preferring an indexed lookup over a linear scan.
- **Shareable Food Log — recording a pickup.** Form lines are folded
  into a `dict` (hash map) keyed by `food_id` so duplicate selections
  are summed in O(1) per entry. A second `dict` of `FoodItem` by id
  gives O(1) lookups while validating each line and applying the stock
  change.
- **Shareable Food Log — deleting a pickup.** Reversing a distribution
  uses the same id→FoodItem `dict` for O(1) restock lookups across all
  lines.
- **No work in render loops.** Templates iterate already-prepared lists
  and never re-query the database inside `{% for %}` blocks.

## 10. Future expansion

The remaining sidebar placeholder is a single "Coming soon" page:

| Module                        | New routes               | Status |
|-------------------------------|--------------------------|--------|
| Common Group Chat             | `/chat/...`              | Coming soon |
| Borrowing system              | `/borrowing/...`         | **Implemented in V3** |
| Cleaning sessions             | `/cleaning/...`          | **Implemented in V3** |

Each module follows the same blueprint pattern as the food module.

---

## 11. Version 2 features (implemented)

V2 ships two new modules on top of V1: **Announcements** and **Requests
to the International Department**.

### 11.1 Permission matrix

| Feature                                       | Admin | Manager | Sub-food Student | Std. Student |
|-----------------------------------------------|:-----:|:-------:|:----------------:|:------------:|
| View announcement feed (audience-filtered)    |   ✅   |    ✅   |        ✅         |       ✅      |
| Create / edit / delete announcement           |   ✅   |    ✅   |        —         |       —      |
| Toggle Draft ↔ Published                       |   ✅   |    ✅   |        —         |       —      |
| React to announcement (👍 ❤️ ✅ 👀)            |   ✅   |    ✅   |        ✅         |       ✅      |
| Submit a request                              |   —   |    —   |        ✅         |       ✅      |
| View own requests                             |   —   |    —   |        ✅         |       ✅      |
| View *all* requests, filter, search           |   ✅   |    ✅   |        —         |       —      |
| Respond to a request                          |   ✅   |    ✅   |        —         |       —      |
| Change request status                         |   ✅   |    ✅   |        —         |       —      |
| Delete a request                              |   ✅   |    ✅   |        —         |       —      |

### 11.2 Data model (additions)

Three new tables are auto-created via `db.create_all()` on first start —
no schema migration is required for fresh databases.

- **`announcements`** — `id`, `title`, `content`, `priority`
  (`normal`/`important`/`urgent`), `target_audience` (`everyone`/
  `all_students`/`sub_food_students`/`staff_only`), `is_published`,
  `created_at`, `updated_at`, `author_id` → `users.id`.
- **`announcement_reactions`** — `id`, `announcement_id`, `user_id`,
  `emoji` (one of 👍 ❤️ ✅ 👀), `created_at`. Unique constraint on
  `(announcement_id, user_id)` enforces one reaction per user per post
  (clicking the same emoji removes; clicking another swaps).
- **`support_requests`** — `id`, `student_id` → `users.id`, `category`
  (Food/Dormitory/Documents/School life/Health/Other), `title`,
  `description`, `status` (`submitted`/`in_review`/`resolved`/
  `rejected`), `admin_response`, `responded_by_id` → `users.id`,
  `responded_at`, `created_at`, `updated_at`.

### 11.3 Routes

**Announcements** (blueprint `announcements`, mount `/announcements`):

| Method | Path                  | Who    | Purpose                              |
|-------:|-----------------------|--------|--------------------------------------|
| GET    | `/`                   | All    | Staff list / student feed (by role)  |
| GET/POST | `/new`              | Staff  | Create announcement                  |
| GET/POST | `/<id>/edit`        | Staff  | Edit                                 |
| POST   | `/<id>/delete`        | Staff  | Delete                               |
| POST   | `/<id>/publish`       | Staff  | Toggle Draft ↔ Published              |
| POST   | `/<id>/react`         | All    | Add / swap / remove reaction         |

**Requests** (blueprint `requests`, file `requests_bp.py`, mount
`/requests`):

| Method | Path                  | Who      | Purpose                            |
|-------:|-----------------------|----------|------------------------------------|
| GET    | `/`                   | All      | Staff filtered list / own requests |
| GET/POST | `/new`              | Student  | Submit a request                   |
| GET    | `/<id>`               | Owner/Staff | Detail page                     |
| POST   | `/<id>/respond`       | Staff    | Add / update admin response        |
| POST   | `/<id>/status`        | Staff    | Change status                      |
| POST   | `/<id>/delete`        | Staff    | Delete                             |

### 11.4 Audience filter (SQL-side)

`Announcement.visible_to(user)` returns a SQLAlchemy query already
filtered to `is_published == True` and a `target_audience` `IN (...)`
list computed from the user's role and `is_sub_food_member` flag. The
student feed and the dashboard widget both call this — students never
load rows they aren't allowed to see.

### 11.5 Requests vs. Borrowing

These are *different* modules:

- **Requests** (V2, implemented) — free-form support tickets sent to
  the International Department (broken heater, lost ID card, transcript
  question, etc.).
- **Borrowing** (still "Coming soon") — checkout/return tracking for
  physical items kept at the lounge (umbrellas, adapters, tools, …).

### 11.6 Dashboard surfacing

- **Admin dashboard** — adds a *Recent announcements* card (3 most
  recent, with priority + Draft/Published badges, plus a "New" button)
  and an *Open requests* counter linking to the staff triage list.
- **Student dashboard** — adds a *Recent announcements* widget (3 most
  recent, audience-filtered) and removes Announcements / Requests from
  the "What's coming next" upcoming-features list.

### 11.7 Naming caveat

The requests blueprint is registered under the name `"requests"` so
`url_for("requests.list_view")` works from anywhere. The implementation
file is named **`requests_bp.py`** to avoid shadowing the popular
`requests` PyPI library if it is ever installed for HTTP work.

---

## 12. Version 3 features (implemented)

V3 ships two new modules on top of V2: **Borrowing** and **Cleaning
teams + sessions**.

### 12.1 Permission matrix

| Feature                                              | Admin | Manager | Sub-food Student | Std. Student |
|------------------------------------------------------|:-----:|:-------:|:----------------:|:------------:|
| View borrowable item catalog                         |   ✅   |    ✅   |        ✅         |       ✅      |
| Create / edit / activate borrowable items            |   ✅   |    ✅   |        —         |       —      |
| Submit borrow request                                |   —   |    —   |        ✅         |       ✅      |
| Approve / reject / mark returned                     |   ✅   |    ✅   |        —         |       —      |
| View own borrow requests                             |   —   |    —   |        ✅         |       ✅      |
| Create / edit cleaning teams                         |   ✅   |    ✅   |        —         |       —      |
| Create / edit / cancel sessions                      |   ✅   |    ✅   |        —         |       —      |
| Add / delete subtasks on a session                   |   ✅   |    ✅   |        —         |       —      |
| Tick own team's subtask as done (with note)          |   —   |    —   |        ✅¹        |       ✅¹     |
| Verify subtask / mark missed                         |   ✅   |    ✅   |        —         |       —      |

¹ Only for sessions whose team they belong to.

### 12.2 Data model (additions)

Six new tables, all auto-created via `db.create_all()` on first start —
no schema migration is needed.

- **`borrowable_items`** — `id`, `name` (unique), `category`,
  `description`, `total_quantity`, `available_quantity`, `is_active`,
  `created_at`. Stock invariant `0 ≤ available ≤ total` enforced
  in the route handlers.
- **`borrow_requests`** — `id`, `student_id` → `users.id`,
  `student_name` (snapshot), `item_id` → `borrowable_items.id`,
  `item_name` (snapshot), `quantity`, `borrow_until_date`,
  `status` (`pending`/`approved`/`rejected`/`returned`),
  `student_note`, `staff_note`, `handled_by_id` → `users.id`,
  `handled_by_name` (snapshot), `handled_at`, `created_at`,
  `updated_at`.
- **`cleaning_teams`** — `id`, `name` (unique), `description`,
  `is_active`, `created_at`.
- **`cleaning_team_members`** — composite-PK join table
  (`team_id`, `student_id`).
- **`cleaning_sessions`** — `id`, `team_id` → `cleaning_teams.id`,
  `team_name` (snapshot), `title`, `scheduled_date`, `start_time`,
  `end_time`, `location`, `status` (`scheduled`/`in_progress`/
  `completed`/`cancelled`), `notes`, `created_at`, `updated_at`.
- **`cleaning_tasks`** — `id`, `session_id` → `cleaning_sessions.id`,
  `description`, `assigned_student_id` → `users.id` (nullable),
  `student_name` (snapshot), `status` (`assigned`/`marked_done`/
  `verified_done`/`marked_missed`), `student_note`,
  `marked_done_at`, `verified_by_id` → `users.id`,
  `handled_by_name` (snapshot), `verified_at`, `created_at`,
  `updated_at`.

### 12.3 Routes

**Borrowing** (blueprint `borrowing`, mount `/borrowing`):

| Method | Path                              | Who      | Purpose                          |
|-------:|-----------------------------------|----------|----------------------------------|
| GET    | `/`                               | All      | Staff catalog/queue OR student feed |
| POST   | `/items/add`                      | Staff    | Create borrowable item           |
| POST   | `/items/<id>/edit`                | Staff    | Edit item                        |
| POST   | `/items/<id>/delete`              | Staff    | Delete (only if no requests)     |
| POST   | `/request`                        | Student  | Submit a borrow request          |
| POST   | `/requests/<id>/approve`          | Staff    | Approve (decrement available)    |
| POST   | `/requests/<id>/reject`           | Staff    | Reject (no stock change)         |
| POST   | `/requests/<id>/return`           | Staff    | Mark returned (restore stock)    |

**Cleaning** (blueprint `cleaning`, mount `/cleaning`):

| Method | Path                                  | Who    | Purpose                               |
|-------:|---------------------------------------|--------|---------------------------------------|
| GET    | `/`                                   | All    | Staff admin OR student team-feed      |
| POST   | `/teams/add`                          | Staff  | Create team + initial members         |
| POST   | `/teams/<id>/edit`                    | Staff  | Rename / sync members (set diff)      |
| POST   | `/teams/<id>/delete`                  | Staff  | Delete (cascades to sessions/tasks)   |
| POST   | `/sessions/add`                       | Staff  | Schedule session + parse subtasks     |
| POST   | `/sessions/<id>/edit`                 | Staff  | Edit session metadata                 |
| POST   | `/sessions/<id>/cancel`               | Staff  | Cancel a session                      |
| POST   | `/sessions/<id>/tasks/add`            | Staff  | Add a subtask                         |
| POST   | `/tasks/<id>/delete`                  | Staff  | Remove a subtask                      |
| POST   | `/tasks/<id>/mark-done`               | Member | Tick own team's subtask + note        |
| POST   | `/tasks/<id>/verify`                  | Staff  | Verify a subtask                      |
| POST   | `/tasks/<id>/missed`                  | Staff  | Mark a subtask as missed              |

### 12.4 Auto-completion rule

After every staff verification on a `cleaning_task`, the parent session
is checked: if **all** its tasks are `verified_done`, the session's
`status` flips to `completed` automatically — no manual "complete
session" button is needed.

### 12.5 Snapshot history

To keep history readable when names change or accounts are deleted,
both modules write the relevant display name into the row at action
time:

- `borrow_requests` stores `student_name`, `item_name`,
  `handled_by_name`.
- `cleaning_sessions` stores `team_name`.
- `cleaning_tasks` stores `student_name`, `handled_by_name`.

These are presentational only — the foreign keys remain authoritative.

### 12.6 Data structures used

- **Hash-set diff for team membership.** Editing a team computes
  `current_set` and `desired_set` of student IDs and applies the
  symmetric difference to `cleaning_team_members`, so a single edit
  costs O(|added| + |removed|) instead of O(|all|²).
- **Set membership for student access.** The student cleaning view
  uses an `in` test against the team's member set to decide whether
  to render *Mark done* — O(1) per lookup.
- **SQL aggregates for queue counters.** Pending borrow request and
  open cleaning task counts are computed with `COUNT(*)` queries
  rather than loading rows into Python.

---

## 13. Version 3.1 features (implemented)

V3.1 is a focused polish pass on top of V3 modules (no new top-level
features). It targets four pain points that surfaced in real use:

1. Staff couldn't send an announcement to a hand-picked subset of
   students.
2. Cleaning sessions only had a single date, so multi-day cleans had
   to be split into multiple records.
3. There was no formal staff sign-off step — a session was either
   "in progress" or "completed", with no way to postpone or to signal
   "team finished, awaiting verification".
4. Students could see only their own teams' names but had no way to
   look up team members' contact info, and there was no central page
   for external resources.

### 13.1 Targeted announcements (`specific_students`)

- New audience value `specific_students` added to
  `Announcement.AUDIENCES`.
- New table `announcement_recipients`:
  - `id` (PK), `announcement_id` (FK → `announcements.id`,
    cascade delete), `user_id` (FK → `users.id`).
  - Composite unique index on `(announcement_id, user_id)`.
- `Announcement.recipients` relationship is `lazy="selectin"` so the
  list endpoint doesn't N+1 when rendering recipient names.
- `Announcement.visible_to(user)` is extended with an OR-clause: a
  student sees the announcement if they are one of the recipients,
  on top of the existing audience checks.
- Staff form (`templates/announcements/form.html`) shows an inline
  multi-select student picker only when `specific_students` is the
  selected audience. A small JS toggle hides/shows the picker.
- Staff list (`templates/announcements/staff_list.html`) shows a
  *Sent to:* row with each recipient name as a small badge.

### 13.2 Cleaning sessions — date range + approval workflow

Schema additions on `cleaning_sessions`:

| Column                 | Type     | Default | Notes                                         |
|------------------------|----------|---------|-----------------------------------------------|
| `start_date`           | DATE     | —       | Required; replaces `scheduled_date` for UX.   |
| `end_date`             | DATE     | NULL    | Optional; same-day if NULL.                   |
| `postpone_count`       | INTEGER  | 0       | Increments on each postpone.                  |
| `postpone_note`        | TEXT     | NULL    | Most recent postpone reason.                  |
| `last_postponed_at`    | DATETIME | NULL    | Timestamp of most recent postpone.            |
| `approved_at`          | DATETIME | NULL    | Set when staff clicks Approve.                |
| `approved_by_name`     | STRING   | NULL    | Snapshot of approver's display name.          |

The legacy `scheduled_date` column is preserved. The startup
`_migrate_schema` ALTERs new columns onto existing SQLite databases
and backfills `start_date := scheduled_date` (and `end_date := NULL`).
Old rows with `status = 'completed'` are migrated to
`status = 'approved'`.

`CleaningSession.STATUSES`:

| status        | meaning                                              |
|---------------|------------------------------------------------------|
| `scheduled`   | Newly created.                                       |
| `marked_done` | Auto-flip: every subtask is done, awaiting approval. |
| `approved`    | Staff clicked Approve; remaining tasks auto-verified.|
| `postponed`   | Staff pushed it to a new date range.                 |
| `cancelled`   | Manually cancelled.                                  |

`ACTIVE_STATUSES = ('scheduled', 'postponed')` — the only states in
which students may mark subtasks done. (`marked_done` is awaiting
approval and locks further student edits unless staff add a new
subtask, which reopens the session.)

### 13.3 Cleaning team detail page

- New route `GET /cleaning/teams/<team_id>/members`.
- Authorization:
  - Staff (admin or manager) can view any team.
  - A student can view a team only if there's a row in
    `cleaning_team_members` with their `user_id` for that team. All
    other team views return HTTP 403.
- The page lists each member's `student_name`, `student_id`, and
  `phone_number` — the phone number is suppressed if the member's
  `show_phone_number` flag is `false`. This re-uses the existing V1
  privacy toggle so contact info honours each student's setting.

### 13.4 Resources page

- New blueprint `resources` mounted at `/resources`. The page is
  protected by `@login_required` only — every signed-in role can see
  it.
- Renders two hardcoded "card" links. Each anchor uses
  `target="_blank" rel="noopener"` so the lounge dashboard stays open.
- Sidebar gets a *Resources* entry under the *Lounge Life* group for
  both staff and students.

### 13.5 Sidebar reorganization

The sidebar (`templates/base.html`) now has three labelled groups:

- **Communication** — Announcements, Requests.
- **Lounge Life** — Borrowing, Cleaning, Resources, plus food/locker
  links.
- **Coming Soon** — Common Group Chat (only remaining stub).

Staff sidebar items previously labelled *Manage Borrowing* / *Manage
Cleaning* are shortened to *Borrowing* / *Cleaning* — the staff role
context already implies management, and matching labels for staff and
students keeps the UI consistent.

### 13.6 Cleaning routes (V3.1 additions)

| Method | Path                                  | Who       | Purpose                                                                  |
|-------:|---------------------------------------|-----------|--------------------------------------------------------------------------|
| GET    | `/teams/<id>/members`                 | Staff/Mem | Render the team's member list (privacy-aware phone numbers).             |
| POST   | `/sessions/<id>/postpone`             | Staff     | Push session to new `start_date`/`end_date`, increment `postpone_count`. |
| POST   | `/sessions/<id>/approve`              | Staff     | Auto-verify remaining tasks, set `approved`, snapshot approver.          |

The pre-existing `/sessions/add` and `/sessions/<id>/edit` routes now
accept `start_date` and `end_date` instead of a single
`scheduled_date`, with server-side validation that
`end_date >= start_date`.

### 13.7 Manual test summary

All flows below were exercised against a freshly migrated SQLite DB
and the `Start application` workflow.

- **Targeted announcement** — admin posts to *Specific students*
  including only S001 and S003. S002 does not see it; S001 and S003
  do; staff list shows *Sent to: Student One, Student Three*.
- **Cleaning approve** — admin clicks *Approve* on an active session
  with mixed verified/non-verified subtasks. All subtasks flip to
  *Verified*; status becomes *Approved* with `approved_by_name`
  rendered under the date.
- **Cleaning postpone** — admin clicks *Postpone* with a new end
  date and a note. Status becomes *Postponed*, `postpone_count`
  becomes 1, the note appears under the date row, and the team can
  still mark subtasks done.
- **Team detail (staff)** — admin opens
  `/cleaning/teams/<id>/members` for an arbitrary team and sees every
  member's name, student ID, and phone (where the member opted in).
- **Team detail (privacy)** — a student that is **not** a member of
  the team gets HTTP 403 from the same URL.
- **Resources** — both an admin and a student can open `/resources/`;
  both cards render and open in a new browser tab.
