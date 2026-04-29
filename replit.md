# International Lounge — Replit notes

## Stack
- **Backend & frontend**: Flask 3 (Jinja2 server-rendered templates)
- **Database**: SQLite via Flask-SQLAlchemy (`instance/app.db`)
- **Auth**: Flask-Login + Werkzeug password hashing
- **UI**: Bootstrap 5 + Bootstrap Icons + custom `static/css/style.css`

## How it runs
- Workflow `Start application` → `python app.py`
- Listens on host `0.0.0.0`, port `5000` (Replit webview)
- DB is created and seeded on first start (see `seed.py`)
- Additive schema migration (`app._migrate_schema`) runs on every start so
  existing SQLite databases pick up new columns without losing data.

## Layout
```
app.py            entry / app factory + coming-soon route + schema migration
models.py         User (with phone/privacy/protection flags), FoodItem, ...
auth.py           login (by email or student_id) / register / logout
admin.py          admin & manager blueprint (mounted at /admin)
student.py        student blueprint (general dashboard + food page)
profile.py        profile + dedicated password change form
seed.py           demo data
templates/        Jinja templates
static/css/       stylesheet
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

## Recent changes
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

## Secrets
`SESSION_SECRET` env var is used for Flask sessions; falls back to a
dev-only string when unset.
