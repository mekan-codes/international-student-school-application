"""
Cleaning teams & sessions blueprint (V3).

Concept:
    Admin/manager creates cleaning teams (a named group of students), then
    schedules cleaning sessions assigned to one team. Each session is broken
    into subtasks (e.g. "Vacuum", "Take out trash"). Team members tick tasks
    as done; staff verify them. A session auto-completes when all its tasks
    are verified.

Performance / data-structure notes:
    - A student's view filters in SQL (sessions whose team_id is in the
      student's team list) — never load every session and filter in Python.
    - Team membership lookup uses a UniqueConstraint(team_id, student_id),
      which gives us an O(1) "is in team?" check via the index.
    - When rendering a team's session list, sessions are grouped/sorted by
      DB-side ORDER BY rather than Python-side sort.
"""
from datetime import datetime, date
from functools import wraps

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)
from flask_login import login_required, current_user

from models import (
    db, User, CleaningTeam, CleaningTeamMember,
    CleaningSession, CleaningTask,
)

cleaning_bp = Blueprint("cleaning", __name__)


# --------------------------------------------------------------------------- #
# Decorators                                                                  #
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
def _parse_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _student_team_ids(user_id: int) -> list[int]:
    """Return the team IDs a student belongs to (DB-side query, O(rows))."""
    return [tid for (tid,) in (
        db.session.query(CleaningTeamMember.team_id)
        .filter_by(student_user_id=user_id).all()
    )]


def _maybe_team_done(s: CleaningSession) -> None:
    """Flip the session to `marked_done` (awaiting staff approval) once every
    subtask has been either marked_done or verified_done. Only applies to
    sessions still in an active state — never overrides approved/cancelled."""
    if s.status not in CleaningSession.ACTIVE_STATUSES:
        return
    if not s.tasks:
        return
    if s.all_tasks_done:
        s.status = "marked_done"
        s.updated_at = datetime.utcnow()


# --------------------------------------------------------------------------- #
# Role-branched index                                                         #
# --------------------------------------------------------------------------- #
@cleaning_bp.route("/")
@login_required
def index():
    if current_user.is_staff:
        return _staff_view()
    return _student_view()


# --------------------------------------------------------------------------- #
# Staff view                                                                  #
# --------------------------------------------------------------------------- #
def _staff_view():
    status_f = (request.args.get("status") or "").strip()

    teams = (CleaningTeam.query
             .order_by(CleaningTeam.name).all())

    q = CleaningSession.query
    if status_f in CleaningSession.STATUSES:
        q = q.filter(CleaningSession.status == status_f)
    # Order by start_date when present (new sessions), falling back to
    # the legacy single-day field.
    sessions = (q.order_by(
        db.func.coalesce(CleaningSession.start_date,
                         CleaningSession.scheduled_date).desc(),
        CleaningSession.created_at.desc()).all())

    # Roster of all student users for the team-builder dropdowns.
    students = (User.query.filter_by(role="student")
                .order_by(User.name).all())

    return render_template(
        "cleaning/admin.html",
        teams=teams, sessions=sessions, students=students,
        statuses=CleaningSession.STATUSES, status_f=status_f,
    )


# --------------------------------------------------------------------------- #
# Student view                                                                #
# --------------------------------------------------------------------------- #
def _student_view():
    """Show only sessions for teams this student belongs to."""
    team_ids = _student_team_ids(current_user.id)

    if team_ids:
        sessions = (CleaningSession.query
                    .filter(CleaningSession.team_id.in_(team_ids))
                    .order_by(
                        db.func.coalesce(CleaningSession.start_date,
                                         CleaningSession.scheduled_date).desc(),
                        CleaningSession.created_at.desc()).all())
        my_teams = (CleaningTeam.query
                    .filter(CleaningTeam.id.in_(team_ids))
                    .order_by(CleaningTeam.name).all())
    else:
        sessions, my_teams = [], []

    return render_template(
        "cleaning/student.html",
        sessions=sessions, my_teams=my_teams,
        my_team_ids=set(team_ids),
    )


