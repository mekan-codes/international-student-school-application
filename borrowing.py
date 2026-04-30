"""
Borrowing system blueprint (V3).

Concept:
    Students can request shared physical items (umbrellas, chargers,
    calculators, board games...). This is intentionally separate from
    the support-ticket "Requests to International Department" module:
        - Requests = asking for help / a service.
        - Borrowing = requesting a physical shared item with quantity tracking.

Stock invariant (enforced in this file):
    0 <= available_quantity <= total_quantity

Key transitions:
    submit  → pending          (no stock change)
    approve → approved         (available_quantity -= qty)
    reject  → rejected         (no stock change)
    return  → returned         (available_quantity += qty)

Performance / data-structure notes:
    - All filtering is done in SQL (`filter_by(student_user_id=...)`),
      so students never load other students' rows.
    - The student-facing item list orders newest-first via SQL ORDER BY
      rather than sorting in Python — same idea as choosing the right
      key/index for a query in a data structures course.
"""
from datetime import datetime, date
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from models import db, BorrowableItem, BorrowRequest

borrowing_bp = Blueprint("borrowing", __name__)


# --------------------------------------------------------------------------- #
# Decorators                                                                  #
# --------------------------------------------------------------------------- #
def staff_required(view):
    """Admin or manager only."""
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
def _parse_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_pos_int(raw: str | None) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        v = int(raw)
    except ValueError:
        return None
    return v if v >= 0 else None


# --------------------------------------------------------------------------- #
# Role-branched index                                                         #
# --------------------------------------------------------------------------- #
@borrowing_bp.route("/")
@login_required
def index():
    if current_user.is_staff:
        return _staff_view()
    return _student_view()


# --------------------------------------------------------------------------- #
# Student view                                                                #
# --------------------------------------------------------------------------- #
def _student_view():
    """Active items + this student's own requests, both newest-first."""
    items = (BorrowableItem.query
             .filter_by(is_active=True)
             .order_by(BorrowableItem.name).all())

    # SQL-side filter: students only ever load their own rows.
    my_requests = (BorrowRequest.query
                   .filter_by(student_user_id=current_user.id)
                   .order_by(BorrowRequest.requested_at.desc()).all())

    return render_template(
        "borrowing/student.html",
        items=items, my_requests=my_requests, today=date.today(),
    )


@borrowing_bp.route("/request", methods=["POST"])
@login_required
def submit_request():
    if current_user.is_staff:
        flash("Staff manage borrowing rather than borrow items here.", "info")
        return redirect(url_for("borrowing.index"))

    item_id = _parse_pos_int(request.form.get("item_id"))
    qty = _parse_pos_int(request.form.get("quantity"))
    until = _parse_date(request.form.get("borrow_until_date"))

    if item_id is None:
        flash("Please choose an item to borrow.", "danger")
        return redirect(url_for("borrowing.index"))
    item = db.session.get(BorrowableItem, item_id)
    if not item or not item.is_active:
        flash("That item is not available.", "danger")
        return redirect(url_for("borrowing.index"))
    if qty is None or qty < 1:
        flash("Quantity must be at least 1.", "danger")
        return redirect(url_for("borrowing.index"))
    if qty > item.total_quantity:
        flash(f"Quantity cannot exceed total stock ({item.total_quantity}).",
              "danger")
        return redirect(url_for("borrowing.index"))
    if until is None:
        flash("Please choose a borrow-until date.", "danger")
        return redirect(url_for("borrowing.index"))
    if until < date.today():
        flash("Borrow-until date cannot be in the past.", "danger")
        return redirect(url_for("borrowing.index"))

    br = BorrowRequest(
        item_id=item.id, item_name=item.name,
        student_user_id=current_user.id,
        student_name=current_user.name,
        quantity=qty, borrow_until_date=until,
        status="pending",
    )
    db.session.add(br)
    db.session.commit()
    flash(f"Borrow request submitted for {item.name}.", "success")
    return redirect(url_for("borrowing.index"))


# --------------------------------------------------------------------------- #
# Staff view                                                                  #
# --------------------------------------------------------------------------- #
def _staff_view():
    """All items + all requests with optional status filter."""
    status_f = (request.args.get("status") or "").strip()

    items = (BorrowableItem.query
             .order_by(BorrowableItem.name).all())

    q = BorrowRequest.query
    if status_f in BorrowRequest.STATUSES:
        q = q.filter(BorrowRequest.status == status_f)
    rows = q.order_by(BorrowRequest.requested_at.desc()).all()

    return render_template(
        "borrowing/admin.html",
        items=items, rows=rows,
        statuses=BorrowRequest.STATUSES, status_f=status_f,
    )


# --------------------------------------------------------------------------- #
# Item CRUD (staff)                                                           #
# --------------------------------------------------------------------------- #
@borrowing_bp.route("/items/add", methods=["POST"])
@staff_required
def add_item():
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "general").strip() or "general"
    description = (request.form.get("description") or "").strip() or None
    total = _parse_pos_int(request.form.get("total_quantity"))
    is_active = bool(request.form.get("is_active"))

    if not name:
        flash("Item name is required.", "danger")
        return redirect(url_for("borrowing.index"))
    if total is None or total < 1:
        flash("Total quantity must be a positive whole number.", "danger")
        return redirect(url_for("borrowing.index"))

    item = BorrowableItem(
        name=name, category=category, description=description,
        total_quantity=total, available_quantity=total,
        is_active=is_active,
    )
    db.session.add(item)
    db.session.commit()
    flash(f"Added borrowable item: {name}.", "success")
    return redirect(url_for("borrowing.index"))


