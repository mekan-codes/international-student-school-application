"""
Requests to International Department blueprint.

This is a SUPPORT-TICKET system (questions / requests for help):
  - Students can submit a request and view their own requests.
  - Admins and managers can view ALL requests, filter them, update
    status, write a response, and (rarely) delete one.

The physical-item BORROWING module is intentionally a separate future
feature and is NOT this system.

Module file is named `requests_bp.py` (not `requests.py`) so it never
shadows the popular `requests` HTTP library.
"""
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from models import db, User, SupportRequest

# Blueprint NAME is `requests` so user-facing URLs are `/requests/...`.
# That name is namespaced from Flask's `request` global, so there is no
# conflict in templates or in `url_for("requests.list_view")`.
requests_bp = Blueprint("requests", __name__)


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_staff:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------------------------------- #
# List view — branches by role.                                                #
# --------------------------------------------------------------------------- #
@requests_bp.route("/")
@login_required
def list_view():
    if current_user.is_staff:
        return _staff_list()
    # Student: only their own requests, newest first. Filter at the DB
    # layer — we never load other students' rows.
    rows = (SupportRequest.query
            .filter_by(student_user_id=current_user.id)
            .order_by(SupportRequest.created_at.desc())
            .all())
    return render_template("requests/student_list.html", rows=rows,
                           categories=SupportRequest.CATEGORIES)


def _staff_list():
    """Filterable management view: status, category, student, search."""
    status_f = (request.args.get("status") or "").strip()
    category_f = (request.args.get("category") or "").strip()
    student_f = (request.args.get("student_id") or "").strip()
    search_f = (request.args.get("q") or "").strip()

    q = SupportRequest.query
    if status_f and status_f in SupportRequest.STATUSES:
        q = q.filter(SupportRequest.status == status_f)
    if category_f and category_f in SupportRequest.CATEGORIES:
        q = q.filter(SupportRequest.category == category_f)
    if student_f.isdigit():
        q = q.filter(SupportRequest.student_user_id == int(student_f))
    if search_f:
        like = f"%{search_f}%"
        q = q.filter(db.or_(
            SupportRequest.title.ilike(like),
            SupportRequest.student_name.ilike(like),
        ))

    rows = q.order_by(SupportRequest.created_at.desc()).all()

    # Distinct list of student users who've ever submitted a request,
    # for the student filter dropdown.
    student_ids = (db.session.query(SupportRequest.student_user_id)
                   .distinct().all())
    students = (User.query
                .filter(User.id.in_([sid for (sid,) in student_ids]))
                .order_by(User.name).all()) if student_ids else []

    is_filtered = any([status_f, category_f, student_f, search_f])

    return render_template(
        "requests/admin_list.html",
        rows=rows,
        statuses=SupportRequest.STATUSES,
        categories=SupportRequest.CATEGORIES,
        students=students,
        status_f=status_f, category_f=category_f,
        student_f=student_f, search_f=search_f,
        is_filtered=is_filtered,
    )


# --------------------------------------------------------------------------- #
# Student create                                                               #
# --------------------------------------------------------------------------- #
@requests_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if current_user.is_staff:
        # Staff don't submit tickets in this module.
        flash("Staff manage requests rather than submit them.", "info")
        return redirect(url_for("requests.list_view"))

    if request.method == "POST":
        category = (request.form.get("category") or "").strip()
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()

        if category not in SupportRequest.CATEGORIES:
            flash("Please choose a category.", "danger")
            return redirect(url_for("requests.new"))
        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("requests.new"))
        if not description:
            flash("Description is required.", "danger")
            return redirect(url_for("requests.new"))

        sr = SupportRequest(
            student_user_id=current_user.id,
            student_name=current_user.name,
            category=category, title=title, description=description,
            status="submitted",
        )
        db.session.add(sr)
        db.session.commit()
        flash("Your request has been submitted.", "success")
        return redirect(url_for("requests.list_view"))

    return render_template("requests/student_new.html",
                           categories=SupportRequest.CATEGORIES)


# --------------------------------------------------------------------------- #
# Detail / respond / status / delete                                           #
# --------------------------------------------------------------------------- #
def _load_or_403(req_id):
    sr = db.session.get(SupportRequest, req_id) or abort(404)
    # Students may only access their own.
    if not current_user.is_staff and sr.student_user_id != current_user.id:
        abort(403)
    return sr


@requests_bp.route("/<int:req_id>")
@login_required
def detail(req_id):
    sr = _load_or_403(req_id)
    return render_template(
        "requests/detail.html",
        r=sr,
        statuses=SupportRequest.STATUSES,
    )


@requests_bp.route("/<int:req_id>/respond", methods=["POST"])
@staff_required
def respond(req_id):
    sr = db.session.get(SupportRequest, req_id) or abort(404)
    response_text = (request.form.get("admin_response") or "").strip()
    sr.admin_response = response_text or None
    sr.handled_by_user_id = current_user.id
    sr.handled_by_name = current_user.name
    sr.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Response saved.", "success")
    return redirect(url_for("requests.detail", req_id=sr.id))


@requests_bp.route("/<int:req_id>/status", methods=["POST"])
@staff_required
def update_status(req_id):
    sr = db.session.get(SupportRequest, req_id) or abort(404)
    new_status = (request.form.get("status") or "").strip()
    if new_status not in SupportRequest.STATUSES:
        flash("Unknown status.", "danger")
        return redirect(url_for("requests.detail", req_id=sr.id))

    if new_status == sr.status:
        flash("Status unchanged.", "info")
        return redirect(url_for("requests.detail", req_id=sr.id))

    sr.status = new_status
    sr.handled_by_user_id = current_user.id
    sr.handled_by_name = current_user.name
    sr.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"Status set to {sr.status_label}.", "success")
    return redirect(url_for("requests.detail", req_id=sr.id))


@requests_bp.route("/<int:req_id>/delete", methods=["POST"])
@staff_required
def delete(req_id):
    sr = db.session.get(SupportRequest, req_id) or abort(404)
    title = sr.title
    db.session.delete(sr)
    db.session.commit()
    flash(f'Request "{title}" deleted.', "info")
    return redirect(url_for("requests.list_view"))
