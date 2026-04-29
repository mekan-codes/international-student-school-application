# Project Specification — International Student School Support App

## 1. Problem statement

International students at the school rely on shared, manually-tracked
systems: a substitute-food program with a small warehouse and a daily-access
locker, a cleaning rotation, borrowed equipment, and an informal suggestion
channel. These are currently managed across spreadsheets, chat groups, and
hallway notes — leading to lost stock, missed cleaning shifts, and unclear
membership status.

This app centralizes these systems into a single role-based dashboard.

## 2. Version 1 features

V1 implements only the **substitute food management module**.

| Feature                              | Admin | Student |
|--------------------------------------|:-----:|:-------:|
| Login / logout                       |   ✅   |    ✅    |
| Public student registration          |   —   |    ✅    |
| Admin dashboard with summary cards   |   ✅   |    —    |
| Student management (CRUD)            |   ✅   |    —    |
| Toggle substitute-food membership    |   ✅   |    —    |
| Food item catalog (CRUD)             |   ✅   |    —    |
| Add stock to warehouse               |   ✅   |    —    |
| Adjust warehouse / locker quantities |   ✅   |    —    |
| Transfer stock warehouse → locker    |   ✅   |    —    |
| Low-stock alerts on dashboard        |   ✅   |    —    |
| Inventory log / history              |   ✅   |    —    |
| Student dashboard (membership view)  |   —   |    ✅    |
| View available locker food (read)    |   —   |    ✅    |

## 3. User roles

- **Admin** — created by another admin. Full access. Demo: `admin@school.com / admin123`.
- **Student** — created by self-registration or by an admin. Read-only access.
  May or may not be a *substitute food member*.

Role enforcement is implemented in two layers:
- Each admin route is decorated with `@admin_required`.
- The student route blocks admins (so the views remain semantically distinct).

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
| category              | STRING      | e.g. grain, protein                     |
| low_stock_threshold   | INTEGER     | locker_quantity ≤ threshold ⇒ low      |
| is_active             | BOOLEAN     |                                         |
| created_at            | DATETIME    |                                         |
| warehouse_quantity    | INTEGER     | non-negative                            |
| locker_quantity       | INTEGER     | non-negative                            |

> Inventory quantities are stored on the food row itself for V1 simplicity.
> If we add additional storage locations later (e.g. multiple lockers),
> we'll split this into a separate `inventory` table keyed by location.

### `inventory_logs`
| Column                  | Type        | Notes                                                    |
|-------------------------|-------------|----------------------------------------------------------|
| log_id                  | INTEGER PK  |                                                          |
| food_id                 | INTEGER FK  | → `food_items.id`                                        |
| food_name               | STRING      | denormalized for log readability                         |
| action_type             | STRING      | `add_to_warehouse`, `transfer_to_locker`, `adjust_warehouse`, `adjust_locker` |
| quantity                | INTEGER     | positive for adds/transfers; signed delta for adjustments |
| source_location         | STRING      | nullable                                                 |
| destination_location    | STRING      | nullable                                                 |
| performed_by_user_id    | INTEGER FK  | → `users.id`                                             |
| performed_by_user_name  | STRING      | denormalized                                             |
| timestamp               | DATETIME    |                                                          |
| note                    | STRING      | nullable                                                 |

## 5. Main workflows

### 5.1 Admin onboarding
1. Admin logs in (seeded account or one created by another admin).
2. Lands on the dashboard with summary cards and low-stock alerts.

### 5.2 Stocking & distribution
1. Admin creates a food item (name, category, threshold).
2. Admin adds a quantity to the **warehouse** (logged as `add_to_warehouse`).
3. Admin transfers a quantity from warehouse → **locker**
   (logged as `transfer_to_locker`).
4. Validation prevents transferring more than what's available; inputs are
   coerced to non-negative integers.
5. Locker quantity ≤ threshold triggers the low-stock alert on the dashboard.

### 5.3 Membership management
1. Admin opens the Students page.
2. Admin can add/edit/delete students and toggle their
   `is_sub_food_member` flag with a single click.

### 5.4 Student day-to-day
1. Student logs in (or self-registers).
2. Lands on a dashboard showing membership status and currently-available
   locker food. Non-members see a banner indicating limited access.
3. Students cannot edit anything.

### 5.5 Audit
- Every inventory change creates an `inventory_logs` row including who did
  it, when, the action type, source/destination, and an optional note.
- Admins can review the last 500 entries on the Logs page.

## 6. Future expansion plan

The codebase is organized as Flask blueprints so future modules slot in
without touching V1 code.

| Module                      | Adds to data model                              | New routes                          |
|-----------------------------|-------------------------------------------------|-------------------------------------|
| Cleaning schedule           | `cleaning_tasks`, `cleaning_assignments`        | `/cleaning/...`                     |
| Borrowing / shared resources | `resources`, `borrow_records`                  | `/resources/...`                    |
| Suggestion board            | `suggestions`, `suggestion_votes`               | `/suggestions/...`                  |
| Notifications (cross-cutting)| `notifications`                                | in-app banner & per-user feed       |

Each module follows the same pattern as the food module:
- a model file (or section in `models.py`),
- an admin-side blueprint for management,
- a student-facing blueprint for read/interact actions,
- templates under `templates/<module>/`,
- a sidebar nav section grouped logically.
