"""
Lounge Board blueprint (V4).

Public community space — different from:
  * Announcements   — official staff notices.
  * Intl Dept. Reqs — private support tickets to staff.

Lounge Board lets ANY signed-in user create posts, comment, and react.
Authors can edit/delete their own content; staff (admin/manager) can
moderate (delete any post/comment, pin/unpin, lock/unlock).

Performance / data structures:
  - Filtering and ordering are pushed into SQL (`ORDER BY is_pinned
    DESC, created_at DESC`) so the page never sorts the whole table
    in Python.
  - Pagination uses Flask-SQLAlchemy's keyset paginator (`paginate(
    page=, per_page=)`) to load only one page (10 rows) at a time.
  - Comment & reaction aggregates are computed once per post via the
    already-loaded relationships — no per-row DB roundtrip in the
    template loop.
"""
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from models import db, LoungePost, LoungeComment, LoungeReaction

lounge_board_bp = Blueprint("lounge_board", __name__)

PER_PAGE = 10  # posts per feed page


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_staff:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------------------------------- #
# Feed                                                                        #
# --------------------------------------------------------------------------- #
@lounge_board_bp.route("/")
@login_required
def index():
    """Paginated feed: pinned first, then newest. Optional category +
    text search filters are applied in SQL so we never load rows we
    don't render."""
    category_f = (request.args.get("category") or "").strip()
    search_f = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    q = LoungePost.query
    if category_f and category_f in LoungePost.CATEGORIES:
        q = q.filter(LoungePost.category == category_f)
    if search_f:
        like = f"%{search_f}%"
        q = q.filter(db.or_(
            LoungePost.title.ilike(like),
            LoungePost.content.ilike(like),
        ))

    # Pinned first, then newest. Both keys are pushed into the ORDER BY.
    q = q.order_by(LoungePost.is_pinned.desc(),
                   LoungePost.created_at.desc())

    pagination = q.paginate(page=page, per_page=PER_PAGE, error_out=False)

    return render_template(
        "lounge_board/list.html",
        pagination=pagination,
        posts=pagination.items,
        categories=LoungePost.CATEGORIES,
        category_f=category_f,
        search_f=search_f,
        is_filtered=bool(category_f or search_f),
    )


# --------------------------------------------------------------------------- #
# Create / edit / delete a post                                               #
# --------------------------------------------------------------------------- #
@lounge_board_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_post():
    if request.method == "POST":
        return _save_post(post=None)
    return render_template(
        "lounge_board/form.html",
        post=None,
        categories=LoungePost.CATEGORIES,
    )


