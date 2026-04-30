"""
Admin / Manager routes:
- Dashboard, user management, food items, inventory, transfers, distributions,
  shareable log, inventory history.

Permissions:
- @staff_required → admin OR manager (most operational tasks)
- @admin_required → admin only (role changes, password resets, deleting/editing
  staff accounts)

Protections:
- "is_protected" users can NOT be modified, demoted, or deleted by anyone except
  themselves (through their own profile page).
- The system always keeps at least one admin: demoting/deleting the last admin
  is refused.
"""
from functools import wraps
from datetime import datetime, date, timedelta
import csv
import io

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
    Response,
)
from flask_login import login_required, current_user
from sqlalchemy import func

from models import (
    db, User, FoodItem, InventoryLog, Distribution, DistributionItem,
    Announcement, SupportRequest,
)

admin_bp = Blueprint("admin", __name__)


# --------------------------------------------------------------------------- #
# Decorators                                                                  #
# --------------------------------------------------------------------------- #
def admin_required(view):
    """Admin only."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def staff_required(view):
    """Admin or manager."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_staff:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _log_action(food: FoodItem, action_type: str, quantity: int,
                source: str | None, destination: str | None, note: str = "") -> None:
    """Append an inventory log row.

    `warehouse_qty_after` and `locker_qty_after` are captured from the food
    object's current state, so callers should mutate the FoodItem BEFORE
    calling this function.
    """
    log = InventoryLog(
        food_id=food.id, food_name=food.name,
        action_type=action_type, quantity=quantity,
        source_location=source, destination_location=destination,
        performed_by_user_id=current_user.id,
        performed_by_user_name=current_user.name,
        note=note or None, timestamp=datetime.utcnow(),
        warehouse_qty_after=food.warehouse_quantity,
        locker_qty_after=food.locker_quantity,
    )
    db.session.add(log)


def _admin_count() -> int:
    return User.query.filter_by(role="admin").count()


def _can_manager_modify(target: User) -> bool:
    """Managers may operate only on student-role users."""
    return target.role == "student"


def _ensure_can_modify(target: User, *, allow_self: bool = False) -> None:
    """Raise via flash+abort/return helpers if current_user can't modify target.
    NOTE: callers should check the returned tuple. This helper just raises a
    flash + 403 when blocked. Use _check_can_modify for boolean form."""
    pass  # kept for documentation; logic lives in _check_can_modify below


def _check_can_modify(target: User, *, allow_self: bool = False) -> tuple[bool, str]:
    """Return (allowed, error_message). Centralizes role-based gating."""
    if target.is_protected and target.id != current_user.id:
        return False, "That account is protected and cannot be modified."
    if current_user.is_admin:
        return True, ""
    if current_user.is_manager:
        if allow_self and target.id == current_user.id:
            return True, ""
        if not _can_manager_modify(target):
            return False, "Managers cannot modify admin or manager accounts."
        return True, ""
    return False, "Permission denied."


# --------------------------------------------------------------------------- #
# Dashboard                                                                   #
# --------------------------------------------------------------------------- #
@admin_bp.route("/")
@staff_required
def dashboard():
    """Render dashboard summary in a single aggregate pass.

    Performance / data-structure notes:
    - User counts use SQL `COUNT(*)` instead of pulling rows into Python.
    - Warehouse/locker totals use `SUM()` aggregates.
    - Low-stock filtering is pushed to the database (`locker_quantity <=
      low_stock_threshold`) so we never load the full food table just to
      filter it in Python — this is the same idea as preferring an indexed
      lookup over a linear scan in a data structures course.
    - Each summary value is computed exactly once and passed to the
      template (no re-querying inside the Jinja loop).
    """
    total_students = User.query.filter_by(role="student").count()
    sub_food_members = User.query.filter_by(role="student",
                                            is_sub_food_member=True).count()
    total_food_types = FoodItem.query.filter_by(is_active=True).count()
    total_warehouse = db.session.query(
        func.coalesce(func.sum(FoodItem.warehouse_quantity), 0)).scalar()
    total_locker = db.session.query(
        func.coalesce(func.sum(FoodItem.locker_quantity), 0)).scalar()

    # SQL-side filter for low stock: avoids loading every food item just to
    # filter it in Python. Returns only the rows we'll actually render.
    low_stock_items = (FoodItem.query
                       .filter_by(is_active=True)
                       .filter(FoodItem.locker_quantity <=
                               FoodItem.low_stock_threshold)
                       .order_by(FoodItem.name)
                       .all())

    # V2: 3 most recent announcements (any state) and a count of open
    # requests, both via DB-side limit/count — no Python-side filtering.
    recent_announcements = (Announcement.query
                            .order_by(Announcement.created_at.desc())
                            .limit(3).all())
    open_requests_count = (SupportRequest.query
                           .filter(SupportRequest.status.in_(
                               ["submitted", "in_review"]))
                           .count())

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        sub_food_members=sub_food_members,
        total_food_types=total_food_types,
        total_warehouse=total_warehouse,
        total_locker=total_locker,
        low_stock_items=low_stock_items,
        recent_announcements=recent_announcements,
        open_requests_count=open_requests_count,
    )


