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
- Personal **Settings page** (`/settings`) — update name, email, phone
  number, phone privacy, and password (separate, safer change-password
  flow). Reachable by clicking the **user chip in the sidebar footer**;
  no separate "My Profile" item clutters the sidebar.
  - The legacy `/profile` URL stays valid as a permanent redirect to
    `/settings` so old links and bookmarks still work.

#### Admin features
- Dashboard with summary cards and low-stock alerts.
- **User management** — every user row has a single **Manage** button
  that opens a consolidated panel with edit profile, change role,
  toggle substitute-food membership, reset password, and a clearly
  separated *Danger zone* delete action with confirmation.
- Food item catalog (add / edit / delete / activate) with **calories per
  serving**, optional **serving size**, and **initial warehouse / locker
  quantities** captured directly in the create form. *Warehouse* and
  *Locker* column headers — and the per-row quantity cells — are
  clickable shortcuts to those pages.
- **Bulk inventory editing** on the Warehouse and Locker pages — every
  row is a number input wrapped by one form; admins/managers edit any
  number of rows, then click *Save changes* once to persist them all
  (one inventory log entry per changed row).
- Stock transfer (warehouse → locker, with validation).
- **Shareable Food Log** — record student pickups, filter by date, copy as
  plain text, export to CSV.
- **Inventory history** with date + user filters and pagination
  (10 entries per page, with first/previous/next/last and a windowed
  page list). Each row records remaining warehouse and locker
  quantities at the time of the action.

#### Manager features
- Same operational surface as admin: user/food/inventory/transfer/log/
  distributions pages.
- Cannot promote, demote, edit, delete, or reset the password of any admin
  or other manager.
- Cannot create managers (admin-only) — managers can only add students.

