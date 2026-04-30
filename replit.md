# International Lounge — Replit notes

## Stack
- **Backend & frontend**: Flask 3 (Jinja2 server-rendered templates)
- **Database**: SQLite via Flask-SQLAlchemy (`instance/app.db`)
- **Auth**: Flask-Login + Werkzeug password hashing
- **UI**: Bootstrap 5 + Bootstrap Icons + custom `static/css/style.css`

## How it runs
- Workflow `Start application` → `gunicorn --bind 0.0.0.0:5000 --reuse-port --reload app:app`
- Production deploy → `gunicorn --bind=0.0.0.0:5000 --reuse-port app:app`
- Listens on host `0.0.0.0`, port `5000` (Replit webview)
- DB is created and seeded on first start (see `seed.py`)
- Additive schema migration (`app._migrate_schema`) runs on every start so
  existing SQLite databases pick up new columns without losing data.

## Layout
```
app.py            entry / app factory + coming-soon route + schema migration
models.py         User, FoodItem, ... + V2: Announcement,
                  AnnouncementReaction, SupportRequest
                  + V3: BorrowableItem, BorrowRequest,
                        CleaningTeam, CleaningTeamMember,
                        CleaningSession, CleaningTask
                  + V3.1: AnnouncementRecipient (targeted DMs)
auth.py           login (by email or student_id) / register / logout
admin.py          admin & manager blueprint (mounted at /admin)
student.py        student blueprint (general dashboard + food page)
profile.py        /settings (profile + password); /profile → /settings
announcements.py  V2 — staff CRUD + student feed + emoji reactions
                  V3.1 — adds `specific_students` audience that
                  routes via AnnouncementRecipient join rows
requests_bp.py    V2 — student submit/list-own/detail + staff filtered
                  list/respond/status/delete. File is *_bp.py so it
                  doesn't shadow the `requests` PyPI library; the
                  blueprint name is "requests".
borrowing.py      V3 — borrowable item catalog + request approve/reject/return
cleaning.py       V3 — cleaning teams + sessions + subtask checklist
                  V3.1 — date-range scheduling, postpone & approve,
                  team-detail page with phone-privacy aware members
resources.py      V3.1 — Resources page (curated external links;
                  visible to all signed-in users)
seed.py           demo data
templates/        Jinja templates (announcements/, requests/,
                  borrowing/, cleaning/, plus V3.1 resources.html
                  and cleaning/_team_members.html)
static/css/       stylesheet (V3 adds task-list, member-pill,
                  borrow-item-card, cleaning-session-card classes;
                  V3.1 adds .resource-card / .resource-icon /
                  .team-badge-link)
docs/             project spec
```

## Demo accounts
- Admin (protected): `admin@school.com` / `admin123`
- Manager: `manager@school.com` / `manager123`
- Sub-food student: `student1@school.com` (or `S001`) / `student123`
- Non-member student: `student2@school.com` (or `S002`) / `student123`
- Sub-food student: `student3@school.com` (or `S003`) / `student123`

You can sign in with the email or the student ID.

## Roles
- **admin** — full access, can promote/demote/reset password.
- **manager** — operational access (users, food, inventory, distributions,
  logs); cannot touch admin/manager rows or reset passwords.
- **student** — personal dashboard + profile. Food page only when
  `is_sub_food_member`.

## Conventions
- Add new feature modules as **Flask blueprints** under their own file.
- Inventory mutations always go through `_log_action(...)` so an
  `inventory_logs` row is created for every change.
- Quantity inputs are validated server-side: integers, non-negative,
  transfers and pickups cannot exceed available stock.
- Protected users (`is_protected = true`) cannot be modified, demoted,
  or deleted by anyone other than themselves through `/profile`.
- The system always keeps at least one admin (`_admin_count()` guard).
- Bootstrap modals are placed **outside** `<tbody>` tags.
- `current_user.is_staff` includes admin AND manager. Use that for nav and
  permission gating; use `is_admin` for admin-only paths.

## V2 modules (Apr 2026)

### Announcements
- Models: `Announcement` + `AnnouncementReaction`.
  - `Announcement.AUDIENCES` = everyone / all_students /
    sub_food_students / staff_only.
  - `Announcement.PRIORITIES` = normal / important / urgent.
  - `Announcement.visible_to(user)` returns a SQLAlchemy query with
    audience + `is_published` filtering pushed into SQL — students
    never load rows they shouldn't see.
  - `AnnouncementReaction.EMOJIS` = ('👍', '❤️', '✅', '👀'); unique
    constraint on `(announcement_id, user_id)` enforces one reaction
    per user per post.
