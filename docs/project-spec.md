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

### Self-service password change (profile page)

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

| Sidebar group  | Admin | Manager | Sub-food Student | Std. Student |
|----------------|:-----:|:-------:|:----------------:|:------------:|
| Dashboard      |   ✅   |    ✅   |        ✅         |       ✅      |
| Users          |   ✅   |    ✅   |        —         |       —      |
| Food Items     |   ✅   |    ✅   |        —         |       —      |
| Warehouse      |   ✅   |    ✅   |        —         |       —      |
| Locker         |   ✅   |    ✅   |        —         |       —      |
| Transfer Stock |   ✅   |    ✅   |        —         |       —      |
| Shareable Log  |   ✅   |    ✅   |        —         |       —      |
| Inventory Log  |   ✅   |    ✅   |        —         |       —      |
| Lounge Locker  |   —   |    —   |        ✅         |       —      |
| My Profile     |   ✅   |    ✅   |        ✅         |       ✅      |
| Coming-soon × 5|   ✅   |    ✅   |        ✅         |       ✅      |

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
- The student profile lists only name, student ID, email, phone number,
  and the edit/password forms — no role row, no membership row.

## 10. Future expansion

Sidebar placeholders for the following modules; they all currently render
a "Coming soon" page.

| Module                        | New routes               |
|-------------------------------|--------------------------|
| Borrowing system              | `/borrowing/...`         |
| Requests to International Dept| `/requests/...`          |
| Announcements                 | `/announcements/...`     |
| Common Group Chat             | `/chat/...`              |
| Cleaning Sessions             | `/cleaning/...`          |

Each module follows the same blueprint pattern as the food module.
