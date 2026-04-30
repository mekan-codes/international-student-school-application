# International Lounge

A web app to centralize daily-life systems for international students.
**Version 4** adds a **Lounge Board** — a community feed of posts,
comments and reactions — and removes the old Group Chat placeholder.
This sits on top of the V3 borrowing + cleaning modules, the V2
announcements/requests modules, and the V1 substitute-food module.

---

## Project purpose

International students rely on shared programs (substitute food, cleaning
rotations, borrowed equipment, announcements) that today are tracked in
spreadsheets, ad-hoc chat groups and hallway notes. The International
Lounge gradually replaces those spreadsheets with a single, role-based
dashboard, and offers a built-in **Lounge Board** for community
conversation in place of external chat groups.

## Version 4 scope

Implemented modules:
- **Substitute food management** (V1, unchanged).
- **Announcements** (V2 + V3.1) — V3.1 adds a *Specific students*
  audience that lets staff pick exactly which students see a post.
- **Requests to International Department** (V2, unchanged).
- **Borrowing system** (V3) — staff curate a catalog of borrowable
  items with stock counts; students request items with a return-by
  date; staff approve/reject and mark returned. Stock invariant
  `0 ≤ available ≤ total` enforced server-side.
- **Cleaning teams & sessions** (V3 + V3.1) — staff create teams of
  students and schedule sessions over a **date range** (start +
  optional end date) with a checklist of subtasks. New approval
  workflow: when every subtask is finished the session auto-flips to
  *Awaiting approval*; staff click **Approve** to close it out, or
  **Postpone** to push it to a new date range. Team names are now
  clickable — staff see every team's roster, students see only the
  rosters of teams they belong to.
- **Resources page** (V3.1) — a single page of curated external
  links available to every signed-in user, reachable from the
  sidebar.
- **Lounge Board** (V4) — a community feed where every signed-in
  user can publish posts, comment, and react with 👍 ❤️ 👀.
  Admin and manager users can additionally **pin**, **lock**, or
  delete any post or comment. Replaces the previous *Group Chat*
  coming-soon placeholder.

There are no remaining "Coming soon" placeholders.

### V3 module: Borrowing

- **Catalog management** at `/borrowing/` (staff): add, edit, activate
  /deactivate items with name, category, description, total quantity.
  *Available* is derived from outstanding approved requests, never
  edited by hand — an item's *available* equals *total* minus the
  number currently borrowed.
- **Student request flow** — students see only active items with
  `available > 0`, submit a quantity and an optional return-by date.
- **Staff queue** — pending requests go to a triage list. Staff
  *approve* (decrements `available`), *reject* (no stock change), or
  mark *returned* (restores `available`) with optional staff notes.
- **History snapshot** — each request stores `student_name`,
  `item_name`, and `handled_by_name` snapshots so renames or deletes
  don't rewrite the borrowing history.

### V3 module: Cleaning teams & sessions

- **Teams** — staff create named cleaning teams at `/cleaning/` and
  pick member students from a checkbox picker. Membership is updated
  by hash-set diff so duplicate adds and removes are O(1) per student.
  Team names are clickable: staff see every team's roster (name,
  student ID, and phone where the student opted in), students may only
  open teams they're a member of (other rosters return 403).
- **Sessions** — staff schedule a session for a team with a **start
  date**, optional **end date**, optional start/end time, location,
  and a newline-separated list of subtasks. Each subtask becomes a row
  in `cleaning_tasks`.
- **Subtask checklist** —
  - Status flow: `assigned` → `marked_done` (by team member, optional
    note) → `verified_done` (by staff). Staff may also `marked_missed`
    a task that wasn't completed.
- **Session lifecycle** (V3.1):
  - `scheduled` — newly created.
  - `marked_done` — auto-flipped when the team finishes every subtask
    (awaiting staff approval).
  - `approved` — staff clicked **Approve**; remaining subtasks are
    auto-verified and `approved_by_name` + `approved_at` are stored.
  - `postponed` — staff clicked **Postpone**, supplied a new date
    range and optional note. The session is reopened for the team and
    `postpone_count` is incremented.
  - `cancelled` — visually muted, ignores further actions.
- **Snapshots** — `student_name`, `team_name`, `handled_by_name`, and
  `approved_by_name` are stored on the row so deleting a student or
  renaming a team does not rewrite cleaning history.

### V2 module: Announcements

- **Staff (admin/manager) CRUD** at `/announcements/` — create, edit,
  delete, and toggle Draft/Published with a single click.
- **Audiences** — `everyone`, `all_students`, `sub_food_students`,
  `staff_only`, and (V3.1) `specific_students` — when picked, a
  multi-select student picker appears so staff can choose exactly
  which students see the post. Audience filtering runs in SQL via
  `Announcement.visible_to(current_user)`, so students never receive
  rows they shouldn't see.
- **Priorities** — `normal`, `important`, `urgent` (urgent posts get a
  highlighted card on the student feed).