@borrowing_bp.route("/items/<int:item_id>/edit", methods=["POST"])
@staff_required
def edit_item(item_id):
    item = db.session.get(BorrowableItem, item_id) or abort(404)

    name = (request.form.get("name") or item.name).strip()
    category = (request.form.get("category") or item.category).strip() or "general"
    description = (request.form.get("description") or "").strip() or None
    total = _parse_pos_int(request.form.get("total_quantity"))
    is_active = bool(request.form.get("is_active"))

    if not name:
        flash("Item name cannot be empty.", "danger")
        return redirect(url_for("borrowing.index"))
    if total is None:
        flash("Total quantity must be a non-negative whole number.", "danger")
        return redirect(url_for("borrowing.index"))

    # Number currently lent out = total - available (before this edit).
    on_loan = item.total_quantity - item.available_quantity
    if total < on_loan:
        flash(f"Total quantity cannot be less than the {on_loan} currently "
              "out on loan.", "danger")
        return redirect(url_for("borrowing.index"))

    # Adjust available proportionally so on-loan amount is preserved.
    item.name = name
    item.category = category
    item.description = description
    item.total_quantity = total
    item.available_quantity = total - on_loan
    item.is_active = is_active
    db.session.commit()
    flash(f"Updated borrowable item: {name}.", "success")
    return redirect(url_for("borrowing.index"))


@borrowing_bp.route("/items/<int:item_id>/delete", methods=["POST"])
@staff_required
def delete_item(item_id):
    item = db.session.get(BorrowableItem, item_id) or abort(404)
    # Refuse if any non-final requests still reference this item.
    open_count = (BorrowRequest.query
                  .filter_by(item_id=item.id)
                  .filter(BorrowRequest.status.in_(["pending", "approved"]))
                  .count())
    if open_count:
        flash("This item still has pending or approved borrow requests.",
              "danger")
        return redirect(url_for("borrowing.index"))
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f"Deleted borrowable item: {name}.", "info")
    return redirect(url_for("borrowing.index"))


# --------------------------------------------------------------------------- #
# Request handling (staff)                                                    #
# --------------------------------------------------------------------------- #
def _stamp_handler(br: BorrowRequest, note: str | None = None) -> None:
    br.handled_by_user_id = current_user.id
    br.handled_by_name = current_user.name
    if note is not None:
        br.staff_note = note or None


@borrowing_bp.route("/requests/<int:req_id>/approve", methods=["POST"])
@staff_required
def approve(req_id):
    br = db.session.get(BorrowRequest, req_id) or abort(404)
    if br.status != "pending":
        flash("Only pending requests can be approved.", "warning")
        return redirect(url_for("borrowing.index"))

    item = db.session.get(BorrowableItem, br.item_id)
    if not item:
        flash("That item no longer exists.", "danger")
        return redirect(url_for("borrowing.index"))
    if br.quantity > item.available_quantity:
        flash(f"Cannot approve — only {item.available_quantity} of "
              f"{item.name} available.", "danger")
        return redirect(url_for("borrowing.index"))

    item.available_quantity -= br.quantity  # invariant: stays >= 0
    br.status = "approved"
    br.approved_at = datetime.utcnow()
    _stamp_handler(br, request.form.get("staff_note"))
    db.session.commit()
    flash(f"Approved {br.student_name}'s request for "
          f"{br.quantity} × {br.item_name}.", "success")
    return redirect(url_for("borrowing.index"))


@borrowing_bp.route("/requests/<int:req_id>/reject", methods=["POST"])
@staff_required
def reject(req_id):
    br = db.session.get(BorrowRequest, req_id) or abort(404)
    if br.status != "pending":
        flash("Only pending requests can be rejected.", "warning")
        return redirect(url_for("borrowing.index"))
    br.status = "rejected"
    br.rejected_at = datetime.utcnow()
    _stamp_handler(br, request.form.get("staff_note"))
    db.session.commit()
    flash(f"Rejected {br.student_name}'s request.", "info")
    return redirect(url_for("borrowing.index"))


@borrowing_bp.route("/requests/<int:req_id>/return", methods=["POST"])
@staff_required
def mark_returned(req_id):
    br = db.session.get(BorrowRequest, req_id) or abort(404)
    if br.status != "approved":
        flash("Only approved requests can be marked returned.", "warning")
        return redirect(url_for("borrowing.index"))

    item = db.session.get(BorrowableItem, br.item_id)
    if item:
        # Cap at total_quantity so available never exceeds the cap.
        item.available_quantity = min(
            item.total_quantity, item.available_quantity + br.quantity)
    br.status = "returned"
    br.returned_at = datetime.utcnow()
    _stamp_handler(br, request.form.get("staff_note"))
    db.session.commit()
    flash(f"Marked {br.quantity} × {br.item_name} returned by "
          f"{br.student_name}.", "success")
    return redirect(url_for("borrowing.index"))
