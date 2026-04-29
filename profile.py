"""
Profile blueprint — lets the logged-in user update their name, email, and password.
Sensitive fields (role, is_sub_food_member, student_id) are read-only here.
"""
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, User

profile_bp = Blueprint("profile", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        # ---- Validate name ----
        if not name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("profile.index"))

        # ---- Validate email ----
        if not EMAIL_RE.match(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("profile.index"))
        if email != current_user.email:
            existing = User.query.filter_by(email=email).first()
            if existing and existing.id != current_user.id:
                flash("That email is already in use by another account.", "danger")
                return redirect(url_for("profile.index"))

        # ---- Optional password change ----
        if new_password or confirm_password or current_password:
            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("profile.index"))
            if len(new_password) < 6:
                flash("New password must be at least 6 characters.", "danger")
                return redirect(url_for("profile.index"))
            if new_password != confirm_password:
                flash("New passwords do not match.", "danger")
                return redirect(url_for("profile.index"))
            current_user.set_password(new_password)

        # ---- Apply changes ----
        # NOTE: role, is_sub_food_member, and student_id are intentionally NOT
        # editable here — only an admin can change those.
        current_user.name = name
        current_user.email = email
        db.session.commit()

        flash("Your profile has been updated.", "success")
        return redirect(url_for("profile.index"))

    return render_template("profile.html")
