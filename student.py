"""
Student routes: dashboard and read-only locker view.
Students can NEVER modify inventory.
"""
from functools import wraps
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from models import FoodItem

student_bp = Blueprint("student", __name__)


def student_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.is_admin:
            # Admins should not consume the student dashboard
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@student_bp.route("/")
def dashboard():
    if not current_user.is_authenticated:
        from flask import redirect, url_for
        return redirect(url_for("auth.login"))
    if current_user.is_admin:
        from flask import redirect, url_for
        return redirect(url_for("admin.dashboard"))

    locker_items = FoodItem.query.filter_by(is_active=True) \
        .filter(FoodItem.locker_quantity > 0) \
        .order_by(FoodItem.name).all()

    return render_template("student/dashboard.html", locker_items=locker_items)