- Blueprint `announcements` mounted at `/announcements`.
  - `/` — `list_view` dispatches by role (staff list vs student feed).
  - `/new`, `/<id>/edit`, `/<id>/delete`, `/<id>/publish` — staff only.
  - `/<id>/react` — students/staff; toggles, swaps, or removes the
    user's reaction in one POST.

### Requests to International Department
- Model: `SupportRequest` with categories Food / Dormitory /
  Documents / School life / Health / Other and statuses submitted /
  in_review / resolved / rejected (`status_label`/`status_badge_class`
  helpers, `has_response` property).
- Blueprint `requests` (file `requests_bp.py` to avoid shadowing the
  `requests` PyPI library) mounted at `/requests`.
  - `/` — staff get a filtered list (status / category / student /
    text search, all SQL-side); students get only their own.
  - `/new` — students submit.
  - `/<id>` — student sees their own (403 otherwise); staff see any.
  - `/<id>/respond`, `/<id>/status`, `/<id>/delete` — staff only.

### Dashboard surfacing
- Admin dashboard: 3 most recent announcements + open-requests
  counter (statuses submitted + in_review).
- Student dashboard: 3 most recent announcements visible to that
  student (via `Announcement.visible_to(current_user)`); after V3
  the dashboard also has Borrowing / Cleaning info tiles, and the
  upcoming-features list only shows Common Group Chat.

### Sidebar
- "Communication" section (Announcements + Requests) appears for
  staff and students under their respective panels; the old
  Coming-soon placeholders for those two were removed but
  `/coming-soon/<slug>` still resolves any unknown slug for
  back-compat.

## V3 modules (Apr 2026)

### Borrowing (`borrowing.py`, mount `/borrowing`)
- Models: `BorrowableItem`, `BorrowRequest`.
  - `BorrowableItem.available_quantity` is the source of truth; the
    invariant `0 ≤ available ≤ total` is enforced in the routes.
  - `BorrowRequest.STATUSES` = pending / approved / rejected /
    returned. Snapshots `student_name`, `item_name`,
    `handled_by_name` are stored so history survives renames.
- Routes:
  - `/` — staff catalog + queue, students see active items + own
    requests.
  - `/items/add`, `/items/<id>/edit`, `/items/<id>/delete` — staff.
  - `/request` — student submits.
  - `/requests/<id>/approve|reject|return` — staff.

### Cleaning (`cleaning.py`, mount `/cleaning`)
- Models: `CleaningTeam`, `CleaningTeamMember` (composite-PK join),
  `CleaningSession`, `CleaningTask`.
  - Subtask flow: assigned → marked_done (member) → verified_done
    (staff). Staff may also mark missed.
  - When all tasks in a session are verified, the session
    auto-completes (in the `verify_task` handler).
  - Team member sync uses a hash-set diff (current vs. desired set
    of student IDs) so updates are O(|added|+|removed|).
- Routes:
  - `/` — staff admin (teams + sessions) OR student feed (only
    sessions for teams the student belongs to).
  - `/teams/add|<id>/edit|<id>/delete` — staff.
  - `/sessions/add|<id>/edit|<id>/cancel` — staff.
  - `/sessions/<id>/tasks/add`, `/tasks/<id>/delete` — staff.
  - `/tasks/<id>/mark-done` — team member only.
  - `/tasks/<id>/verify`, `/tasks/<id>/missed` — staff.

### Sidebar (V3)
- Borrowing & Cleaning replaced their Coming-soon stubs with real
  links for staff *and* students. Common Group Chat is the only
  remaining placeholder.

## V3.1 modules (Apr 2026)

### Targeted announcements (`specific_students` audience)
- New `AnnouncementRecipient` join table — `(announcement_id,
  user_id)` unique. The `Announcement.recipients` relationship
  is `lazy="selectin"` and cascades on delete.
- `Announcement.AUDIENCES` now includes `specific_students`.
  `Announcement.visible_to(user)` adds an OR-clause: the user
  sees the announcement if they're a chosen recipient.
- Staff form (`templates/announcements/form.html`) shows a
  multi-select student picker only when "Specific students" is
  picked; tiny JS toggles the picker visibility on change.
- Staff list shows a "Sent to:" row with each recipient name as
  a small badge (`recipient_names` model helper).