# --------------------------------------------------------------------------- #
# User management (was: students)                                             #
# --------------------------------------------------------------------------- #
@admin_bp.route("/users")
@staff_required
def users():
    role_filter = request.args.get("role", "all")
    q = User.query
    if role_filter in ("admin", "manager", "student"):
        q = q.filter_by(role=role_filter)
    user_list = q.order_by(User.role, User.created_at.desc()).all()
    return render_template(
        "admin/users.html",
        users=user_list, role_filter=role_filter,
    )


@admin_bp.route("/users/add", methods=["POST"])
@staff_required
def add_user():
    """Add a new user. Managers may only add students; admins may add students
    or managers (but not other admins via this form — keep admin creation a
    deliberate database-level action)."""
    name = (request.form.get("name") or "").strip()
    student_id = (request.form.get("student_id") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "student").strip()
    is_member = bool(request.form.get("is_sub_food_member"))

    if role not in ("student", "manager"):
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.users"))
    if role == "manager" and not current_user.is_admin:
        flash("Only admins can create managers.", "danger")
        return redirect(url_for("admin.users"))

    if not all([name, email, password]):
        flash("Name, email, and password are required.", "danger")
        return redirect(url_for("admin.users"))
    if role == "student" and not student_id:
        flash("Student ID is required for students.", "danger")
        return redirect(url_for("admin.users"))
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("admin.users"))
    if User.query.filter_by(email=email).first():
        flash("Email already exists.", "danger")
        return redirect(url_for("admin.users"))
    if student_id and User.query.filter_by(student_id=student_id).first():
        flash("Student ID already exists.", "danger")
        return redirect(url_for("admin.users"))

    user = User(
        name=name,
        student_id=student_id or None,
        email=email,
        role=role,
        is_sub_food_member=(is_member if role == "student" else False),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f"Added {role} {name}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/edit", methods=["POST"])
@staff_required
def edit_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    ok, err = _check_can_modify(user)
    if not ok:
        flash(err, "danger"); return redirect(url_for("admin.users"))

    user.name = (request.form.get("name") or user.name).strip()

    # Email
    new_email = (request.form.get("email") or user.email).strip().lower()
    if new_email != user.email:
        existing = User.query.filter_by(email=new_email).first()
        if existing and existing.id != user.id:
            flash("Email already in use by another account.", "danger")
            return redirect(url_for("admin.users"))
        user.email = new_email

    # Student ID (only meaningful for students)
    if user.role == "student":
        new_sid = (request.form.get("student_id") or user.student_id or "").strip()
        if new_sid and new_sid != (user.student_id or ""):
            existing = User.query.filter_by(student_id=new_sid).first()
            if existing and existing.id != user.id:
                flash("Student ID already in use.", "danger")
                return redirect(url_for("admin.users"))
            user.student_id = new_sid
        user.is_sub_food_member = bool(request.form.get("is_sub_food_member"))

    db.session.commit()
    flash(f"Updated {user.name}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle-member", methods=["POST"])
