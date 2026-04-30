"""
Student routes: dashboards (general + food).
- Non-sub-food students see a neutral general dashboard with no food info.
- Sub-food members additionally get a food availability page.
Students can NEVER modify inventory.
"""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, abort, flash
from flask_login import login_required, current_user

from models import FoodItem, Announcement

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


@student_bp.route("/food")
@member_required
def food():
    """Available locker food — only for substitute food program members."""
    locker_items = (FoodItem.query.filter_by(is_active=True)
                    .filter(FoodItem.locker_quantity > 0)
                    .order_by(FoodItem.name).all())
    return render_template("student/food.html", locker_items=locker_items)
