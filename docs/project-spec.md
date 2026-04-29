# Project Specification — International Lounge

## 1. Problem statement

International students at the school rely on shared, manually-tracked
systems: a substitute-food program with a small warehouse and a daily-access
locker, a cleaning rotation, borrowed equipment, and an informal suggestion
channel. These are currently managed across spreadsheets, chat groups, and
hallway notes — leading to lost stock, missed cleaning shifts, and unclear
membership status.

The International Lounge centralizes these systems into a single
role-based dashboard.

## 2. Version 1 features

V1 implements only the **substitute food management module**.

| Feature                                | Admin | Student |
|----------------------------------------|:-----:|:-------:|
| Login / logout                         |   ✅   |    ✅    |
| Public student registration            |   —   |    ✅    |
| Personal profile editing               |   ✅   |    ✅    |
| Admin dashboard with summary cards     |   ✅   |    —    |
| Student management (CRUD)              |   ✅   |    —    |
| Toggle substitute-food membership      |   ✅   |    —    |
| Food item catalog (CRUD + active flag) |   ✅   |    —    |
| Add stock to warehouse                 |   ✅   |    —    |
| Adjust warehouse / locker quantities   |   ✅   |    —    |
| Transfer stock warehouse → locker      |   ✅   |    —    |
| Record student food pickups            |   ✅   |    —    |
| Shareable Food Log (text + CSV)        |   ✅   |    —    |
| Low-stock alerts on dashboard          |   ✅   |    —    |
| Inventory log / history                |   ✅   |    —    |
| Student dashboard                      |   —   |    ✅    |
| View available locker food (read)      |   —   |    ✅    |

## 3. User roles

- **Admin** — created by another admin. Full access. Demo: `admin@school.com / admin123`.
- **Student** — created by self-registration or by an admin. Read-only access
  to inventory; can edit only their own name, email, and password.

Role enforcement is implemented in two layers:
- Each admin route is decorated with `@admin_required`.
- The student dashboard route blocks admins (so the views remain semantically distinct).
- The profile route is `@login_required` and only mutates `name`, `email`,
  and `password_hash` — `role`, `is_sub_food_member`, and `student_id`
  cannot be changed by the user themselves.

## 4. Database / data model

### `users`
| Column                | Type        | Notes                                   |
|-----------------------|-------------|-----------------------------------------|
| id                    | INTEGER PK  |                                         |
| name                  | STRING      |                                         |
| student_id            | STRING      | unique; null for admins                 |
| email                 | STRING      | unique                                  |
| password_hash         | STRING      | werkzeug PBKDF2                         |
| role                  | STRING      | `admin` or `student`                    |
| is_sub_food_member    | BOOLEAN     | only meaningful for students            |
| created_at            | DATETIME    |                                         |

### `food_items`
| Column                | Type        | Notes                                   |
|-----------------------|-------------|-----------------------------------------|
| id                    | INTEGER PK  |                                         |
| name                  | STRING      | unique                                  |
| category              | STRING      |                                         |
| low_stock_threshold   | INTEGER     | locker_quantity ≤ threshold ⇒ low      |
| is_active             | BOOLEAN     |                                         |
| created_at            | DATETIME    |                                         |
| warehouse_quantity    | INTEGER     | non-negative                            |
| locker_quantity       | INTEGER     | non-negative                            |

### `inventory_logs`
Every quantity change writes a row here, regardless of cause.

| Column                  | Type        | Notes                                                                                       |
|-------------------------|-------------|---------------------------------------------------------------------------------------------|
| log_id                  | INTEGER PK  |                                                                                             |
| food_id                 | INTEGER FK  | → `food_items.id`                                                                           |
| food_name               | STRING      | denormalized                                                                                |
| action_type             | STRING      | `add_to_warehouse`, `transfer_to_locker`, `adjust_warehouse`, `adjust_locker`, `distribute_to_student` |
| quantity                | INTEGER     | positive for adds/transfers/distributions; signed delta for adjustments                     |
| source_location         | STRING      | nullable                                                                                    |
| destination_location    | STRING      | nullable                                                                                    |
| performed_by_user_id    | INTEGER FK  | → `users.id`                                                                                |
| performed_by_user_name  | STRING      | denormalized                                                                                |
| timestamp               | DATETIME    |                                                                                             |
| note                    | STRING      | nullable                                                                                    |