@staff_required
def toggle_member(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.role != "student":
        flash("Only students can be sub-food members.", "danger")
        return redirect(url_for("admin.users"))
    ok, err = _check_can_modify(user)
    if not ok:
        flash(err, "danger"); return redirect(url_for("admin.users"))
    user.is_sub_food_member = not user.is_sub_food_member
    db.session.commit()
    flash(
        f"{user.name} is now {'a member' if user.is_sub_food_member else 'not a member'}"
        " of the substitute food program.",
        "success",
    )
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/promote", methods=["POST"])
@admin_required
def promote_user(user_id):
    """student → manager. Admin only."""
    user = db.session.get(User, user_id) or abort(404)
    if user.is_protected:
        flash("That account is protected.", "danger")
        return redirect(url_for("admin.users"))
    if user.role != "student":
        flash("Only students can be promoted to manager.", "danger")
        return redirect(url_for("admin.users"))
    user.role = "manager"
    user.is_sub_food_member = False  # managers aren't part of the food program
    db.session.commit()
    flash(f"{user.name} is now a manager.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/demote", methods=["POST"])
@admin_required
def demote_user(user_id):
    """manager → student. Admin only. Cannot demote admins through this route."""
    user = db.session.get(User, user_id) or abort(404)
    if user.is_protected:
        flash("That account is protected.", "danger")
        return redirect(url_for("admin.users"))
    if user.role != "manager":
        flash("Only managers can be demoted to student.", "danger")
        return redirect(url_for("admin.users"))
    if not user.student_id:
        # student_id is required for students; ask admin to set one via edit.
        flash("Set a student ID for this account before demoting.", "warning")
        return redirect(url_for("admin.users"))
    user.role = "student"
    db.session.commit()
    flash(f"{user.name} is now a student.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_password(user_id):
    """Admin sets a temporary new password for any non-protected user.
    Old/current password is never displayed or required."""
    user = db.session.get(User, user_id) or abort(404)
    if user.is_protected and user.id != current_user.id:
        flash("That account is protected.", "danger")
        return redirect(url_for("admin.users"))
    new_password = request.form.get("new_password") or ""
    if len(new_password) < 6:
        flash("Temporary password must be at least 6 characters.", "danger")
        return redirect(url_for("admin.users"))
    user.set_password(new_password)
    db.session.commit()
    flash(
        f"Password reset for {user.name}. Share the temporary password securely; "
        "they should change it on next login.",
        "success",
    )
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@staff_required
def delete_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("admin.users"))
    ok, err = _check_can_modify(user)
    if not ok:
        flash(err, "danger"); return redirect(url_for("admin.users"))
    if user.role == "admin":
        # Even an admin can't delete an admin via UI without a second admin.
        if _admin_count() <= 1:
            flash("Cannot delete the last remaining admin.", "danger")
            return redirect(url_for("admin.users"))
    if user.role in ("admin", "manager") and not current_user.is_admin:
        flash("Only admins can delete staff accounts.", "danger")
        return redirect(url_for("admin.users"))

    db.session.delete(user)
    db.session.commit()
    flash(f"Deleted {user.name}.", "info")
    return redirect(url_for("admin.users"))


# --------------------------------------------------------------------------- #
# Food items                                                                  #
# --------------------------------------------------------------------------- #
@admin_bp.route("/food-items")
@staff_required
def food_items():
    items = FoodItem.query.order_by(FoodItem.name).all()
    return render_template("admin/food_items.html", items=items)


def _parse_calories(raw: str | None) -> tuple[bool, int | None, str]:
    """Return (ok, value-or-None, error_message)."""
    raw = (raw or "").strip()
    if not raw:
        return True, None, ""
    try:
        v = int(raw)
    except ValueError:
        return False, None, "Calories per serving must be a whole number."
    if v < 0:
        return False, None, "Calories per serving must be zero or greater."
    return True, v, ""


def _parse_nonneg_int(raw: str | None, label: str) -> tuple[bool, int, str]:
    """Parse a non-negative integer. Empty/None becomes 0."""
    raw = (raw or "").strip()
    if not raw:
        return True, 0, ""
    try:
        v = int(raw)
    except ValueError:
        return False, 0, f"{label} must be a whole number."
    if v < 0:
        return False, 0, f"{label} cannot be negative."
    return True, v, ""


@admin_bp.route("/food-items/add", methods=["POST"])
@staff_required
def add_food_item():
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "general").strip()
    serving_size = (request.form.get("serving_size") or "").strip() or None
    is_active = bool(request.form.get("is_active"))

    ok, threshold, err = _parse_nonneg_int(
        request.form.get("low_stock_threshold"), "Low-stock threshold")
    if not ok:
        flash(err, "danger"); return redirect(url_for("admin.food_items"))

    cal_ok, calories, cal_err = _parse_calories(request.form.get("calories_per_serving"))
    if not cal_ok:
        flash(cal_err, "danger"); return redirect(url_for("admin.food_items"))

    ok, init_wh, err = _parse_nonneg_int(
        request.form.get("initial_warehouse_quantity"), "Initial warehouse quantity")
    if not ok:
        flash(err, "danger"); return redirect(url_for("admin.food_items"))

    ok, init_lk, err = _parse_nonneg_int(
        request.form.get("initial_locker_quantity"), "Initial locker quantity")
    if not ok:
        flash(err, "danger"); return redirect(url_for("admin.food_items"))

    if not name:
        flash("Food name is required.", "danger")
        return redirect(url_for("admin.food_items"))
    if FoodItem.query.filter_by(name=name).first():
        flash("A food item with that name already exists.", "danger")
        return redirect(url_for("admin.food_items"))

    item = FoodItem(
        name=name, category=category, low_stock_threshold=threshold,
        calories_per_serving=calories, serving_size=serving_size,
        is_active=is_active,
        warehouse_quantity=init_wh, locker_quantity=init_lk,
    )
    db.session.add(item)
    db.session.flush()  # populate item.id for log FK

    # Inventory log entries for any nonzero starting stock.
    if init_wh > 0:
        _log_action(item, "add_to_warehouse", init_wh,
                    source=None, destination="warehouse",
                    note="Initial stock on creation")
    if init_lk > 0:
        _log_action(item, "adjust_locker", init_lk,
                    source=None, destination="locker",
                    note="Initial stock on creation")

    db.session.commit()
    flash(f"Created food item: {name}.", "success")
    return redirect(url_for("admin.food_items"))