# --------------------------------------------------------------------------- #
# Team detail (members) — clickable team badge                                #
# --------------------------------------------------------------------------- #
@cleaning_bp.route("/teams/<int:team_id>/members")
@login_required
def team_members(team_id):
    """Render the member list of a single team.

    Authorization:
      - Staff can view any team.
      - A student can view a team only if they're on it (so other teams'
        members and phone numbers stay private).
    """
    team = db.session.get(CleaningTeam, team_id) or abort(404)

    if not current_user.is_staff:
        is_member = (CleaningTeamMember.query
                     .filter_by(team_id=team.id,
                                student_user_id=current_user.id)
                     .first()) is not None
        if not is_member:
            abort(403)

    # Pull in the underlying user rows so we can show student_id and respect
    # each member's `show_phone_number` privacy toggle.
    member_rows = []
    for m in team.members:
        u = db.session.get(User, m.student_user_id)
        member_rows.append({
            "name": m.student_name,
            "student_id": (u.student_id if u else None),
            "phone_number": (u.phone_number if u and u.show_phone_number else None),
        })

    return render_template(
        "cleaning/_team_members.html",
        team=team, members=member_rows,
    )


# --------------------------------------------------------------------------- #
# Teams (staff)                                                               #
# --------------------------------------------------------------------------- #
@cleaning_bp.route("/teams/add", methods=["POST"])
@staff_required
def add_team():
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    student_ids_raw = request.form.getlist("student_ids")

    if not name:
        flash("Team name is required.", "danger")
        return redirect(url_for("cleaning.index"))

    team = CleaningTeam(
        name=name, description=description,
        created_by_user_id=current_user.id,
    )
    db.session.add(team)
    db.session.flush()  # populate team.id

    _sync_team_members(team, student_ids_raw)
    db.session.commit()
    flash(f"Created cleaning team: {name}.", "success")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/teams/<int:team_id>/edit", methods=["POST"])
@staff_required
def edit_team(team_id):
    team = db.session.get(CleaningTeam, team_id) or abort(404)
    name = (request.form.get("name") or team.name).strip()
    description = (request.form.get("description") or "").strip() or None
    student_ids_raw = request.form.getlist("student_ids")

    if not name:
        flash("Team name cannot be empty.", "danger")
        return redirect(url_for("cleaning.index"))

    team.name = name
    team.description = description
    _sync_team_members(team, student_ids_raw)
    # Snapshot team_name in any future-tense sessions to keep them in sync.
    for s in team.sessions:
        if s.status == "scheduled":
            s.team_name = name
    db.session.commit()
    flash(f"Updated cleaning team: {name}.", "success")
    return redirect(url_for("cleaning.index"))


def _sync_team_members(team: CleaningTeam, student_id_strings: list[str]) -> None:
    """Add/remove members so the DB matches the requested student IDs."""
    # Use a hash set for O(1) lookup of "should be a member".
    requested_ids: set[int] = set()
    for raw in student_id_strings:
        try:
            requested_ids.add(int(raw))
        except (TypeError, ValueError):
            continue

    # Index existing members by student id for O(1) removal lookup.
    existing_by_uid = {m.student_user_id: m for m in team.members}

    # Remove members not in the requested set.
    for uid, member in list(existing_by_uid.items()):
        if uid not in requested_ids:
            db.session.delete(member)

    # Add new members (only valid student-role users).
    to_add = requested_ids - set(existing_by_uid)
    if to_add:
        users = (User.query
                 .filter(User.id.in_(to_add), User.role == "student")
                 .all())
        for u in users:
            db.session.add(CleaningTeamMember(
                team_id=team.id,
                student_user_id=u.id,
                student_name=u.name,
            ))


@cleaning_bp.route("/teams/<int:team_id>/delete", methods=["POST"])
@staff_required
def delete_team(team_id):
    team = db.session.get(CleaningTeam, team_id) or abort(404)
    open_sessions = (CleaningSession.query
                     .filter(CleaningSession.team_id == team.id,
                             CleaningSession.status.in_(
                                 list(CleaningSession.ACTIVE_STATUSES)
                                 + ["marked_done"]))
                     .count())
    if open_sessions:
        flash("This team still has open cleaning sessions. "
              "Cancel or approve them first.", "danger")
        return redirect(url_for("cleaning.index"))
    name = team.name
    db.session.delete(team)
    db.session.commit()
    flash(f"Deleted cleaning team: {name}.", "info")
    return redirect(url_for("cleaning.index"))


