"""
Announcements blueprint.

- Staff (admin/manager) get full CRUD + publish toggle (`/announcements`).
- Students see a read-only feed of published, audience-matched
  announcements (`/announcements`, dispatched by role).
- Optional emoji reactions: one reaction per (user, announcement).

The visibility filter is implemented in `Announcement.visible_to()` and
runs in SQL — students never load unpublished or off-audience rows.
"""
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from models import db, Announcement, AnnouncementReaction, AnnouncementRecipient, User

announcements_bp = Blueprint("announcements", __name__)


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_staff:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------------------------------- #
# Public list — branches by role.                                              #
# --------------------------------------------------------------------------- #
@announcements_bp.route("/")
@login_required
def list_view():
    """Students get the read-only feed; staff get the management table."""
    if current_user.is_staff:
        items = Announcement.visible_to(current_user).all()
        return render_template("announcements/staff_list.html", items=items)
    items = Announcement.visible_to(current_user).all()
    return render_template("announcements/student_list.html", items=items)


# --------------------------------------------------------------------------- #
# Staff management                                                             #
# --------------------------------------------------------------------------- #
def _all_students():
    """Roster used by the specific-students multi-select picker."""
    return (User.query.filter_by(role="student").order_by(User.name).all())


@announcements_bp.route("/new", methods=["GET", "POST"])
@staff_required
def new():
    if request.method == "POST":
        return _save_form(announcement=None)
    return render_template(
        "announcements/form.html",
        announcement=None,
        priorities=Announcement.PRIORITIES,
        audiences=Announcement.AUDIENCES,
        students=_all_students(),
        selected_recipient_ids=set(),
    )


@announcements_bp.route("/<int:ann_id>/edit", methods=["GET", "POST"])
@staff_required
def edit(ann_id):
    a = db.session.get(Announcement, ann_id) or abort(404)
    if request.method == "POST":
        return _save_form(announcement=a)
    return render_template(
        "announcements/form.html",
        announcement=a,
        priorities=Announcement.PRIORITIES,
        audiences=Announcement.AUDIENCES,
        students=_all_students(),
        selected_recipient_ids=set(a.recipient_user_ids()),
    )


@announcements_bp.route("/<int:ann_id>/delete", methods=["POST"])
@staff_required
def delete(ann_id):
    a = db.session.get(Announcement, ann_id) or abort(404)
    title = a.title
    db.session.delete(a)
    db.session.commit()
    flash(f'Announcement "{title}" deleted.', "info")
    return redirect(url_for("announcements.list_view"))


@announcements_bp.route("/<int:ann_id>/publish", methods=["POST"])
@staff_required
def toggle_publish(ann_id):
    a = db.session.get(Announcement, ann_id) or abort(404)
    a.is_published = not a.is_published
    a.updated_at = datetime.utcnow()
    db.session.commit()
    flash(
        f'Announcement "{a.title}" is now '
        + ("published." if a.is_published else "unpublished."),
        "success",
    )
    return redirect(url_for("announcements.list_view"))


# --------------------------------------------------------------------------- #
# Reactions (any logged-in user, on visible+published announcements only)     #
# --------------------------------------------------------------------------- #
@announcements_bp.route("/<int:ann_id>/react", methods=["POST"])
@login_required
def react(ann_id):
    emoji = (request.form.get("emoji") or "").strip()
    if emoji not in AnnouncementReaction.EMOJIS:
        abort(400)

    # Re-use the same visibility query so users can't react to something
    # they shouldn't even see.
    a = (Announcement.visible_to(current_user)
         .filter(Announcement.id == ann_id).first()) or abort(404)
    # Students may only react to published items (visible_to enforces that).

    existing = AnnouncementReaction.query.filter_by(
        announcement_id=a.id, user_id=current_user.id).first()

    if existing is None:
        db.session.add(AnnouncementReaction(
            announcement_id=a.id, user_id=current_user.id, emoji=emoji))
    elif existing.emoji == emoji:
        # Same emoji → toggle off.
        db.session.delete(existing)
    else:
        # Different emoji → swap.
        existing.emoji = emoji
        existing.created_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("announcements.list_view") + f"#a-{a.id}")


# --------------------------------------------------------------------------- #
# Internal: shared create/update form handler                                  #
# --------------------------------------------------------------------------- #
def _save_form(*, announcement):
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    priority = (request.form.get("priority") or "normal").strip()
    audience = (request.form.get("target_audience") or "everyone").strip()
    publish_now = bool(request.form.get("is_published"))
    recipient_ids_raw = request.form.getlist("recipient_ids")

    if not title:
        flash("Title is required.", "danger")
        return redirect(request.url)
    if not content:
        flash("Content cannot be empty.", "danger")
        return redirect(request.url)
    if priority not in Announcement.PRIORITIES:
        flash("Unknown priority.", "danger")
        return redirect(request.url)
    if audience not in Announcement.AUDIENCES:
        flash("Unknown target audience.", "danger")
        return redirect(request.url)

    # When the audience is `specific_students`, validate + resolve the
    # picked student rows up-front so we can fail fast with a clear error.
    chosen_students: list[User] = []
    if audience == "specific_students":
        wanted_ids: set[int] = set()
        for raw in recipient_ids_raw:
            try:
                wanted_ids.add(int(raw))
            except (TypeError, ValueError):
                continue
        if not wanted_ids:
            flash("Pick at least one student for a targeted announcement.",
                  "danger")
            return redirect(request.url)
        chosen_students = (User.query
                           .filter(User.id.in_(wanted_ids),
                                   User.role == "student").all())
        if not chosen_students:
            flash("None of the selected recipients are valid students.",
                  "danger")
            return redirect(request.url)

    if announcement is None:
        announcement = Announcement(
            title=title, content=content,
            priority=priority, target_audience=audience,
            is_published=publish_now,
            author_user_id=current_user.id,
            author_name=current_user.name,
        )
        db.session.add(announcement)
        db.session.flush()  # populate announcement.id
        flash(f'Announcement "{title}" created.', "success")
    else:
        announcement.title = title
        announcement.content = content
        announcement.priority = priority
        announcement.target_audience = audience
        announcement.is_published = publish_now
        announcement.updated_at = datetime.utcnow()
        flash(f'Announcement "{title}" updated.', "success")

    # Sync the recipient join-table rows to match the picked audience.
    _sync_recipients(announcement, chosen_students if audience == "specific_students" else [])

    db.session.commit()
    return redirect(url_for("announcements.list_view"))


def _sync_recipients(ann: Announcement, students: list[User]) -> None:
    """Ensure `ann.recipients` exactly matches the given student list.
    Removes stale rows when the audience flips away from specific_students."""
    # Hash sets give O(1) "is wanted?" / "is existing?" lookups.
    wanted_ids = {u.id for u in students}
    existing_by_uid = {r.student_user_id: r for r in ann.recipients}

    # Remove rows that are no longer wanted.
    for uid, row in list(existing_by_uid.items()):
        if uid not in wanted_ids:
            db.session.delete(row)

    # Add new ones.
    for u in students:
        if u.id not in existing_by_uid:
            db.session.add(AnnouncementRecipient(
                announcement_id=ann.id,
                student_user_id=u.id,
                student_name=u.name,
            ))