@admin_bp.route("/food-items/<int:item_id>/edit", methods=["POST"])
@staff_required
def edit_food_item(item_id):
    item = db.session.get(FoodItem, item_id) or abort(404)

    new_name = (request.form.get("name") or "").strip()
    if not new_name:
        flash("Food name cannot be empty.", "danger")
        return redirect(url_for("admin.food_items"))
    if new_name != item.name:
        existing = FoodItem.query.filter_by(name=new_name).first()
        if existing and existing.id != item.id:
            flash("Another food item already uses that name.", "danger")
            return redirect(url_for("admin.food_items"))
    item.name = new_name
    item.category = (request.form.get("category") or item.category).strip() or "general"
    try:
        item.low_stock_threshold = max(0, int(request.form.get("low_stock_threshold") or 0))
    except ValueError:
        flash("Threshold must be a non-negative integer.", "danger")
        return redirect(url_for("admin.food_items"))
    cal_ok, calories, cal_err = _parse_calories(request.form.get("calories_per_serving"))
    if not cal_ok:
        flash(cal_err, "danger")
        return redirect(url_for("admin.food_items"))
    item.calories_per_serving = calories
    item.serving_size = (request.form.get("serving_size") or "").strip() or None
    item.is_active = bool(request.form.get("is_active"))
    db.session.commit()
    flash(f"Updated food item: {item.name}.", "success")
    return redirect(url_for("admin.food_items"))


@admin_bp.route("/food-items/<int:item_id>/delete", methods=["POST"])
@staff_required
def delete_food_item(item_id):
    item = db.session.get(FoodItem, item_id) or abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Food item deleted.", "info")
    return redirect(url_for("admin.food_items"))


