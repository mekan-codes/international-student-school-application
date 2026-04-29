# International Student School Support App

A web app to centralize daily-life systems for international students.
**Version 1** focuses on the **substitute food management module**.

---

## Project purpose

International students at the school depend on shared programs (substitute
food, cleaning rotations, borrowed equipment) that today are tracked in
spreadsheets and group chats. This app gradually replaces those spreadsheets
with a single, role-based dashboard.

## Version 1 scope

Only the **substitute food management module** is implemented in V1.
The project structure already accommodates future modules.

### Implemented features
- Email + password login & student registration
- Role-based access control (admin / student)
- Admin dashboard with summary cards and low-stock alerts
- Student management (add / edit / delete / toggle membership)
- Food item catalog (add / edit / delete / activate)
- Warehouse inventory page (add stock, adjust)
- Locker inventory page (adjust)
- Stock transfer page (warehouse → locker, with validation)
- Inventory log / history page (every change is recorded)
- Read-only student dashboard with available locker food
- Seeded demo data on first run

### Not in V1 (future modules)
- Cleaning schedule
- Borrowing / shared resources
- Suggestion board

## User roles

| Role      | Capabilities                                                                |
|-----------|-----------------------------------------------------------------------------|
| `admin`   | Full access: manage students, food items, warehouse, locker, transfers, logs |
| `student` | Read-only dashboard: see membership status and available locker food         |

## Demo accounts (seeded automatically)

| Role    | Email                | Password    | Notes                          |
|---------|----------------------|-------------|--------------------------------|
| Admin   | admin@school.com     | admin123    | Full admin access              |
| Student | student1@school.com  | student123  | Substitute food member         |
| Student | student2@school.com  | student123  | NOT a member                   |
| Student | student3@school.com  | student123  | Substitute food member         |

Sample food items (with starting stock):

| Food         | Warehouse | Locker | Low-stock threshold |
|--------------|-----------|--------|---------------------|
| chicken mayo | 20        | 5      | 2                   |
| rice         | 30        | 8      | 3                   |
| noodles      | 15        | 2      | 3 (already low!)    |

## How to run the project

The app is configured to run automatically inside Replit.

1. Open the project on Replit.
2. The **Start application** workflow runs `python app.py` and binds to
   port `5000` (host `0.0.0.0`) — the Replit preview opens automatically.
3. The SQLite database (`instance/app.db`) is created and seeded on first run.
4. Log in with one of the demo accounts above.

To run locally outside Replit:

```bash
pip install flask flask-sqlalchemy flask-login werkzeug
python app.py
# then open http://localhost:5000
```

## Folder structure

```
.
├── app.py                  # Flask application factory + entry point
├── models.py               # SQLAlchemy models (User, FoodItem, InventoryLog)
├── auth.py                 # Login / register / logout blueprint
├── admin.py                # Admin blueprint (all admin pages & actions)
├── student.py              # Student blueprint (read-only dashboard)
├── seed.py                 # Demo data seeder (runs once at startup)
├── instance/
│   └── app.db              # SQLite database (created at runtime)
├── static/
│   └── css/style.css       # App stylesheet
├── templates/
│   ├── base.html           # Layout with sidebar / topbar / flash messages
│   ├── login.html
│   ├── register.html
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── students.html
│   │   ├── food_items.html
│   │   ├── warehouse.html
│   │   ├── locker.html
│   │   ├── transfer.html
│   │   └── logs.html
│   └── student/
│       └── dashboard.html
├── docs/
│   └── project-spec.md     # Detailed spec & expansion plan
└── README.md
```

## Future features (planned modules)

- **Cleaning schedule** — rotating chore assignments and check-offs.
- **Borrowing / shared resources** — track who borrowed what and when.
- **Suggestion board** — students post ideas, admins triage them.

The blueprint structure (`auth.py`, `admin.py`, `student.py`) is set up so
each future module can be added as its own blueprint without touching the
existing code.
