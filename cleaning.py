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


def _maybe_complete_session(s: CleaningSession) -> None:
    """If every task is verified_done, flip the session to completed."""
    if s.status != "scheduled":
        return
    if not s.tasks:
        return
    if all(t.status == "verified_done" for t in s.tasks):
        s.status = "completed"
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
    sessions = (q.order_by(CleaningSession.scheduled_date.desc(),
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
                    .order_by(CleaningSession.scheduled_date.desc(),
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
                     .filter_by(team_id=team.id, status="scheduled")
                     .count())
    if open_sessions:
        flash("This team still has scheduled cleaning sessions. "
              "Cancel or complete them first.", "danger")
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
    scheduled = _parse_date(request.form.get("scheduled_date"))
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
    if scheduled is None:
        flash("Please choose a scheduled date.", "danger")
        return redirect(url_for("cleaning.index"))

    # Tasks: one per non-empty line.
    task_names = [ln.strip() for ln in raw_tasks.splitlines() if ln.strip()]
    if not task_names:
        flash("Add at least one subtask (one per line).", "danger")
        return redirect(url_for("cleaning.index"))

    s = CleaningSession(
        title=title, description=description, location=location,
        team_id=team.id, team_name=team.name,
        scheduled_date=scheduled, start_time=start, end_time=end,
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
    scheduled = _parse_date(request.form.get("scheduled_date"))
    start = (request.form.get("start_time") or "").strip() or None
    end = (request.form.get("end_time") or "").strip() or None
    team_id_raw = (request.form.get("team_id") or "").strip()

    if not title:
        flash("Session title cannot be empty.", "danger")
        return redirect(url_for("cleaning.index"))
    if scheduled is None:
        flash("Scheduled date is required.", "danger")
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
    s.scheduled_date = scheduled
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
    # Adding a new task may un-complete a session.
    if s.status == "completed":
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
    _maybe_complete_session(s)
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
    if s.status != "scheduled":
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
    _maybe_complete_session(t.session)
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