# --------------------------------------------------------------------------- #
# Warehouse inventory                                                         #
# --------------------------------------------------------------------------- #
@admin_bp.route("/warehouse")
@staff_required
def warehouse():
    items = FoodItem.query.filter_by(is_active=True).order_by(FoodItem.name).all()
    return render_template("admin/warehouse.html", items=items)


@admin_bp.route("/warehouse/add-stock", methods=["POST"])
@staff_required
def add_warehouse_stock():
    item = db.session.get(FoodItem, int(request.form.get("food_id") or 0)) or abort(404)
    try:
        qty = int(request.form.get("quantity") or 0)
    except ValueError:
        flash("Quantity must be an integer.", "danger")
        return redirect(url_for("admin.warehouse"))
    if qty <= 0:
        flash("Quantity must be greater than zero.", "danger")
        return redirect(url_for("admin.warehouse"))

    note = (request.form.get("note") or "").strip()
    item.warehouse_quantity += qty
    _log_action(item, "add_to_warehouse", qty, source=None,
                destination="warehouse", note=note)
    db.session.commit()
    flash(f"Added {qty} of {item.name} to warehouse.", "success")
    return redirect(url_for("admin.warehouse"))


def _bulk_adjust(field: str, action_type: str, redirect_endpoint: str):
    """Shared logic for bulk warehouse/locker quantity edits.

    Reads form fields named `qty_<food_id>` for every food item, validates
    each as a non-negative integer, then applies any rows whose value
    actually changed. One inventory log entry per changed row.
    """
    items = FoodItem.query.all()
    note = (request.form.get("note") or "Bulk adjustment").strip()

    changes: list[tuple[FoodItem, int, int]] = []  # (item, old, new)
    for item in items:
        raw = request.form.get(f"qty_{item.id}")
        if raw is None:
            continue
        raw = raw.strip()
        if raw == "":
            continue
        try:
            new_qty = int(raw)
        except ValueError:
            flash(f"Quantity for {item.name} must be a whole number.", "danger")
            return redirect(url_for(redirect_endpoint))
        if new_qty < 0:
            flash(f"Quantity for {item.name} cannot be negative.", "danger")
            return redirect(url_for(redirect_endpoint))
        old_qty = getattr(item, field)
        if new_qty != old_qty:
            changes.append((item, old_qty, new_qty))

    if not changes:
        flash("No changes to save.", "info")
        return redirect(url_for(redirect_endpoint))

    location = "warehouse" if field == "warehouse_quantity" else "locker"
    summary_parts: list[str] = []
    for item, old_qty, new_qty in changes:
        delta = new_qty - old_qty
        setattr(item, field, new_qty)
        _log_action(item, action_type, delta,
                    source=location, destination=location,
                    note=note)
        summary_parts.append(f"{item.name} ({old_qty}→{new_qty})")

    db.session.commit()
    flash(f"Saved {len(changes)} change(s): " + ", ".join(summary_parts),
          "success")
    return redirect(url_for(redirect_endpoint))


@admin_bp.route("/warehouse/adjust", methods=["POST"])
@staff_required
def adjust_warehouse():
    """Single-row warehouse quantity setter (kept for compatibility)."""
    item = db.session.get(FoodItem, int(request.form.get("food_id") or 0)) or abort(404)
    try:
        new_qty = int(request.form.get("new_quantity"))
    except (ValueError, TypeError):
        flash("Quantity must be an integer.", "danger")
        return redirect(url_for("admin.warehouse"))
    if new_qty < 0:
        flash("Warehouse quantity cannot be negative.", "danger")
        return redirect(url_for("admin.warehouse"))

    delta = new_qty - item.warehouse_quantity
    if delta == 0:
        flash("No change — warehouse quantity is already that value.", "info")
        return redirect(url_for("admin.warehouse"))

    item.warehouse_quantity = new_qty
    _log_action(item, "adjust_warehouse", delta, source="warehouse",
                destination="warehouse",
                note=(request.form.get("note") or "manual adjustment"))
    db.session.commit()
    flash(f"Adjusted warehouse stock for {item.name} to {new_qty}.", "success")
    return redirect(url_for("admin.warehouse"))


