# International Lounge

A web app to centralize daily-life systems for international students.
**Version 1** focuses on the **substitute food management module**.

---

## Project purpose

International students rely on shared programs (substitute food, cleaning
rotations, borrowed equipment, announcements) that today are tracked in
spreadsheets and group chats. The International Lounge gradually replaces
those spreadsheets with a single, role-based dashboard.

## Version 1 scope

Only the **substitute food management module** is implemented in V1.
The project structure already accommodates future modules.

### Current features

#### For everyone (admin & student)
- Email + password login & student registration
- Personal **profile page** (update name, email, password)
- Role-based access control (admin / student)

#### Admin features
- Dashboard with summary cards and low-stock alerts
- Student management (add / edit / delete / toggle membership)
- Food item catalog (add / edit / delete / activate)
- Warehouse inventory (add stock, safe quantity adjustment)
- Locker inventory (safe quantity adjustment)
- Stock transfer (warehouse → locker, with validation)
- **Shareable Food Log** — record student pickups (multiple foods grouped
  into one row), filter by date, copy as plain text, export to CSV
- Inventory history (every change is logged)
- Sidebar placeholders for upcoming modules

#### Student features
- Read-only dashboard with available locker food
- Personal profile editing

### Planned future features (placeholders shown in the sidebar)
- Borrowing system
- Requests to International Department
- Announcements
- Common Group Chat
- Cleaning Sessions

## User roles

| Role      | Capabilities                                                                 |
|-----------|------------------------------------------------------------------------------|
| `admin`   | Full access: students, food items, warehouse, locker, transfers, distributions, logs |
| `student` | Read-only dashboard, profile editing only                                    |

Students cannot:
- change their own role,
- change their `is_sub_food_member` flag,
- access or modify any inventory data.

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

To run locally:

```bash
pip install flask flask-sqlalchemy flask-login werkzeug
python app.py
# then open http://localhost:5000
```

## Folder structure

```
.
├── app.py                  # Flask application factory + entry point
├── models.py               # SQLAlchemy models (User, FoodItem, InventoryLog,
│                           #                    Distribution, DistributionItem)
├── auth.py                 # Login / register / logout
├── admin.py                # Admin blueprint (all admin pages & actions)
├── student.py              # Student blueprint (read-only dashboard)
├── profile.py              # Personal profile (name, email, password)
├── seed.py                 # Demo data seeder (runs once at startup)
├── instance/
│   └── app.db              # SQLite database (created at runtime)
├── static/
│   └── css/style.css       # App stylesheet
├── templates/
│   ├── base.html           # Layout with sidebar / topbar / flash messages
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   ├── coming_soon.html    # Placeholder for upcoming modules
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── students.html
│   │   ├── food_items.html
│   │   ├── warehouse.html
│   │   ├── locker.html
│   │   ├── transfer.html
│   │   ├── distributions.html  # Shareable Food Log
│   │   └── logs.html
│   └── student/
│       └── dashboard.html
├── docs/
│   └── project-spec.md
└── README.md
```
