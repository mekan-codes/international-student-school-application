"""
Admin routes: dashboard, student management, food items, inventory, transfers, logs.
All routes are protected and require an authenticated user with role='admin'.
"""
from functools import wraps
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from models import db, User, FoodItem, InventoryLog

admin_bp = Blueprint("admin", __name__)


def admin_required(view):
    """Decorator: only allow users with role='admin'."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _log_action(food: FoodItem, action_type: str, quantity: int,
                source: str | None, destination: str | None, note: str = "") -> None:
    """Helper: create an InventoryLog row for an action."""
    log = InventoryLog(
        food_id=food.id,
        food_name=food.name,
        action_type=action_type,
        quantity=quantity,
        source_location=source,
        destination_location=destination,
        performed_by_user_id=current_user.id,
        performed_by_user_name=current_user.name,
        note=note or None,
        timestamp=datetime.utcnow(),
    )
    db.session.add(log)


# --------------------------------------------------------------------------- #
# Dashboard                                                                   #
# --------------------------------------------------------------------------- #
@admin_bp.route("/")
@admin_required
def dashboard():
    total_students = User.query.filter_by(role="student").count()
    sub_food_members = User.query.filter_by(role="student", is_sub_food_member=True).count()
    total_food_types = FoodItem.query.filter_by(is_active=True).count()
    total_warehouse = db.session.query(func.coalesce(func.sum(FoodItem.warehouse_quantity), 0)).scalar()
    total_locker = db.session.query(func.coalesce(func.sum(FoodItem.locker_quantity), 0)).scalar()

    low_stock_items = [f for f in FoodItem.query.filter_by(is_active=True).all() if f.is_low_stock]

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        sub_food_members=sub_food_members,
        total_food_types=total_food_types,
        total_warehouse=total_warehouse,
        total_locker=total_locker,
        low_stock_items=low_stock_items,
    )


# --------------------------------------------------------------------------- #
# Student management                                                          #
# --------------------------------------------------------------------------- #
@admin_bp.route("/students")
@admin_required
def students():
    student_list = User.query.filter_by(role="student").order_by(User.created_at.desc()).all()
    return render_template("admin/students.html", students=student_list)


@admin_bp.route("/students/add", methods=["POST"])
@admin_required
def add_student():
    name = (request.form.get("name") or "").strip()
    student_id = (request.form.get("student_id") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    is_member = bool(request.form.get("is_sub_food_member"))

    if not all([name, student_id, email, password]):
        flash("All fields are required.", "danger")
        return redirect(url_for("admin.students"))
    if User.query.filter_by(email=email).first():
        flash("Email already exists.", "danger")
        return redirect(url_for("admin.students"))
    if User.query.filter_by(student_id=student_id).first():
        flash("Student ID already exists.", "danger")
        return redirect(url_for("admin.students"))

    user = User(
        name=name, student_id=student_id, email=email,
        role="student", is_sub_food_member=is_member,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f"Added student {name}.", "success")
    return redirect(url_for("admin.students"))


@admin_bp.route("/students/<int:user_id>/edit", methods=["POST"])
@admin_required
def edit_student(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != "student":
        abort(400)

    user.name = (request.form.get("name") or user.name).strip()
    user.student_id = (request.form.get("student_id") or user.student_id).strip()
    new_email = (request.form.get("email") or user.email).strip().lower()
    if new_email != user.email and User.query.filter_by(email=new_email).first():
        flash("Email already in use by another account.", "danger")
        return redirect(url_for("admin.students"))
    user.email = new_email
    user.is_sub_food_member = bool(request.form.get("is_sub_food_member"))

    new_password = request.form.get("password") or ""
    if new_password:
        if len(new_password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("admin.students"))
        user.set_password(new_password)

    db.session.commit()
    flash(f"Updated {user.name}.", "success")
    return redirect(url_for("admin.students"))


@admin_bp.route("/students/<int:user_id>/toggle-member", methods=["POST"])
@admin_required
def toggle_member(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != "student":
        abort(400)
    user.is_sub_food_member = not user.is_sub_food_member
    db.session.commit()
    flash(
        f"{user.name} is now {'a member' if user.is_sub_food_member else 'not a member'}"
        " of the substitute food program.",
        "success",
    )
    return redirect(url_for("admin.students"))


@admin_bp.route("/students/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_student(user_id):
    user = User.query.get_or_404(user_id)
    if user.role != "student":
        abort(400)
    db.session.delete(user)
    db.session.commit()
    flash("Student deleted.", "info")
    return redirect(url_for("admin.students"))


# --------------------------------------------------------------------------- #
# Food items                                                                  #
# --------------------------------------------------------------------------- #
@admin_bp.route("/food-items")
@admin_required
def food_items():
    items = FoodItem.query.order_by(FoodItem.name).all()
    return render_template("admin/food_items.html", items=items)


@admin_bp.route("/food-items/add", methods=["POST"])
@admin_required
def add_food_item():
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "general").strip()
    try:
        threshold = max(0, int(request.form.get("low_stock_threshold") or 0))
    except ValueError:
        flash("Threshold must be a non-negative integer.", "danger")
        return redirect(url_for("admin.food_items"))

    if not name:
        flash("Food name is required.", "danger")
        return redirect(url_for("admin.food_items"))
    if FoodItem.query.filter_by(name=name).first():
        flash("A food item with that name already exists.", "danger")
        return redirect(url_for("admin.food_items"))

    item = FoodItem(name=name, category=category, low_stock_threshold=threshold)
    db.session.add(item)
    db.session.commit()
    flash(f"Created food item: {name}.", "success")
    return redirect(url_for("admin.food_items"))


@admin_bp.route("/food-items/<int:item_id>/edit", methods=["POST"])
@admin_required
def edit_food_item(item_id):
    item = FoodItem.query.get_or_404(item_id)
    item.name = (request.form.get("name") or item.name).strip()
    item.category = (request.form.get("category") or item.category).strip()
    try:
        item.low_stock_threshold = max(0, int(request.form.get("low_stock_threshold") or 0))
    except ValueError:
        flash("Threshold must be a non-negative integer.", "danger")
        return redirect(url_for("admin.food_items"))
    item.is_active = bool(request.form.get("is_active"))
    db.session.commit()
    flash(f"Updated food item: {item.name}.", "success")
    return redirect(url_for("admin.food_items"))


@admin_bp.route("/food-items/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_food_item(item_id):
    item = FoodItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Food item deleted.", "info")
    return redirect(url_for("admin.food_items"))


# --------------------------------------------------------------------------- #
# Warehouse inventory                                                         #
# --------------------------------------------------------------------------- #
@admin_bp.route("/warehouse")
@admin_required
def warehouse():
    items = FoodItem.query.filter_by(is_active=True).order_by(FoodItem.name).all()
    return render_template("admin/warehouse.html", items=items)


@admin_bp.route("/warehouse/add-stock", methods=["POST"])
@admin_required
def add_warehouse_stock():
    item = FoodItem.query.get_or_404(int(request.form.get("food_id") or 0))
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


@admin_bp.route("/warehouse/adjust", methods=["POST"])
@admin_required
def adjust_warehouse():
    """Manually set warehouse quantity (e.g. for corrections)."""
    item = FoodItem.query.get_or_404(int(request.form.get("food_id") or 0))
    try:
        new_qty = int(request.form.get("new_quantity") or -1)
    except ValueError:
        flash("Quantity must be an integer.", "danger")
        return redirect(url_for("admin.warehouse"))
    if new_qty < 0:
        flash("Quantity cannot be negative.", "danger")
        return redirect(url_for("admin.warehouse"))

    delta = new_qty - item.warehouse_quantity
    item.warehouse_quantity = new_qty
    _log_action(item, "adjust_warehouse", delta, source="warehouse",
                destination="warehouse",
                note=(request.form.get("note") or "manual adjustment"))
    db.session.commit()
    flash(f"Adjusted warehouse stock for {item.name} to {new_qty}.", "success")
    return redirect(url_for("admin.warehouse"))


# --------------------------------------------------------------------------- #
# Locker inventory                                                            #
# --------------------------------------------------------------------------- #
@admin_bp.route("/locker")
@admin_required
def locker():
    items = FoodItem.query.filter_by(is_active=True).order_by(FoodItem.name).all()
    return render_template("admin/locker.html", items=items)


@admin_bp.route("/locker/adjust", methods=["POST"])
@admin_required
def adjust_locker():
    item = FoodItem.query.get_or_404(int(request.form.get("food_id") or 0))
    try:
        new_qty = int(request.form.get("new_quantity") or -1)
    except ValueError:
        flash("Quantity must be an integer.", "danger")
        return redirect(url_for("admin.locker"))
    if new_qty < 0:
        flash("Quantity cannot be negative.", "danger")
        return redirect(url_for("admin.locker"))

    delta = new_qty - item.locker_quantity
    item.locker_quantity = new_qty
    _log_action(item, "adjust_locker", delta, source="locker",
                destination="locker",
                note=(request.form.get("note") or "manual adjustment"))
    db.session.commit()
    flash(f"Adjusted locker stock for {item.name} to {new_qty}.", "success")
    return redirect(url_for("admin.locker"))


# --------------------------------------------------------------------------- #
# Transfer warehouse -> locker                                                #
# --------------------------------------------------------------------------- #
@admin_bp.route("/transfer", methods=["GET", "POST"])
@admin_required
def transfer():
    if request.method == "POST":
        item = FoodItem.query.get_or_404(int(request.form.get("food_id") or 0))
        try:
            qty = int(request.form.get("quantity") or 0)
        except ValueError:
            flash("Quantity must be an integer.", "danger")
            return redirect(url_for("admin.transfer"))
        if qty <= 0:
            flash("Quantity must be greater than zero.", "danger")
            return redirect(url_for("admin.transfer"))
        if qty > item.warehouse_quantity:
            flash(
                f"Cannot transfer {qty} — only {item.warehouse_quantity} available in warehouse.",
                "danger",
            )
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
# Logs / history                                                              #
# --------------------------------------------------------------------------- #
@admin_bp.route("/logs")
@admin_required
def logs():
    log_list = InventoryLog.query.order_by(InventoryLog.timestamp.desc()).limit(500).all()
    return render_template("admin/logs.html", logs=log_list)
