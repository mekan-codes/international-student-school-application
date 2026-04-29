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

#### For everyone
- **Login by email OR student ID** + password.
- Personal **profile page** — update name, email, phone number, phone
  privacy, and password (separate, safer change-password flow).

#### Admin features
- Dashboard with summary cards and low-stock alerts.
- **User management** with role badges, role filter, edit, delete,
  promote/demote, and password reset.
- Food item catalog (add / edit / delete / activate). Column headers for
  *Warehouse* and *Locker* link directly to those pages.
- Warehouse inventory (add stock, safe quantity adjustment).
- Locker inventory (safe quantity adjustment).
- Stock transfer (warehouse → locker, with validation).
- **Shareable Food Log** — record student pickups, filter by date, copy as
  plain text, export to CSV.
- Inventory history (every change is logged).

#### Manager features
- Same operational surface as admin: user/food/inventory/transfer/log/
  distributions pages.
- Cannot promote, demote, edit, delete, or reset the password of any admin
  or other manager.
- Cannot create managers (admin-only) — managers can only add students.

#### Student features
- **Sub-food member students** see a Food Availability page in addition to
  their dashboard and profile.
- **Standard (non-member) students** see only a neutral general dashboard
  and profile — no mention of the substitute food program.

### Planned future features (placeholders shown in the sidebar)
- Borrowing system
- Requests to International Department
- Announcements
- Common Group Chat
- Cleaning Sessions

## User roles

| Role      | Can do                                                                           |
|-----------|----------------------------------------------------------------------------------|
| `admin`   | Everything: manage users, change roles, reset passwords, full inventory access.  |
| `manager` | Manage students, food, warehouse, locker, transfers, distributions, logs.        |
| `student` | Read-only personal dashboard + profile; food page only if a sub-food member.     |

### Manager limits
- Managers cannot edit, delete, promote, or demote admins or other managers.
- Managers cannot reset any user's password (admin-only).
- Managers cannot create manager accounts (admin-only).

### Account protection
- Some accounts may be marked `is_protected` (e.g. the seeded developer
  admin). Protected accounts cannot be modified, demoted, or deleted by
  anyone other than themselves through their own profile page.
- The system always keeps at least one admin: demoting/deleting the last
  admin is refused.

### Password rules
- **Self-service change:** users provide current password, new password,
  and a matching confirmation; the new password must differ from the
  current one and be at least 6 characters.
- **Admin reset:** admin sets a temporary password — the existing password
  is never displayed and never required. The user is expected to change it
  on next login through their profile.

### Phone number privacy
- Each user can store a phone number in their profile.
- A `show_phone_number` toggle controls visibility — when off, the number
  is stored but not displayed on directory views or other profiles.

## Demo accounts (seeded automatically)

| Role    | Email                | Password    | Notes                            |
|---------|----------------------|-------------|----------------------------------|
| Admin   | admin@school.com     | admin123    | Protected — cannot be deleted    |
| Manager | manager@school.com   | manager123  | Operational access, no role mgmt |
| Student | student1@school.com  | student123  | Substitute food member (S001)    |
| Student | student2@school.com  | student123  | NOT a member (S002)              |
| Student | student3@school.com  | student123  | Substitute food member (S003)    |

You can sign in with **either** the email **or** the student ID
(e.g. `S001`).

## How to run the project

The app is configured to run automatically inside Replit.

1. Open the project on Replit.
2. The **Start application** workflow runs `python app.py` and binds to
   port `5000` (host `0.0.0.0`) — the Replit preview opens automatically.
3. The SQLite database (`instance/app.db`) is created and seeded on first
   run. Existing databases are auto-migrated to add the new
   `phone_number`, `show_phone_number`, and `is_protected` columns.
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
├── app.py                  # Flask app factory + entry point + schema migration
├── models.py               # SQLAlchemy models
├── auth.py                 # Login (by email or student_id) / register / logout
├── admin.py                # Admin & manager blueprint
├── student.py              # Student blueprint (general + food)
├── profile.py              # Personal profile + password change
├── seed.py                 # Demo data seeder
├── instance/
│   └── app.db              # SQLite database (created at runtime)
├── static/
│   └── css/style.css
├── templates/
│   ├── base.html           # Layout + role-aware sidebar
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   ├── coming_soon.html
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── users.html       # was students.html
│   │   ├── food_items.html
│   │   ├── warehouse.html
│   │   ├── locker.html
│   │   ├── transfer.html
│   │   ├── distributions.html
│   │   └── logs.html
│   └── student/
│       ├── dashboard.html   # general dashboard (no food info for non-members)
│       └── food.html        # locker food (members only)
├── docs/
│   └── project-spec.md
└── README.md
```

## Testing the four flows

Use the seeded accounts:

1. **Admin** (`admin@school.com` / `admin123`)
   - Open *Users* → see all roles. Promote a student to manager,
     demote them back, reset a password, delete a user. Try to delete
     yourself or the protected admin → blocked.
   - Use every inventory page; record a pickup on Shareable Food Log.

2. **Manager** (`manager@school.com` / `manager123`)
   - Open *Users* → can edit students only; admin/manager rows show
     no edit/promote/reset/delete actions. Adding a user only allows
     the *Student* role.
   - Full access to food, warehouse, locker, transfer, distributions, logs.

3. **Sub-food student** (`student1@school.com` / `student123`)
   - Sidebar shows *My Dashboard*, *Food Availability*, *My Profile*,
     and the coming-soon items.
   - Profile lets you update name, email, phone, privacy, password.

4. **Standard student** (`student2@school.com` / `student123`)
   - Sidebar shows *My Dashboard*, *My Profile*, and the coming-soon items.
   - **No food links anywhere.** Direct visit to `/student/food` redirects
     back with a flash.

You can also log any student in by their student ID — e.g.
`S002` / `student123`.
