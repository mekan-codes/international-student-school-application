"""
Resources blueprint — editable Common Drives / link cards (V3.2).

Staff (admin/manager) can add, edit, and delete resource cards.
Students see only active resources as external-link cards.

Data-structure note:
  `Resource.query.filter_by(is_active=True)` pushes the filter to SQL so
  students never load inactive rows into Python — same principle as avoiding
  a linear scan when an indexed lookup is available.
"""
from urllib.parse import urlparse
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from models import db, Resource

resources_bp = Blueprint("resources", __name__)


# --------------------------------------------------------------------------- #
# Decorator                                                                   #
# --------------------------------------------------------------------------- #
def staff_required(view):
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
def _validate_url(raw: str) -> str | None:
    """Return the URL if it looks valid, otherwise None."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None
    except Exception:
        return None
    return raw


# --------------------------------------------------------------------------- #
# Routes                                                                      #
# --------------------------------------------------------------------------- #
@resources_bp.route("/")
@login_required
def index():
    """Students see active resources; staff see all with management controls."""
    if current_user.is_staff:
        # Staff: all resources ordered by newest first — O(n) DB scan is fine
        # here since the resources table is expected to be tiny.
        resources = Resource.query.order_by(Resource.created_at.desc()).all()
    else:
        # Students: only active resources, push filter to SQL.
        resources = (Resource.query
                     .filter_by(is_active=True)
                     .order_by(Resource.created_at.desc())
                     .all())
    return render_template("resources.html", resources=resources)


@resources_bp.route("/add", methods=["POST"])
@staff_required
def add_resource():
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    raw_url = request.form.get("url") or ""
    is_active = bool(request.form.get("is_active"))

    if not title:
        flash("Title is required.", "danger")
        return redirect(url_for("resources.index"))

    url = _validate_url(raw_url)
    if url is None:
        flash("Please enter a valid URL starting with http:// or https://.",
              "danger")
        return redirect(url_for("resources.index"))

    r = Resource(
        title=title,
        description=description,
        url=url,
        is_active=is_active,
        created_by_user_id=current_user.id,
    )
    db.session.add(r)
    db.session.commit()
    flash(f"Added resource: {title}.", "success")
    return redirect(url_for("resources.index"))


@resources_bp.route("/<int:resource_id>/edit", methods=["POST"])
@staff_required
def edit_resource(resource_id):
    r = db.session.get(Resource, resource_id) or abort(404)

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    raw_url = request.form.get("url") or ""
    # Checkbox: present = active, absent = inactive.
    is_active = bool(request.form.get("is_active"))

    if not title:
        flash("Title is required.", "danger")
        return redirect(url_for("resources.index"))

    url = _validate_url(raw_url)
    if url is None:
        flash("Please enter a valid URL starting with http:// or https://.",
              "danger")
        return redirect(url_for("resources.index"))

    r.title = title
    r.description = description
    r.url = url
    r.is_active = is_active
    db.session.commit()
    flash(f"Updated resource: {title}.", "success")
    return redirect(url_for("resources.index"))


@resources_bp.route("/<int:resource_id>/delete", methods=["POST"])
@staff_required
def delete_resource(resource_id):
    r = db.session.get(Resource, resource_id) or abort(404)
    title = r.title
    db.session.delete(r)
    db.session.commit()
    flash(f"Deleted resource: {title}.", "info")
    return redirect(url_for("resources.index"))