#### Student features
- All students see a clean general dashboard and profile. **Internal
  classifications** (role label, "program subscription", "substitute
  food membership", "limited access") are never shown to students.
- **Sub-food member students** also see a *Lounge Locker* page listing
  what's currently available, including calories per serving and serving
  size when set ("Calories not listed" otherwise).
- **Standard (non-member) students** see only the general dashboard and
  profile — no food links anywhere in the sidebar.
- The student Settings page shows only the basics: name, student ID,
  email, phone number (if added), plus profile-edit and password-change
  forms.

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

### Phone number privacy & formatting
- Each user can store a phone number in their Settings page.
- The phone field uses an international **country-code picker** (powered
  by the `intl-tel-input` library, loaded from a CDN — no Python
  dependency added). The number is formatted as you type and stored in
  clean international format (e.g. `+82 10 1234 5678`).
- A `show_phone_number` toggle controls visibility — when off, the number
  is stored but not displayed on directory views or other profiles.

### Auto-dismissing notifications
- Success / info messages auto-dismiss after **5 seconds**.
- Warning / error messages auto-dismiss after **7 seconds**.
- Users can still close any message manually with the × button.

## V1 polish notes (latest pass)

- **Sidebar navigation cleanup.** The standalone "My Profile" link was
  removed from every sidebar (admin, manager, student). Instead the
  bottom user chip — avatar, name, and student ID/email — is now itself a
  clickable link that goes to `/settings`, with hover and active styling
  so users understand it is interactive. Logout stays right beneath it.
- **Settings replaces the Profile page.** The route is now `/settings`
  and the page is titled *Settings*. It groups Profile information,
  Phone number/privacy, and Password change into one place. `/profile`
  still works as a `301` redirect to `/settings` for any saved links.
- **Student-facing labels.** Students never see internal classification
  wording (`role`, "program subscription", "substitute food membership",
  "limited access", etc.) anywhere. Standard students see no food links
  at all; sub-food members see the locker without internal membership
  wording.
- **Performance / data structures.** The admin dashboard pushes its
  low-stock filter into SQL instead of loading every food row and
  filtering in Python. The Shareable Food Log builds a `dict` (hash
  map) by food id for O(1) lookups while validating each line of a
  pickup, and another `dict` when reversing one for the locker restock.
  Each helper carries a short comment that names the data structure
  and why it's used (this is a data-structures class project).
- **"Homepage" wording.** The first sidebar link (and dashboard page
  title) is called **Homepage** for both staff and students — the route
  paths (`/admin/` and `/student/`) are unchanged so internal references
  still work.
- **Future modules.** Borrowing, Requests to International Department,
  Announcements, Common Group Chat, and Cleaning Sessions remain in
  the sidebar as **Coming soon** placeholders only — none of them are
  implemented in V1.

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
   run. Existing databases are auto-migrated to add the user columns
   (`phone_number`, `show_phone_number`, `is_protected`) and the new
   food columns (`calories_per_serving`, `serving_size`).
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
├── profile.py              # Settings page + password change (legacy
│                           #   /profile redirects to /settings)
├── seed.py                 # Demo data seeder
├── instance/
│   └── app.db              # SQLite database (created at runtime)
├── static/
│   └── css/style.css
├── templates/
│   ├── base.html           # Layout + role-aware sidebar
│   ├── login.html
│   ├── register.html
│   ├── settings.html        # was profile.html (renamed in V1 polish)
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
   - Sidebar starts with **Homepage**, then *Manage* (Users, Food Items),
     *Inventory* (Warehouse, Locker, Transfer Stock, Shareable Food Log,
     Inventory History), and *Coming soon* (5 placeholders).
   - Open *Users* → every row has one **Manage** button. Try each
     section: edit profile, promote to manager, toggle membership,
     reset password, delete (in the *Danger zone*).
   - On *Food Items*, click *Add Food Item* and fill in **calories per
     serving**, **serving size**, plus **initial warehouse / locker
     quantities**. Save → the new row shows those quantities and *two*
     entries appear in the inventory history.
   - On *Warehouse* (or *Locker*): change a few of the row inputs, then
     click **Save changes** once. A success toast lists each row's
     before→after value and auto-dismisses after ~5 seconds. Save again
     without changes → "No changes to save."
   - On *Inventory History*: filter by date and/or user, walk through
     the *Previous / 1 2 3 / Next* pagination, then click *Clear*.
   - Visit `/profile` directly → 301 redirect to `/settings`.

2. **Manager** (`manager@school.com` / `manager123`)
   - Sidebar matches the admin layout (same items, same clickable user
     chip → Settings). No "My Profile" item.
   - Open *Users* → only student rows show a **Manage** button.
     Admin and manager rows display *Protected* / *—* and have no
     edit/promote/reset/delete actions.
   - The Manage panel for a student shows profile edit and substitute-
     food toggle, but no role-change or password-reset sections (admin
     only). The Add User form only allows the *Student* role.
   - Full access to food, warehouse, locker, transfer, distributions,
     logs.

3. **Sub-food student** (`student1@school.com` / `student123`)
   - Sidebar shows *Homepage*, *Lounge Locker*, and the coming-soon
     items — no "My Profile" item. The user chip at the bottom is the
     way into *Settings*. No role label appears anywhere.
   - *Lounge Locker* lists items in stock with calories per serving and
     serving size when set, or "Calories not listed" otherwise. There
     is no internal "membership" wording on the page.
   - On *Settings*, click the country flag to pick (e.g.) Korea (+82),
     type a number — it formats as you type. Save → the page header
     toast disappears on its own after a few seconds.

4. **Standard student** (`student2@school.com` / `student123`)
   - Sidebar shows *Homepage* and the coming-soon items only — no food
     link, no "My Profile" link. The user chip at the bottom is the
     entry to *Settings*.
   - Direct visit to `/student/food` silently redirects back to the
     dashboard.
   - Dashboard never mentions roles, programs, membership, or limits;
     it only welcomes the student and lists upcoming features.

You can also log any student in by their student ID — e.g.
`S002` / `student123`.
