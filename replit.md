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

## Layout
```
app.py            entry / app factory + coming-soon route
models.py         User, FoodItem, InventoryLog, Distribution, DistributionItem
auth.py           login / register / logout
admin.py          admin blueprint (mounted at /admin)
student.py        student blueprint (mounted at /student)
profile.py        profile blueprint (mounted at /profile)
seed.py           demo data
templates/        Jinja templates
static/css/       stylesheet
docs/             project spec
```

## Demo accounts
- Admin: `admin@school.com` / `admin123`
- Student: `student1@school.com` / `student123` (member)
- Student: `student2@school.com` / `student123` (non-member)
- Student: `student3@school.com` / `student123` (member)

## Conventions
- Add new feature modules as **Flask blueprints** under their own file.
- Inventory mutations always go through helper `_log_action(...)` in `admin.py`
  so an `inventory_logs` row is created for every change — including pickups
  recorded via the Shareable Food Log.
- Quantity inputs are validated server-side: integers, non-negative,
  transfers and pickups cannot exceed available stock.
- Admin pages use the `@admin_required` decorator. The student dashboard
  blocks admins so the two views stay semantically separate.
- The profile route only mutates `name`, `email`, and `password_hash`;
  `role`, `is_sub_food_member`, and `student_id` are off-limits by design.
- Bootstrap modals are placed **outside** `<tbody>` tags — putting them
  inside causes the browser to silently relocate them and break the trigger.

## Recent changes
- Renamed the app to **International Lounge** in all surfaces.
- Fixed silent food-item edit bug (modals were inside `<tbody>`).
- Added `/profile` for self-service name/email/password edits.
- Added Distribution + DistributionItem models for the Shareable Food Log.
- Added sidebar placeholders for upcoming modules.
- Removed the "limited access" warning from the student dashboard.

## Secrets
`SESSION_SECRET` env var is used for Flask sessions; falls back to a
dev-only string when unset.
