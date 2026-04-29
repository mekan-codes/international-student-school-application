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

### `food_items`, `inventory_logs`, `distributions`, `distribution_items`

Unchanged from the previous spec — see commit history for full schemas.

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
| Food Availability |  —  |    —   |        ✅         |       —      |
| My Profile     |   ✅   |    ✅   |        ✅         |       ✅      |
| Coming-soon × 5|   ✅   |    ✅   |        ✅         |       ✅      |

## 7. Food Items page UX

The page shows one row per food item with a clean layout:

- Name, Category, Threshold, Warehouse, Locker, Status, Actions.
- The **Warehouse** and **Locker** column headers are clickable
  shortcut links that open the corresponding inventory pages.
- Active/Inactive uses subtle pill badges.
- Items below threshold show a "Low locker stock" warning chip on the
  name cell.

## 8. Future expansion

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