- **Reactions** — students can react with 👍 ❤️ ✅ 👀. Each user has
  exactly one reaction per announcement (clicking the same emoji
  removes it; clicking another swaps it).
- **Recent announcements widget** appears on both the admin and student
  dashboards (3 most recent visible to the viewer).

### V2 module: Requests to International Department

- **Students** submit a request at `/requests/new` (category, title,
  description), see only their own list at `/requests/`, and view their
  own detail page including any staff response.
- **Categories**: Food, Dormitory, Documents, School life, Health,
  Other.
- **Statuses**: submitted, in review, resolved, rejected (color-coded
  badges).
- **Staff** see all requests at `/requests/` with **filters** for
  status, category, student, and free-text search (all SQL-side).
  Staff can write a response, change status, and delete a request.
- The admin dashboard surfaces an **Open requests** counter linking
  straight to the staff triage list.

> Requests vs. Borrowing — these are different: *Requests* are free-form
> support tickets to the International Department. *Borrowing* (V3)
> manages physical items checked out from the lounge.

### V4 module: Lounge Board

A community feed for everyone signed in — students and staff alike —
that replaces the old *Group Chat* coming-soon placeholder.

- **Posts** at `/lounge-board/`. Every signed-in user can publish a
  post with a title, a category (General, Questions, Lost & Found,
  Events, Food, Dormitory, Other) and free-form body text. The feed
  paginates 10 posts per page; pinned posts always appear first, then
  newest-first by creation time.
- **Filters** — a single search box matches in title or body, and a
  category dropdown narrows the feed. Both filters survive pagination.
- **Comments** — every post has a comment thread shown on the detail
  page. Comments are author-editable and author-deletable just like
  posts.
- **Reactions** — three emoji reactions (👍 ❤️ 👀) with a per-user
  toggle/swap rule: each user can hold at most one reaction per post.
  Tapping the same emoji again removes it; tapping a different one
  swaps the reaction. A `UNIQUE(post_id, user_id)` constraint enforces
  this at the database level.
- **Moderation** — admins and managers can additionally **pin**,
  **lock**, or delete any post or comment. Locked posts visually lock
  down the comment form for normal students (staff can still post a
  comment to the locked thread, e.g. an "official close" note).
- **History snapshots** — every post and comment stores an
  `author_name` snapshot at write time (same pattern as Announcements
  and Requests) so renames or account deletions don't rewrite history.

## Version 1 scope (still active)

The **substitute food management module** is unchanged from V1.

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

### Planned future features
- _None — V4 ships the Lounge Board and removes the last placeholder._

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
- **Future modules.** All originally planned modules are implemented:
  Announcements, Requests, Borrowing, Cleaning, Resources, and the new
  V4 Lounge Board (replacing the Group Chat placeholder).

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
├── models.py               # SQLAlchemy models (V2 adds Announcement,
│                           #   AnnouncementReaction, SupportRequest)
├── auth.py                 # Login (by email or student_id) / register / logout
├── admin.py                # Admin & manager blueprint
├── student.py              # Student blueprint (general + food)
├── profile.py              # Settings page + password change (legacy
│                           #   /profile redirects to /settings)
├── announcements.py        # V2: Announcements blueprint (staff CRUD,
│                           #   student feed, emoji reactions)
├── requests_bp.py          # V2: Requests blueprint (named "requests";
│                           #   file is *_bp.py to avoid shadowing the
│                           #   `requests` PyPI library)
├── borrowing.py            # V3: Borrowing blueprint (item catalog,
│                           #   request approve/reject/return)
├── cleaning.py             # V3: Cleaning blueprint (teams, sessions,
│                           #   subtask checklist + verification)
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
│   │   ├── dashboard.html   # V2: + recent announcements + open req count
│   │   ├── users.html       # was students.html
│   │   ├── food_items.html
│   │   ├── warehouse.html
│   │   ├── locker.html
│   │   ├── transfer.html
│   │   ├── distributions.html
│   │   └── logs.html
│   ├── student/
│   │   ├── dashboard.html   # V2: + recent announcements widget
│   │   └── food.html        # locker food (members only)
│   ├── announcements/       # V2
│   │   ├── staff_list.html
│   │   ├── student_list.html
│   │   └── form.html
│   ├── requests/            # V2
│   │   ├── student_list.html
│   │   ├── student_new.html
│   │   ├── admin_list.html
│   │   └── detail.html
│   ├── borrowing/           # V3
│   │   ├── student.html
│   │   └── admin.html
│   └── cleaning/            # V3
│       ├── student.html
│       └── admin.html
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
   - Sidebar shows *Homepage*, the **Communication** section
     (Announcements, Requests, Resources, **Lounge Board**), the
     **Lounge Life** section (Borrowing, Cleaning, Lounge Locker) — no
     "My Profile" item. The user chip at the bottom is the way into
     *Settings*. No role label appears anywhere.
   - *Lounge Locker* lists items in stock with calories per serving and
     serving size when set, or "Calories not listed" otherwise. There
     is no internal "membership" wording on the page.
   - On *Settings*, click the country flag to pick (e.g.) Korea (+82),
     type a number — it formats as you type. Save → the page header
     toast disappears on its own after a few seconds.