@admin_bp.route("/warehouse/bulk-adjust", methods=["POST"])
@staff_required
def bulk_adjust_warehouse():
    return _bulk_adjust("warehouse_quantity", "adjust_warehouse",
                        "admin.warehouse")


# --------------------------------------------------------------------------- #
# Locker inventory                                                            #
# --------------------------------------------------------------------------- #
@admin_bp.route("/locker")
@staff_required
def locker():
    items = FoodItem.query.filter_by(is_active=True).order_by(FoodItem.name).all()
    return render_template("admin/locker.html", items=items)


@admin_bp.route("/locker/adjust", methods=["POST"])
@staff_required
def adjust_locker():
    item = db.session.get(FoodItem, int(request.form.get("food_id") or 0)) or abort(404)
    try:
        new_qty = int(request.form.get("new_quantity"))
    except (ValueError, TypeError):
        flash("Quantity must be an integer.", "danger")
        return redirect(url_for("admin.locker"))
    if new_qty < 0:
        flash("Locker quantity cannot be negative.", "danger")
        return redirect(url_for("admin.locker"))

    delta = new_qty - item.locker_quantity
    if delta == 0:
        flash("No change — locker quantity is already that value.", "info")
        return redirect(url_for("admin.locker"))

    item.locker_quantity = new_qty
    _log_action(item, "adjust_locker", delta, source="locker",
                destination="locker",
                note=(request.form.get("note") or "manual adjustment"))
    db.session.commit()
    flash(f"Adjusted locker stock for {item.name} to {new_qty}.", "success")
    return redirect(url_for("admin.locker"))


@admin_bp.route("/locker/bulk-adjust", methods=["POST"])
@staff_required
def bulk_adjust_locker():
    return _bulk_adjust("locker_quantity", "adjust_locker", "admin.locker")


# --------------------------------------------------------------------------- #
# Transfer warehouse -> locker                                                #
# --------------------------------------------------------------------------- #
@admin_bp.route("/transfer", methods=["GET", "POST"])
@staff_required
def transfer():
    if request.method == "POST":
        item = db.session.get(FoodItem, int(request.form.get("food_id") or 0)) or abort(404)
        try:
            qty = int(request.form.get("quantity") or 0)
        except ValueError:
            flash("Quantity must be an integer.", "danger")
            return redirect(url_for("admin.transfer"))
        if qty <= 0:
            flash("Quantity must be greater than zero.", "danger")
            return redirect(url_for("admin.transfer"))
        if qty > item.warehouse_quantity:
            flash(f"Cannot transfer {qty} — only {item.warehouse_quantity}"
                  " available in warehouse.", "danger")
            return redirect(url_for("admin.transfer"))

        item.warehouse_quantity -= qty
        item.locker_quantity += qty
        _log_action(item, "transfer_to_locker", qty,
                    source="warehouse", destination="locker",
                    note=(request.form.get("note") or ""))
        db.session.commit()
        flash(f"Transferred {qty} of {item.name} to locker.", "success")
        return redirect(url_for("admin.transfer"))

    items = FoodItem.query.filter_by(is_active=True).order_by(FoodItem.name).all()
    return render_template("admin/transfer.html", items=items)