# --------------------------------------------------------------------------- #
# Sessions (staff)                                                            #
# --------------------------------------------------------------------------- #
@cleaning_bp.route("/sessions/add", methods=["POST"])
@staff_required
def add_session():
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    location = (request.form.get("location") or "").strip() or None
    team_id_raw = (request.form.get("team_id") or "").strip()
    start_date = _parse_date(request.form.get("start_date"))
    end_date = _parse_date(request.form.get("end_date"))
    start = (request.form.get("start_time") or "").strip() or None
    end = (request.form.get("end_time") or "").strip() or None
    raw_tasks = request.form.get("tasks") or ""

    if not title:
        flash("Session title is required.", "danger")
        return redirect(url_for("cleaning.index"))
    try:
        team_id = int(team_id_raw)
    except ValueError:
        flash("Please choose a team.", "danger")
        return redirect(url_for("cleaning.index"))
    team = db.session.get(CleaningTeam, team_id)
    if not team:
        flash("That team no longer exists.", "danger")
        return redirect(url_for("cleaning.index"))
    if start_date is None:
        flash("Please choose a start date.", "danger")
        return redirect(url_for("cleaning.index"))
    # If end date is omitted, treat the session as a single-day event.
    if end_date is None:
        end_date = start_date
    if end_date < start_date:
        flash("End date can't be earlier than the start date.", "danger")
        return redirect(url_for("cleaning.index"))

    # Tasks: one per non-empty line.
    task_names = [ln.strip() for ln in raw_tasks.splitlines() if ln.strip()]
    if not task_names:
        flash("Add at least one subtask (one per line).", "danger")
        return redirect(url_for("cleaning.index"))

    s = CleaningSession(
        title=title, description=description, location=location,
        team_id=team.id, team_name=team.name,
        # Keep `scheduled_date` in lock-step with start_date for back-compat.
        scheduled_date=start_date,
        start_date=start_date, end_date=end_date,
        start_time=start, end_time=end,
        status="scheduled",
        created_by_user_id=current_user.id,
    )
    db.session.add(s)
    db.session.flush()
    for tname in task_names:
        db.session.add(CleaningTask(session_id=s.id, task_name=tname))
    db.session.commit()
    flash(f"Created cleaning session: {title}.", "success")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/sessions/<int:sess_id>/edit", methods=["POST"])
@staff_required
def edit_session(sess_id):
    s = db.session.get(CleaningSession, sess_id) or abort(404)
    title = (request.form.get("title") or s.title).strip()
    description = (request.form.get("description") or "").strip() or None
    location = (request.form.get("location") or "").strip() or None
    start_date = _parse_date(request.form.get("start_date"))
    end_date = _parse_date(request.form.get("end_date"))
    start = (request.form.get("start_time") or "").strip() or None
    end = (request.form.get("end_time") or "").strip() or None
    team_id_raw = (request.form.get("team_id") or "").strip()

    if not title:
        flash("Session title cannot be empty.", "danger")
        return redirect(url_for("cleaning.index"))
    if start_date is None:
        flash("Start date is required.", "danger")
        return redirect(url_for("cleaning.index"))
    if end_date is None:
        end_date = start_date
    if end_date < start_date:
        flash("End date can't be earlier than the start date.", "danger")
        return redirect(url_for("cleaning.index"))

    if team_id_raw:
        try:
            new_team = db.session.get(CleaningTeam, int(team_id_raw))
        except ValueError:
            new_team = None
        if not new_team:
            flash("Selected team is invalid.", "danger")
            return redirect(url_for("cleaning.index"))
        s.team_id = new_team.id
        s.team_name = new_team.name

    s.title = title
    s.description = description
    s.location = location
    s.scheduled_date = start_date
    s.start_date = start_date
    s.end_date = end_date
    s.start_time = start
    s.end_time = end
    db.session.commit()
    flash(f"Updated cleaning session: {title}.", "success")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/sessions/<int:sess_id>/cancel", methods=["POST"])
