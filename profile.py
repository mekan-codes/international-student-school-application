"""
Profile / Settings blueprint.

V1 polish: the page is now called **Settings** (clearer name for what it
actually does — change name/email/phone/privacy/password). The legacy
`/profile` URL is kept as a permanent redirect to `/settings` so old
links and bookmarks keep working.

Sections rendered on the Settings page:
  - Profile information (name, email)
  - Phone number + privacy toggle
  - Password change (current / new / confirm)

Sensitive fields (role, is_sub_food_member, student_id, is_protected) are
never editable here — only an admin can change those.
"""
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, User

profile_bp = Blueprint("profile", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Permissive phone validator: digits, spaces, +, -, parentheses; 5..30 chars.
PHONE_RE = re.compile(r"^[\d +()\-]{5,30}$")


@profile_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone_number = (request.form.get("phone_number") or "").strip()
        show_phone = bool(request.form.get("show_phone_number"))

        # ---- Validate name ----
        if not name:
            flash("Name cannot be empty.", "danger")
            return redirect(url_for("profile.settings"))

        # ---- Validate email ----
        if not EMAIL_RE.match(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("profile.settings"))
        if email != current_user.email:
            existing = User.query.filter_by(email=email).first()
            if existing and existing.id != current_user.id:
                flash("That email is already in use by another account.", "danger")
                return redirect(url_for("profile.settings"))

        # ---- Validate phone (optional) ----
        if phone_number and not PHONE_RE.match(phone_number):
            flash("Please enter a valid phone number "
                  "(digits, spaces, +, -, () only).", "danger")
            return redirect(url_for("profile.settings"))

        # ---- Apply changes (NOT password) ----
        current_user.name = name
        current_user.email = email
        current_user.phone_number = phone_number or None
        current_user.show_phone_number = show_phone if phone_number else False
        db.session.commit()

        flash("Your settings have been updated.", "success")
        return redirect(url_for("profile.settings"))

    return render_template("settings.html")


@profile_bp.route("/profile")
@login_required
def index():
    """Backward-compatible redirect: /profile → /settings."""
    return redirect(url_for("profile.settings"), code=301)


@profile_bp.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    """Dedicated password change form — current + new + confirm required."""
    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    if not current_password or not new_password or not confirm_password:
        flash("All password fields are required.", "danger")
        return redirect(url_for("profile.settings"))

    if not current_user.check_password(current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for("profile.settings"))

    if len(new_password) < 6:
        flash("New password must be at least 6 characters.", "danger")
        return redirect(url_for("profile.settings"))

    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "danger")
        return redirect(url_for("profile.settings"))

    if new_password == current_password:
        flash("New password must be different from the current password.", "warning")
        return redirect(url_for("profile.settings"))

    current_user.set_password(new_password)
    db.session.commit()

    flash("Your password has been updated.", "success")
    return redirect(url_for("profile.settings"))
