"""
Student routes: dashboards (general + food).
- Non-sub-food students see a neutral general dashboard with no food info.
- Sub-food members additionally get a Substitute Food Locker page where they
  can take food directly (student self-pickup).
Students can NEVER modify inventory except through the controlled self-pickup form.
"""
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, abort, flash, request
from flask_login import login_required, current_user

from models import db, FoodItem, Announcement, Distribution, DistributionItem, InventoryLog

student_bp = Blueprint("student", __name__)


def student_required(view):
    """Only students (not staff) may access the student dashboard."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_staff:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def member_required(view):
    """Sub-food member students only."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_staff or not current_user.is_sub_food_member:
            return redirect(url_for("student.dashboard"))
        return view(*args, **kwargs)
    return wrapped


@student_bp.route("/")
@login_required
def dashboard():
    if current_user.is_staff:
        return redirect(url_for("admin.dashboard"))
    # Latest 3 announcements visible to this student. The visibility filter
    # runs in SQL — students never load unpublished or off-audience rows.
    recent_announcements = (Announcement.visible_to(current_user)
                            .limit(3).all())
    return render_template("student/dashboard.html",
                           recent_announcements=recent_announcements)


@student_bp.route("/food", methods=["GET", "POST"])
@member_required
def food():
    """Substitute Food Locker — sub-food members can view and take food."""
    if request.method == "POST":
        # ---- Parse submitted quantities: food_id -> qty dict (hash map) ----
        food_ids = request.form.getlist("food_id[]")
        quantities = request.form.getlist("quantity[]")

        line_map: dict[int, int] = {}
        for fid, qty_str in zip(food_ids, quantities):
            if not fid or not qty_str:
                continue
            try:
                fid_i = int(fid)
                qty_i = int(qty_str)
            except ValueError:
                flash("Quantity must be at least 1.", "danger")
                return redirect(url_for("student.food"))
            if qty_i < 1:
                flash("Quantity must be at least 1.", "danger")
                return redirect(url_for("student.food"))
            line_map[fid_i] = line_map.get(fid_i, 0) + qty_i

        if not line_map:
            flash("Please select at least one food item.", "danger")
            return redirect(url_for("student.food"))

        # ---- Validate availability (dict for O(1) lookups) ----
        items = {f.id: f for f in FoodItem.query.filter(
            FoodItem.id.in_(line_map.keys())).all()}

        for fid, qty in line_map.items():
            f = items.get(fid)
            if not f or not f.is_active:
                flash("One of the selected foods is no longer available.", "danger")
                return redirect(url_for("student.food"))
            if qty > f.locker_quantity:
                flash(
                    f"Only {f.locker_quantity} available for {f.name}.",
                    "danger",
                )
                return redirect(url_for("student.food"))

        # ---- Create grouped Distribution record ----
        dist = Distribution(
            student_id=current_user.id,
            student_name=current_user.name,
            performed_by_user_id=current_user.id,
            performed_by_user_name=current_user.name,
            timestamp=datetime.utcnow(),
            note="Student self-pickup",
            source_type="student_self_pickup",
        )
        db.session.add(dist)
        db.session.flush()  # Assigns dist.id before we reference it below.

        taken_parts: list[str] = []
        for fid, qty in line_map.items():
            f = items[fid]
            f.locker_quantity -= qty
            db.session.add(DistributionItem(
                distribution_id=dist.id,
                food_id=f.id,
                food_name=f.name,
                quantity=qty,
                locker_qty_after=f.locker_quantity,
                warehouse_qty_after=f.warehouse_quantity,
            ))
            # Inventory log entry — mirrors what admin._log_action does but
            # created inline to avoid a circular import with admin.py.
            db.session.add(InventoryLog(
                food_id=f.id,
                food_name=f.name,
                action_type="distribute_to_student",
                quantity=qty,
                source_location="locker",
                destination_location=f"student:{current_user.name}",
                performed_by_user_id=current_user.id,
                performed_by_user_name=current_user.name,
                note=f"Student self-pickup (Distribution #{dist.id})",
                timestamp=datetime.utcnow(),
                warehouse_qty_after=f.warehouse_quantity,
                locker_qty_after=f.locker_quantity,
            ))
            taken_parts.append(f"{f.name} \u00d7 {qty}")

        db.session.commit()
        flash(f"You took {', '.join(taken_parts)}.", "success")
        return redirect(url_for("student.food"))

    # ---- GET — available locker items + this student's recent pickups ----
    locker_items = (FoodItem.query.filter_by(is_active=True)
                    .filter(FoodItem.locker_quantity > 0)
                    .order_by(FoodItem.name).all())
    recent_pickups = (Distribution.query
                      .filter_by(student_id=current_user.id)
                      .order_by(Distribution.timestamp.desc())
                      .limit(5).all())
    return render_template("student/food.html",
                           locker_items=locker_items,
                           recent_pickups=recent_pickups)