### Cleaning sessions — date range + approval workflow
- `CleaningSession` gets `start_date`, `end_date`,
  `postpone_count`, `postpone_note`, `last_postponed_at`,
  `approved_at`, `approved_by_name`. The legacy
  `scheduled_date` column is preserved for backwards
  compatibility; the additive migration in `app._migrate_schema`
  backfills the new columns from it.
- `CleaningSession.STATUSES` =
  scheduled / marked_done / approved / postponed / cancelled.
  `ACTIVE_STATUSES` = ('scheduled', 'postponed') — the only
  states students can act on.
- Flow: students mark subtasks done → when every task is
  `marked_done` or `verified_done` the session auto-flips to
  `marked_done` (awaiting approval) via `_maybe_team_done`.
  Staff click **Approve** (`/sessions/<id>/approve`), which
  verifies any remaining subtasks, sets `status='approved'`,
  and stamps `approved_by_name` + `approved_at`.
- Staff can **Postpone** (`/sessions/<id>/postpone`) — accepts
  new `start_date`/`end_date` (+ optional note), increments
  `postpone_count`, sets status to `postponed`. Reopens the
  session for the team.
- Old `'completed'` rows are migrated to `'approved'` on
  startup.
- `date_range_label` renders "Apr 30, 2026" for single-day
  sessions, "Apr 30 – May 2, 2026" for ranges.

### Cleaning teams — clickable detail page
- New route `/cleaning/teams/<id>/members` renders a small read-
  only list (name, student ID, phone if `show_phone_number`).
- Authorization: staff see any team; a student may only view a
  team they're a member of (otherwise 403). This keeps other
  teams' rosters and phone numbers private.
- Both staff and student cleaning views link the team name to
  this page via the `.team-badge-link` style.

### Resources page (`resources.py`, mount `/resources`)
- Two hardcoded "card" links rendered on a single page; opens in
  a new tab (`target="_blank" rel="noopener"`). Visible to every
  signed-in user (no role gating beyond `@login_required`).
- Sidebar gets a Resources entry under Lounge Life for both
  staff and students.

### Sidebar reorganization (V3.1)
- Sidebar now groups items into three labelled sections:
  **Communication** (Announcements, Requests),
  **Lounge Life** (Borrowing, Cleaning, Resources, food/locker
  links), **Coming Soon** (Common Group Chat only).
- Staff "Manage Borrowing" / "Manage Cleaning" labels were
  shortened to **Borrowing** / **Cleaning** since the role
  context already implies management.

## Manual test summary (V3.1)

Routes smoke-tested while logged in (admin + S001):
- `GET /cleaning/` — admin board renders date-range form,
  Approve / Postpone / Cancel buttons appear on active sessions,
  postpone history shows under each session.
- `GET /cleaning/teams/2/members` — admin sees full list with
  student IDs & phone numbers (where `show_phone_number=True`).
- `GET /cleaning/teams/2/members` as **non-member** student →
  HTTP 403 (privacy guard works).
- `GET /cleaning/` as student S001 — sees only their teams,
  team badge links to the members page, date range label
  rendered, "Mark done" available while status is
  `scheduled` or `postponed`.
- `GET /announcements/new` — "Specific students" option
  appears, recipient picker toggles via JS on selection.
- `GET /announcements/` (staff) — recipient names render as
  badges under any specific-students post.
- `GET /resources/` — two cards render and open in new tab;
  reachable from sidebar by both staff and students.

## Recent changes
- **Phone formatting** in Settings now uses `intl-tel-input` (CDN, no
  Python dep) — country dropdown, format-as-you-type, stored in
  international format. A hidden field carries the canonical value.
- **"My Dashboard" → "Homepage"** for both staff and students. Routes
  unchanged.
- **Auto-dismiss flash messages**: success/info 5 s, warning/danger 7 s.
  Manual close still works.
- **Bulk warehouse / locker editing**: one Save changes button replaces
  per-row Set buttons; only changed rows are persisted; "No changes to
  save" when nothing differs; one inventory log entry per change.
- **Initial quantities on food creation**: `initial_warehouse_quantity`
  and `initial_locker_quantity` fields, validated non-negative,
  recorded as inventory log entries.
- **Inventory History** has date + user filters, 10 entries per page,
  and standard pagination (« Previous 1 2 … 9 Next »). Each row shows
  the post-action warehouse and locker quantities (new
  `warehouse_qty_after` / `locker_qty_after` columns; old rows show —).