@staff_required
def cancel_session(sess_id):
    s = db.session.get(CleaningSession, sess_id) or abort(404)
    if s.status == "cancelled":
        flash("Session is already cancelled.", "info")
        return redirect(url_for("cleaning.index"))
    s.status = "cancelled"
    s.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"Cancelled session: {s.title}.", "info")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/sessions/<int:sess_id>/postpone", methods=["POST"])
@staff_required
def postpone_session(sess_id):
    """Move an active session to a new date range. Bumps `postpone_count`
    and stores an optional staff note describing the reason."""
    s = db.session.get(CleaningSession, sess_id) or abort(404)
    if s.status in ("approved", "cancelled"):
        flash("This session is already closed and can't be postponed.",
              "warning")
        return redirect(url_for("cleaning.index"))

    new_start = _parse_date(request.form.get("start_date"))
    new_end = _parse_date(request.form.get("end_date"))
    note = (request.form.get("postpone_note") or "").strip() or None

    if new_start is None:
        flash("Please choose a new start date for the postponement.", "danger")
        return redirect(url_for("cleaning.index"))
    if new_end is None:
        new_end = new_start
    if new_end < new_start:
        flash("End date can't be earlier than the start date.", "danger")
        return redirect(url_for("cleaning.index"))

    s.start_date = new_start
    s.end_date = new_end
    s.scheduled_date = new_start  # keep legacy column aligned
    s.status = "postponed"
    s.postpone_count = (s.postpone_count or 0) + 1
    s.postpone_note = note
    s.last_postponed_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f"Postponed session: {s.title} → {s.date_range_label}.", "info")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/sessions/<int:sess_id>/approve", methods=["POST"])
@staff_required
def approve_session(sess_id):
    """Sign off on the team's work. Any subtasks still in 'marked_done' get
    auto-verified so the session lands in a clean, fully-verified state."""
    s = db.session.get(CleaningSession, sess_id) or abort(404)
    if s.status == "approved":
        flash("Session is already approved.", "info")
        return redirect(url_for("cleaning.index"))
    if s.status == "cancelled":
        flash("Cancelled sessions can't be approved.", "warning")
        return redirect(url_for("cleaning.index"))

    now = datetime.utcnow()
    for t in s.tasks:
        if t.status in ("assigned", "marked_done"):
            t.status = "verified_done"
            t.verified_by_user_id = current_user.id
            t.verified_by_name = current_user.name
            t.verified_at = now
    s.status = "approved"
    s.approved_at = now
    s.approved_by_name = current_user.name
    s.updated_at = now
    db.session.commit()
    flash(f"Approved session: {s.title}.", "success")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/sessions/<int:sess_id>/delete", methods=["POST"])
@staff_required
def delete_session(sess_id):
    s = db.session.get(CleaningSession, sess_id) or abort(404)
    title = s.title
    db.session.delete(s)
    db.session.commit()
    flash(f"Deleted session: {title}.", "info")
    return redirect(url_for("cleaning.index"))


# --------------------------------------------------------------------------- #
# Tasks (subtasks of a session)                                               #
# --------------------------------------------------------------------------- #
@cleaning_bp.route("/sessions/<int:sess_id>/tasks/add", methods=["POST"])
@staff_required
def add_task(sess_id):
    s = db.session.get(CleaningSession, sess_id) or abort(404)
    name = (request.form.get("task_name") or "").strip()
    if not name:
        flash("Task name is required.", "danger")
        return redirect(url_for("cleaning.index"))
    db.session.add(CleaningTask(session_id=s.id, task_name=name))
    s.updated_at = datetime.utcnow()
    # Adding a new (still-assigned) task should re-open a session that had
    # auto-flipped to "marked_done" — there's now unfinished work again.
    if s.status == "marked_done":
        s.status = "scheduled"
    db.session.commit()
    flash(f"Added subtask “{name}”.", "success")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/tasks/<int:task_id>/delete", methods=["POST"])
