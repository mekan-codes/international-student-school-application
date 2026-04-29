# International Student School Support App — Replit notes

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
app.py            entry / app factory
models.py         User, FoodItem, InventoryLog
auth.py           login / register / logout
admin.py          admin blueprint (mounted at /admin)
student.py        student blueprint (mounted at /student)
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
  so an `inventory_logs` row is created for every change.
- Quantity inputs are validated server-side: integers, non-negative,
  transfers cannot exceed available warehouse stock.
- Admin pages use the `@admin_required` decorator; the student dashboard
  blocks admins so the two views remain semantically separate.

## Secrets
`SESSION_SECRET` env var is used for Flask sessions; falls back to a
dev-only string when unset.