- **V1 polish pass**: removed standalone "My Profile" sidebar item;
  the bottom user chip is now a clickable link to `/settings` with
  hover/active styling. Profile page renamed to **Settings**;
  `/profile` is a 301 redirect to `/settings`. Dashboard low-stock
  filter pushed into SQL. Distribution flow uses dict (hash map) by
  food id for O(1) lookups, with comments explaining the choice.
- Users page redesigned: **single Manage button per row** opens a
  consolidated modal (profile edit, role change, membership toggle,
  password reset, separated *Danger zone* delete).
- Food items now have **calories_per_serving** and **serving_size**
  columns (nullable). Schema migration adds them automatically.
- Food Items page shows a **Calories** column and per-row clickable
  Warehouse/Locker quantity cells.
- Sub-food student page renamed to **Lounge Locker** and now displays
  calories per serving + serving size; falls back to "Calories not
  listed" when unset.
- Students never see internal classification labels (role, "program
  subscription", "substitute food membership", etc.) anywhere.
- Student profile shows only name, student ID, email, phone — no role
  or membership rows.
- Login by **email or student ID** (single `identifier` field).
- Added **manager** role with operational access but no role/password mgmt.
- Added **phone_number** + **show_phone_number** privacy toggle.
- Added **is_protected** flag for developer accounts.
- Added **admin password reset** action (temporary password).
- Profile has a **separate password change form** (current/new/confirm).
- Renamed `/admin/students` → `/admin/users` with role filter.
- Additive SQLite migration on every start.

## V3.2 polish (Apr 2026)

### Editable Resources
- `Resource` DB model replaces hardcoded list in `resources.py`.
- Staff (admin/manager) can add/edit/delete resource cards via modal UI.
- Students see only `is_active=True` resources.
- Two placeholder cards seeded on first-run.

### Cleaning admin UI cleanup
- Per-task action buttons replaced with a single **Manage** button/modal per task.
- Manage modal: Verify, Mark Missed, Reset to Assigned, Delete task.
- Session actions reorganised into a clean action row with collapse panels for Postpone/Edit.
- New `POST /tasks/<id>/reset` route to reset a task back to `assigned`.

### Student cleaning UX fix
- `assigned` → shows "Mark done" form.
- `marked_done` → shows "Waiting for staff verification" text only (no "Update" button).
- `verified_done` → shows "Verified by [name]" text only.
- `missed` → shows "Marked missed by staff" text only.
- Approved sessions show a banner; no student action buttons.

### Users page polish
- Table simplified to: Name, Student ID, Email, Status, Actions.
- Summary cards above table: Total / Students / Managers / Sub-food members.
- Badges: "No" → "Standard", "Member" → "Sub-food".
- `counts` dict passed from route (SQL aggregates, O(1) template access).

### Sidebar reorganisation
- Resources moved under **Communication** for both staff and students.
- Staff "Manage" section renamed "Management".
- Student "Lounge Locker" moved inside **Lounge Life** section.

## V3.3 — Substitute Food Locker & Stability Audit (Apr 2026)

### Rename: Lounge Locker → Substitute Food Locker
- Student sidebar label, page title, and card header updated.
- Internal route/function names unchanged (`/student/food`, `food()`).

### Student self-pickup
- `POST /student/food` — `@member_required` (sub-food members only).
- Validates qty ≥ 1 and no overdraw against `locker_quantity`.
- Creates one grouped `Distribution` + one `DistributionItem` per food.
- Creates one `InventoryLog` entry per food (action_type = distribute_to_student).
- `source_type = "student_self_pickup"` on the Distribution record.
- JS confirmation dialog before submission; "Take selected food" button disabled until qty > 0.
- Success flash: "You took Chicken Mayo × 1, Noodles × 1."

### Recently taken by me
- Last 5 `Distribution` rows for the current student shown below the form.
- Empty state: "No pickup history yet."

### Source label on admin Shareable Food Log
- New `source_type` column on the `distributions` table.
- Admin table shows "Staff recorded" (grey) vs "Student pickup" (teal) badge.
- Additive migration in `_migrate_schema()` — runs automatically on startup.

### Schema change
| Table | Column added |
|---|---|
| `distributions` | `source_type VARCHAR(30) DEFAULT 'staff_recorded'` |

### Stability audit
- All permission decorators verified: `@staff_required`, `@admin_required`, `@member_required`.
- Last-admin guard, protected-account guard, and overdraw guards all confirmed present.
- No bugs found.

## Secrets
`SESSION_SECRET` env var is used for Flask sessions; falls back to a
dev-only string when unset.