# --------------------------------------------------------------------------- #
# Distributions / Shareable Food Log                                          #
# --------------------------------------------------------------------------- #
def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@admin_bp.route("/distributions", methods=["GET", "POST"])
@staff_required
def distributions():
    if request.method == "POST":
        try:
            student_id = int(request.form.get("student_id") or 0)
        except ValueError:
            flash("Invalid student.", "danger")
            return redirect(url_for("admin.distributions"))

        student = User.query.filter_by(id=student_id, role="student").first()
        if not student:
            flash("Student not found.", "danger")
            return redirect(url_for("admin.distributions"))

        food_ids = request.form.getlist("food_id[]")
        quantities = request.form.getlist("quantity[]")
        note = (request.form.get("note") or "").strip()

        # Data structure: dict (hash map) keyed by food_id so duplicate rows
        # in the form are summed in O(1) per entry instead of an O(n) scan.
        line_map: dict[int, int] = {}
        for fid, qty in zip(food_ids, quantities):
            if not fid or not qty:
                continue
            try:
                fid_i = int(fid); qty_i = int(qty)
            except ValueError:
                flash("Invalid quantity entered.", "danger")
                return redirect(url_for("admin.distributions"))
            if qty_i <= 0:
                continue
            line_map[fid_i] = line_map.get(fid_i, 0) + qty_i

        if not line_map:
            flash("Please add at least one food and quantity.", "danger")
            return redirect(url_for("admin.distributions"))

        # Data structure: dict (hash map) of FoodItem by id → O(1) lookups
        # while we validate and apply each line, instead of repeatedly
        # filtering the foods list.
        items = {f.id: f for f in FoodItem.query.filter(
            FoodItem.id.in_(line_map.keys())).all()}
        for fid, qty in line_map.items():
            f = items.get(fid)
            if not f:
                flash("One of the selected foods no longer exists.", "danger")
                return redirect(url_for("admin.distributions"))
            if qty > f.locker_quantity:
                flash(f"Cannot give {qty} of {f.name} — only "
                      f"{f.locker_quantity} in the locker.", "danger")
                return redirect(url_for("admin.distributions"))

        dist = Distribution(
            student_id=student.id, student_name=student.name,
            performed_by_user_id=current_user.id,
            performed_by_user_name=current_user.name,
            note=note or None, timestamp=datetime.utcnow(),
        )
        db.session.add(dist); db.session.flush()

        for fid, qty in line_map.items():
            f = items[fid]
            f.locker_quantity -= qty
            db.session.add(DistributionItem(
                distribution_id=dist.id, food_id=f.id, food_name=f.name,
                quantity=qty,
                locker_qty_after=f.locker_quantity,
                warehouse_qty_after=f.warehouse_quantity,
            ))
            _log_action(f, "distribute_to_student", qty,
                        source="locker", destination=f"student:{student.name}",
                        note=f"Distribution #{dist.id}")
        db.session.commit()
        flash(f"Recorded pickup for {student.name}.", "success")
        return redirect(url_for("admin.distributions"))

    students_list = (User.query.filter_by(role="student")
                     .order_by(User.name).all())
    foods_list = (FoodItem.query.filter_by(is_active=True)
                  .order_by(FoodItem.name).all())

    start_d = _parse_date(request.args.get("start"))
    end_d = _parse_date(request.args.get("end"))
    q = Distribution.query
    if start_d:
        q = q.filter(Distribution.timestamp >= datetime.combine(start_d, datetime.min.time()))
    if end_d:
        q = q.filter(Distribution.timestamp < datetime.combine(end_d + timedelta(days=1),
                                                               datetime.min.time()))
    dists = q.order_by(Distribution.timestamp.desc()).limit(500).all()

    text_lines = []
    for d in dists:
        items_str = ", ".join(f"{i.food_name}: {i.quantity}" for i in d.items)
        text_lines.append(
            f"{d.timestamp.strftime('%b %d, %Y')} | {d.student_name} | {items_str}")
    shareable_text = "\n".join(text_lines) if text_lines else "(no pickups in this range)"

    return render_template(
        "admin/distributions.html",
        students=students_list, foods=foods_list, distributions=dists,
        start=request.args.get("start", ""), end=request.args.get("end", ""),
        shareable_text=shareable_text,
    )


@admin_bp.route("/distributions/export.csv")
@staff_required
def export_distributions_csv():
    start_d = _parse_date(request.args.get("start"))
    end_d = _parse_date(request.args.get("end"))
    q = Distribution.query
    if start_d:
        q = q.filter(Distribution.timestamp >= datetime.combine(start_d, datetime.min.time()))
    if end_d:
        q = q.filter(Distribution.timestamp < datetime.combine(end_d + timedelta(days=1),
                                                               datetime.min.time()))
    dists = q.order_by(Distribution.timestamp.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Date", "Time", "Student", "Foods Taken (food: qty)",
        "Locker Remaining (per food)", "Warehouse Remaining (per food)", "Note",
    ])
    for d in dists:
        foods_taken = "; ".join(f"{i.food_name}: {i.quantity}" for i in d.items)
        locker_remaining = "; ".join(
            f"{i.food_name}: {i.locker_qty_after if i.locker_qty_after is not None else '-'}"
            for i in d.items)
        warehouse_remaining = "; ".join(
            f"{i.food_name}: {i.warehouse_qty_after if i.warehouse_qty_after is not None else '-'}"
            for i in d.items)
        writer.writerow([
            d.timestamp.strftime("%Y-%m-%d"),
            d.timestamp.strftime("%H:%M"),
            d.student_name, foods_taken,
            locker_remaining, warehouse_remaining,
            d.note or "",
        ])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=shareable-food-log.csv"},
    )