### `distributions`  (Shareable Food Log)
A single pickup event for one student covering one or more foods.

| Column                  | Type        | Notes                       |
|-------------------------|-------------|-----------------------------|
| id                      | INTEGER PK  |                             |
| student_id              | INTEGER FK  | → `users.id`                |
| student_name            | STRING      | denormalized                |
| performed_by_user_id    | INTEGER FK  | → `users.id` (admin)        |
| performed_by_user_name  | STRING      | denormalized                |
| timestamp               | DATETIME    |                             |
| note                    | STRING      | nullable                    |

### `distribution_items`
The per-food line items of a distribution (snapshot of stock after pickup).

| Column                  | Type        | Notes                                |
|-------------------------|-------------|--------------------------------------|
| id                      | INTEGER PK  |                                      |
| distribution_id         | INTEGER FK  | → `distributions.id` (cascade delete)|
| food_id                 | INTEGER FK  | → `food_items.id`                    |
| food_name               | STRING      | denormalized                         |
| quantity                | INTEGER     | positive                             |
| locker_qty_after        | INTEGER     | snapshot for the shareable log       |
| warehouse_qty_after     | INTEGER     | snapshot for the shareable log       |

## 5. Main workflows

### 5.1 Admin onboarding
1. Admin logs in (seeded account or one created by another admin).
2. Lands on the dashboard with summary cards and low-stock alerts.

### 5.2 Stocking & distribution
1. Admin creates a food item (name, category, threshold).
2. Admin adds a quantity to the **warehouse** (`add_to_warehouse`).
3. Admin transfers a quantity from warehouse → **locker**
   (`transfer_to_locker`); transfer cannot exceed warehouse stock.
4. Admin records a **student pickup** on the Shareable Food Log page.
   Multiple foods picked up by the same student in one visit are stored
   as a single `Distribution` (one row in the log) but each line still
   produces an `inventory_logs` `distribute_to_student` entry for audit.
5. Locker quantity ≤ threshold triggers the low-stock alert on the dashboard.

### 5.3 Membership management
1. Admin opens the Students page.
2. Admin can add/edit/delete students and toggle their
   `is_sub_food_member` flag with a single click.

### 5.4 Profile (any user)
- Logged-in users open `/profile` to update their name, email, and password.
- Email is validated; password change requires the current password and a
  matching confirmation.

### 5.5 Student day-to-day
1. Student logs in (or self-registers).
2. Lands on a neutral dashboard showing membership badge, info tiles, and
   currently-available locker food.
3. Students cannot edit anything inventory-related.

### 5.6 Sharing the food log
- Filter the `Shareable Food Log` page by a date range.
- A plain-text representation is generated server-side
  (`Apr 29, 2026 | Mekan | Chicken Mayo: 1, Noodles: 1, Rice: 1`).
- One click copies the text to the clipboard.
- A second button downloads a CSV of the same range.

### 5.7 Audit
- Every inventory change creates an `inventory_logs` row including who did
  it, when, the action type, source/destination, and an optional note.
- Admins can review the last 500 entries on the Inventory History page.

## 6. Future expansion plan

Sidebar placeholders are already wired up for the following modules; they
all currently render a "Coming soon" page.

| Module                        | Adds to data model                           | New routes               |
|-------------------------------|----------------------------------------------|--------------------------|
| Borrowing system              | `resources`, `borrow_records`                | `/borrowing/...`         |
| Requests to International Dept| `requests`, `request_messages`               | `/requests/...`          |
| Announcements                 | `announcements`                              | `/announcements/...`     |
| Common Group Chat             | `messages`, `chat_rooms`                     | `/chat/...`              |
| Cleaning Sessions             | `cleaning_tasks`, `cleaning_assignments`     | `/cleaning/...`          |

Each module follows the same pattern as the food module:
- a model section in `models.py`,
- an admin-side blueprint for management,
- a student-facing blueprint for read/interact actions,
- templates under `templates/<module>/`,
- a sidebar nav section grouped logically.
