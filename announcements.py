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

from models import db, Announcement, AnnouncementReaction

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

    if announcement is None:
        announcement = Announcement(
            title=title, content=content,
            priority=priority, target_audience=audience,
            is_published=publish_now,
            author_user_id=current_user.id,
            author_name=current_user.name,
        )
        db.session.add(announcement)
        flash(f'Announcement "{title}" created.', "success")
    else:
        announcement.title = title
        announcement.content = content
        announcement.priority = priority
        announcement.target_audience = audience
        announcement.is_published = publish_now
        announcement.updated_at = datetime.utcnow()
        flash(f'Announcement "{title}" updated.', "success")

    db.session.commit()
    return redirect(url_for("announcements.list_view"))