@admin_bp.route("/distributions/<int:dist_id>/delete", methods=["POST"])
@staff_required
def delete_distribution(dist_id):
    dist = db.session.get(Distribution, dist_id) or abort(404)
    # Data structure: dict of FoodItem by id for O(1) restock lookups while
    # reversing each line of the distribution.
    foods = {f.id: f for f in FoodItem.query.filter(
        FoodItem.id.in_([i.food_id for i in dist.items])).all()}
    for item in dist.items:
        f = foods.get(item.food_id)
        if f is not None:
            f.locker_quantity += item.quantity
            _log_action(f, "adjust_locker", item.quantity,
                        source="locker", destination="locker",
                        note=f"Reversed distribution #{dist.id}")
    db.session.delete(dist)
    db.session.commit()
    flash("Pickup deleted and locker stock restored.", "info")
    return redirect(url_for("admin.distributions"))


# --------------------------------------------------------------------------- #
# Inventory history                                                           #
# --------------------------------------------------------------------------- #
PAGE_SIZE = 10


def _page_window(current: int, last: int, span: int = 2) -> list[int | str]:
    """Pagination helper: build a compact window of page numbers with
    ellipses for skipped sections.

    Example for current=5, last=20: [1, '…', 3, 4, 5, 6, 7, '…', 20]
    """
    if last <= 1:
        return [1]
    pages: list[int | str] = []
    left = max(2, current - span)
    right = min(last - 1, current + span)
    pages.append(1)
    if left > 2:
        pages.append("…")
    for p in range(left, right + 1):
        pages.append(p)
    if right < last - 1:
        pages.append("…")
    pages.append(last)
    return pages


@admin_bp.route("/logs")
@staff_required
def logs():
    """Inventory history with filters (date, user) and pagination."""
    # ---- Parse filters ----
    on_date = _parse_date(request.args.get("date"))
    user_id_raw = (request.args.get("user_id") or "").strip()
    try:
        user_id = int(user_id_raw) if user_id_raw else None
    except ValueError:
        user_id = None

    try:
        page = max(1, int(request.args.get("page") or 1))
    except ValueError:
        page = 1

    # ---- Build query (filters applied at SQL level, not in Python) ----
    q = InventoryLog.query
    if on_date is not None:
        start_dt = datetime.combine(on_date, datetime.min.time())
        end_dt = datetime.combine(on_date + timedelta(days=1), datetime.min.time())
        q = q.filter(InventoryLog.timestamp >= start_dt,
                     InventoryLog.timestamp < end_dt)
    if user_id is not None:
        q = q.filter(InventoryLog.performed_by_user_id == user_id)
    q = q.order_by(InventoryLog.timestamp.desc())

    total = q.count()
    last_page = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > last_page:
        page = last_page
    offset = (page - 1) * PAGE_SIZE
    entries = q.offset(offset).limit(PAGE_SIZE).all()

    # ---- Distinct users for the filter dropdown ----
    distinct_actors = (db.session.query(
        InventoryLog.performed_by_user_id,
        InventoryLog.performed_by_user_name,
    ).distinct().order_by(InventoryLog.performed_by_user_name).all())

    return render_template(
        "admin/logs.html",
        logs=entries,
        page=page, last_page=last_page, total=total,
        page_window=_page_window(page, last_page),
        page_size=PAGE_SIZE,
        actors=distinct_actors,
        filter_date=request.args.get("date", ""),
        filter_user_id=user_id_raw,
    )