@lounge_board_bp.route("/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    post = db.session.get(LoungePost, post_id) or abort(404)
    # Only the author may edit a post; staff get delete/pin/lock instead.
    if not post.can_edit(current_user):
        abort(403)
    if request.method == "POST":
        return _save_post(post=post)
    return render_template(
        "lounge_board/form.html",
        post=post,
        categories=LoungePost.CATEGORIES,
    )


def _save_post(*, post):
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    category = (request.form.get("category") or "General").strip()

    if not title:
        flash("Title is required.", "danger")
        return redirect(request.url)
    if not content:
        flash("Post content is required.", "danger")
        return redirect(request.url)
    if category not in LoungePost.CATEGORIES:
        # Spec: defaults to General if invalid.
        category = "General"

    if post is None:
        post = LoungePost(
            author_user_id=current_user.id,
            author_name=current_user.name,
            title=title, content=content, category=category,
        )
        db.session.add(post)
        flash("Post published.", "success")
    else:
        post.title = title
        post.content = content
        post.category = category
        post.updated_at = datetime.utcnow()
        flash("Post updated.", "success")

    db.session.commit()
    return redirect(url_for("lounge_board.detail", post_id=post.id))


@lounge_board_bp.route("/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = db.session.get(LoungePost, post_id) or abort(404)
    if not post.can_delete(current_user):
        abort(403)
    title = post.title
    db.session.delete(post)
    db.session.commit()
    flash(f'Post "{title}" deleted.', "info")
    return redirect(url_for("lounge_board.index"))


# --------------------------------------------------------------------------- #
# Detail page                                                                 #
# --------------------------------------------------------------------------- #
@lounge_board_bp.route("/<int:post_id>")
@login_required
def detail(post_id):
    post = db.session.get(LoungePost, post_id) or abort(404)
    return render_template("lounge_board/detail.html", post=post)


# --------------------------------------------------------------------------- #
# Moderation: pin / lock (staff only)                                         #
# --------------------------------------------------------------------------- #
@lounge_board_bp.route("/<int:post_id>/pin", methods=["POST"])
@staff_required
def toggle_pin(post_id):
    post = db.session.get(LoungePost, post_id) or abort(404)
    post.is_pinned = not post.is_pinned
    post.updated_at = datetime.utcnow()
    db.session.commit()
    flash(("Pinned" if post.is_pinned else "Unpinned") + f' "{post.title}".',
          "success")
    return redirect(request.referrer
                    or url_for("lounge_board.detail", post_id=post.id))


@lounge_board_bp.route("/<int:post_id>/lock", methods=["POST"])
@staff_required
def toggle_lock(post_id):
    post = db.session.get(LoungePost, post_id) or abort(404)
    post.is_locked = not post.is_locked
    post.updated_at = datetime.utcnow()
    db.session.commit()
    flash(("Locked" if post.is_locked else "Unlocked") + f' "{post.title}".',
          "success")
    return redirect(request.referrer
                    or url_for("lounge_board.detail", post_id=post.id))


# --------------------------------------------------------------------------- #
# Reactions — one per (post, user). Toggle / swap.                            #
# --------------------------------------------------------------------------- #
@lounge_board_bp.route("/<int:post_id>/react", methods=["POST"])
@login_required
def react(post_id):
    reaction_type = (request.form.get("reaction_type") or "").strip()
    if reaction_type not in LoungeReaction.REACTIONS:
        abort(400)

    post = db.session.get(LoungePost, post_id) or abort(404)

    # Indexed lookup via the unique (post_id, user_id) constraint — O(log n).
    existing = LoungeReaction.query.filter_by(
        post_id=post.id, user_id=current_user.id).first()

    if existing is None:
        db.session.add(LoungeReaction(
            post_id=post.id, user_id=current_user.id,
            reaction_type=reaction_type))
    elif existing.reaction_type == reaction_type:
        # Same emoji → toggle off.
        db.session.delete(existing)
    else:
        # Different emoji → swap.
        existing.reaction_type = reaction_type
        existing.created_at = datetime.utcnow()
    db.session.commit()

    # Keep the reader where they were (feed or detail page).
    return redirect(request.referrer
                    or url_for("lounge_board.detail", post_id=post.id))


# --------------------------------------------------------------------------- #
# Comments                                                                    #
# --------------------------------------------------------------------------- #
@lounge_board_bp.route("/<int:post_id>/comments", methods=["POST"])
@login_required
def add_comment(post_id):
    post = db.session.get(LoungePost, post_id) or abort(404)
    if not post.can_comment(current_user):
        flash("This post is locked. New comments are disabled.", "warning")
        return redirect(url_for("lounge_board.detail", post_id=post.id))

    content = (request.form.get("content") or "").strip()
    if not content:
        flash("Comment cannot be empty.", "danger")
        return redirect(url_for("lounge_board.detail", post_id=post.id))

    c = LoungeComment(
        post_id=post.id,
        author_user_id=current_user.id,
        author_name=current_user.name,
        content=content,
    )
    db.session.add(c)
    db.session.commit()
    return redirect(url_for("lounge_board.detail", post_id=post.id)
                    + f"#c-{c.id}")


@lounge_board_bp.route("/comments/<int:comment_id>/edit", methods=["POST"])
@login_required
def edit_comment(comment_id):
    c = db.session.get(LoungeComment, comment_id) or abort(404)
    if not c.can_edit(current_user):
        abort(403)
    new_content = (request.form.get("content") or "").strip()
    if not new_content:
        flash("Comment cannot be empty.", "danger")
        return redirect(url_for("lounge_board.detail", post_id=c.post_id))
    c.content = new_content
    c.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Comment updated.", "success")
    return redirect(url_for("lounge_board.detail", post_id=c.post_id)
                    + f"#c-{c.id}")


@lounge_board_bp.route("/comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    c = db.session.get(LoungeComment, comment_id) or abort(404)
    if not c.can_delete(current_user):
        abort(403)
    post_id = c.post_id
    db.session.delete(c)
    db.session.commit()
    flash("Comment deleted.", "info")
    return redirect(url_for("lounge_board.detail", post_id=post_id))