@staff_required
def delete_task(task_id):
    t = db.session.get(CleaningTask, task_id) or abort(404)
    s = t.session
    db.session.delete(t)
    db.session.flush()
    db.session.refresh(s)
    _maybe_team_done(s)
    db.session.commit()
    flash("Deleted subtask.", "info")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/tasks/<int:task_id>/mark-done", methods=["POST"])
@login_required
def mark_done(task_id):
    """Student action: only members of the assigned team may mark done."""
    t = db.session.get(CleaningTask, task_id) or abort(404)
    s = t.session

    if current_user.is_staff:
        flash("Staff verify tasks rather than mark them done.", "info")
        return redirect(url_for("cleaning.index"))
    if s.status not in CleaningSession.ACTIVE_STATUSES:
        flash("This session is not active for student updates.", "warning")
        return redirect(url_for("cleaning.index"))

    # Membership check uses the indexed (team_id, student_user_id) pair → O(1).
    is_member = (CleaningTeamMember.query
                 .filter_by(team_id=s.team_id,
                            student_user_id=current_user.id)
                 .first()) is not None
    if not is_member:
        abort(403)
    if t.status not in ("assigned", "marked_done"):
        flash("This task can no longer be marked done.", "warning")
        return redirect(url_for("cleaning.index"))

    note = (request.form.get("student_note") or "").strip() or None
    t.status = "marked_done"
    t.student_note = note
    t.marked_done_by_user_id = current_user.id
    t.marked_done_by_name = current_user.name
    t.marked_done_at = datetime.utcnow()
    # If this was the last outstanding subtask, flip the whole session over
    # to "marked_done" so staff can review/approve.
    _maybe_team_done(s)
    db.session.commit()
    flash(f"Marked “{t.task_name}” as done. Awaiting verification.", "success")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/tasks/<int:task_id>/verify", methods=["POST"])
@staff_required
def verify_task(task_id):
    t = db.session.get(CleaningTask, task_id) or abort(404)
    if t.status not in ("marked_done", "assigned"):
        flash("Only marked-done (or assigned) tasks can be verified.",
              "warning")
        return redirect(url_for("cleaning.index"))
    note = (request.form.get("admin_note") or "").strip() or None
    t.status = "verified_done"
    t.admin_note = note
    t.verified_by_user_id = current_user.id
    t.verified_by_name = current_user.name
    t.verified_at = datetime.utcnow()
    _maybe_team_done(t.session)
    db.session.commit()
    flash(f"Verified “{t.task_name}”.", "success")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/tasks/<int:task_id>/miss", methods=["POST"])
@staff_required
def mark_missed(task_id):
    t = db.session.get(CleaningTask, task_id) or abort(404)
    note = (request.form.get("admin_note") or "").strip() or None
    t.status = "missed"
    t.admin_note = note
    t.verified_by_user_id = current_user.id
    t.verified_by_name = current_user.name
    t.verified_at = datetime.utcnow()
    db.session.commit()
    flash(f"Marked “{t.task_name}” as missed.", "info")
    return redirect(url_for("cleaning.index"))


@cleaning_bp.route("/tasks/<int:task_id>/reset", methods=["POST"])
@staff_required
def reset_task(task_id):
    """Staff can reset a task back to 'assigned' — useful when a missed task
    needs to be retried or a mark-done was recorded in error."""
    t = db.session.get(CleaningTask, task_id) or abort(404)
    s = t.session
    if s.status in ("approved", "cancelled"):
        flash("Tasks in approved or cancelled sessions cannot be reset.",
              "warning")
        return redirect(url_for("cleaning.index"))
    # Clear all completion tracking fields so the task starts fresh.
    t.status = "assigned"
    t.student_note = None
    t.marked_done_by_user_id = None
    t.marked_done_by_name = None
    t.marked_done_at = None
    t.verified_by_user_id = None
    t.verified_by_name = None
    t.verified_at = None
    t.admin_note = None
    # If the session had auto-flipped to marked_done, reopen it.
    if s.status == "marked_done":
        s.status = "scheduled"
        s.updated_at = datetime.utcnow()
    db.session.commit()
    flash("Reset task to Assigned.", "info")
    return redirect(url_for("cleaning.index"))
