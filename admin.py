"""
Admin routes: dashboard, student management, food items, inventory, transfers,
distributions, shareable log, and inventory history.
All routes are protected by @admin_required.
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

from models import db, User, FoodItem, InventoryLog, Distribution, DistributionItem

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

    new_name = (request.form.get("name") or "").strip()
    if not new_name:
        flash("Food name cannot be empty.", "danger")
        return redirect(url_for("admin.food_items"))
    # Avoid unique-constraint violation
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
@admin_required
def distributions():
    """Record a food pickup for a student (locker quantities decrease) and
    show the Shareable Food Log."""

    if request.method == "POST":
        # ---- Build the pickup ----
        try:
            student_id = int(request.form.get("student_id") or 0)
        except ValueError:
            flash("Invalid student.", "danger")
            return redirect(url_for("admin.distributions"))

        student = User.query.filter_by(id=student_id, role="student").first()
        if not student:
            flash("Student not found.", "danger")
            return redirect(url_for("admin.distributions"))

        # Form sends parallel lists food_id[] and quantity[]
        food_ids = request.form.getlist("food_id[]")
        quantities = request.form.getlist("quantity[]")
        note = (request.form.get("note") or "").strip()

        # Normalize and aggregate (in case the same food appears twice)
        line_map: dict[int, int] = {}
        for fid, qty in zip(food_ids, quantities):
            if not fid or not qty:
                continue
            try:
                fid_i = int(fid)
                qty_i = int(qty)
            except ValueError:
                flash("Invalid quantity entered.", "danger")
                return redirect(url_for("admin.distributions"))
            if qty_i <= 0:
                continue
            line_map[fid_i] = line_map.get(fid_i, 0) + qty_i

        if not line_map:
            flash("Please add at least one food and quantity.", "danger")
            return redirect(url_for("admin.distributions"))

        # Validate that locker stock is sufficient for every item BEFORE writing
        items = {f.id: f for f in FoodItem.query.filter(FoodItem.id.in_(line_map.keys())).all()}
        for fid, qty in line_map.items():
            f = items.get(fid)
            if not f:
                flash("One of the selected foods no longer exists.", "danger")
                return redirect(url_for("admin.distributions"))
            if qty > f.locker_quantity:
                flash(
                    f"Cannot give {qty} of {f.name} — only {f.locker_quantity} in the locker.",
                    "danger",
                )
                return redirect(url_for("admin.distributions"))

        # Create the distribution event
        dist = Distribution(
            student_id=student.id,
            student_name=student.name,
            performed_by_user_id=current_user.id,
            performed_by_user_name=current_user.name,
            note=note or None,
            timestamp=datetime.utcnow(),
        )
        db.session.add(dist)
        db.session.flush()  # get dist.id

        for fid, qty in line_map.items():
            f = items[fid]
            f.locker_quantity -= qty  # decrement stock
            db.session.add(DistributionItem(
                distribution_id=dist.id,
                food_id=f.id,
                food_name=f.name,
                quantity=qty,
                locker_qty_after=f.locker_quantity,
                warehouse_qty_after=f.warehouse_quantity,
            ))
            # Also write a row to inventory_logs so every stock change is audited
            _log_action(
                f, "distribute_to_student", qty,
                source="locker", destination=f"student:{student.name}",
                note=f"Distribution #{dist.id}",
            )

        db.session.commit()
        flash(f"Recorded pickup for {student.name}.", "success")
        return redirect(url_for("admin.distributions"))

    # ---- GET: list distributions, with optional date filter ----
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
        # inclusive end-of-day
        q = q.filter(Distribution.timestamp < datetime.combine(end_d + timedelta(days=1),
                                                               datetime.min.time()))

    dists = q.order_by(Distribution.timestamp.desc()).limit(500).all()

    # Build the plain-text shareable representation
    text_lines = []
    for d in dists:
        items_str = ", ".join(f"{i.food_name}: {i.quantity}" for i in d.items)
        text_lines.append(
            f"{d.timestamp.strftime('%b %d, %Y')} | {d.student_name} | {items_str}"
        )
    shareable_text = "\n".join(text_lines) if text_lines else "(no pickups in this range)"

    return render_template(
        "admin/distributions.html",
        students=students_list,
        foods=foods_list,
        distributions=dists,
        start=request.args.get("start", ""),
        end=request.args.get("end", ""),
        shareable_text=shareable_text,
    )


@admin_bp.route("/distributions/export.csv")
@admin_required
def export_distributions_csv():
    """Download the distribution log as CSV (one row per student-pickup,
    foods grouped into a single column)."""
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
            for i in d.items
        )
        warehouse_remaining = "; ".join(
            f"{i.food_name}: {i.warehouse_qty_after if i.warehouse_qty_after is not None else '-'}"
            for i in d.items
        )
        writer.writerow([
            d.timestamp.strftime("%Y-%m-%d"),
            d.timestamp.strftime("%H:%M"),
            d.student_name,
            foods_taken,
            locker_remaining,
            warehouse_remaining,
            d.note or "",
        ])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=shareable-food-log.csv"},
    )


@admin_bp.route("/distributions/<int:dist_id>/delete", methods=["POST"])
@admin_required
def delete_distribution(dist_id):
    """Delete a recorded pickup and restore the locker stock."""
    dist = Distribution.query.get_or_404(dist_id)
    foods = {f.id: f for f in FoodItem.query.filter(
        FoodItem.id.in_([i.food_id for i in dist.items])).all()}

    for item in dist.items:
        f = foods.get(item.food_id)
        if f is not None:
            f.locker_quantity += item.quantity
            _log_action(
                f, "adjust_locker", item.quantity,
                source="locker", destination="locker",
                note=f"Reversed distribution #{dist.id}",
            )
    db.session.delete(dist)
    db.session.commit()
    flash("Pickup deleted and stock restored.", "info")
    return redirect(url_for("admin.distributions"))


# --------------------------------------------------------------------------- #
# Logs / history                                                              #
# --------------------------------------------------------------------------- #
@admin_bp.route("/logs")
@admin_required
def logs():
    log_list = InventoryLog.query.order_by(InventoryLog.timestamp.desc()).limit(500).all()
    return render_template("admin/logs.html", logs=log_list)