4. **Standard student** (`student2@school.com` / `student123`)
   - Sidebar shows *Homepage*, the **Communication** section
     (Announcements, Requests, Resources, **Lounge Board**) and the
     **Lounge Life** section (Borrowing, Cleaning) — no food link, no
     "My Profile" link. The user chip at the bottom is the entry to
     *Settings*.
   - Direct visit to `/student/food` silently redirects back to the
     dashboard.
   - Dashboard never mentions roles, programs, membership, or limits;
     it shows the welcome card, the **Recent announcements** widget,
     and quick-link tiles for the Lounge Board and Resources.

You can also log any student in by their student ID — e.g.
`S002` / `student123`.

### V2 testing flows

5. **Announcements (admin)** — sign in as admin, open *Announcements*,
   click *New*. Try each priority and audience. Save as Draft → it
   shows a *Draft* badge and is invisible to students. Click *Publish*
   on the row → badge flips to *Published*. Edit / Delete on the same
   row. The admin dashboard's *Recent announcements* card refreshes.

6. **Announcements (student)** — sign in as `student2` (standard,
   non-member). The feed shows everything published to *everyone* and
   *all_students*, **never** *staff_only* or *sub_food_students*. Sign
   in as `student1` (sub-food member) — the feed additionally shows
   *sub_food_students* posts. React to a post with 👍 → counter goes
   up; click 👍 again → it goes back down; click ❤️ → reaction swaps
   (one reaction per user per announcement).

7. **Requests (student)** — sign in as `student2`, open *Requests*,
   click *New request*, pick a category, submit. The list shows only
   your own requests. Visit any other student's request URL → 403.

8. **Requests (staff)** — sign in as admin, open *Requests*. Filter
   by status, category, student, or text. Open a request → write a
   response, change the status, or delete it. The student sees the
   response and updated status on their own detail page.

### V3 testing flows

9. **Borrowing (staff)** — sign in as admin, open *Borrowing*. Click
   *Add item*, enter a name, category, total quantity, and a note —
   save. Active items appear in the catalog with `available / total`.
   Edit any item to change the total or deactivate it. Pending
   requests show in the *Requests* queue with **Approve** / **Reject**
   buttons; approved requests show **Mark returned**.

10. **Borrowing (student)** — sign in as `student1`. The page lists
    only items with `available > 0`. Submit a request with quantity
    and an optional return-by date. The request shows under *My
    requests* with status **Pending**. Once a staffer approves, the
    badge flips to **Approved**; once they mark it returned, to
    **Returned**.

11. **Cleaning (staff)** — sign in as admin, open *Cleaning*. Create
    a *Team* (name + member checkboxes). Then create a *Session* for
    that team with a **start date** (and optional **end date**),
    optional time/location, and a newline-separated list of subtasks.
    Each line becomes a checklist row. Use **Verify** on each subtask
    as students complete them — when all are verified the session
    badge flips to **Awaiting approval** automatically (V3.1).
    Use **Mark missed** to record an undone task. *Cancel session*
    mutes the card visually.

12. **Cleaning (student)** — sign in as `student1`. The page shows
    only sessions for teams the student belongs to, with the date
    range printed for each session. Each subtask is a checkbox-style
    row with **Mark done** (and an optional note). Verified rows turn
    green; missed rows turn red. Click any team badge to open the
    members list. Students who are not on any team see an empty-state
    message.

### V3.1 testing flows

13. **Approve & Postpone a cleaning session (staff)** — sign in as
    admin, open *Cleaning*. On any active session click **Approve**:
    every remaining subtask flips to *Verified*, the badge becomes
    *Approved*, and the session shows "Approved by Admin · ⟨date⟩".
    On another active session click **Postpone**, supply a new start
    date (and optional end date + note), and submit. The badge flips
    to *Postponed*, the postpone history appears under the session,
    and the team can keep marking subtasks done.

14. **Specific-student announcement (staff)** — sign in as admin, open
    *Announcements* → *New*. Choose audience **Specific students** —
    a multi-select picker of every student appears. Pick `student1`
    and `student3`, set a title/body, save & publish. The list view
    shows a *Sent to: Student One, Student Three* row under the post.
    Sign in as `student2` (not picked) — the post does **not** appear
    in their feed; sign in as `student1` — it does.

15. **Clickable cleaning team (student)** — sign in as `student1`,
    open *Cleaning*, and click the team badge at the top or beside
    any session. The team detail page lists every member's name and
    student ID, plus phone numbers only for those members who set
    *Show phone number* in their settings. Try the same URL as
    `student2` (a non-member) — you get a 403, proving the privacy
    guard.

16. **Resources page** — open *Resources* from the sidebar (works for
    both staff and student accounts). The two cards open in a new
    tab so the lounge dashboard stays where you left it.
