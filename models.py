"""
Database models for International Lounge.
Uses Flask-SQLAlchemy with SQLite for simple, persistent storage.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Represents admins, managers, and students. Role + flags drive access."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=True)  # null for staff
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # Role: 'admin' | 'manager' | 'student'
    role = db.Column(db.String(20), nullable=False, default="student")

    is_sub_food_member = db.Column(db.Boolean, nullable=False, default=False)

    # Optional phone number with privacy toggle.
    phone_number = db.Column(db.String(40), nullable=True)
    show_phone_number = db.Column(db.Boolean, nullable=False, default=False)

    # Protected (developer/system) accounts cannot be modified, demoted, or
    # deleted by anyone other than themselves (through their own profile).
    is_protected = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # ----- Helpers -----
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_manager(self) -> bool:
        return self.role == "manager"

    @property
    def is_staff(self) -> bool:
        """Admins and managers both count as staff."""
        return self.role in ("admin", "manager")

    @property
    def role_label(self) -> str:
        return {"admin": "Admin", "manager": "Manager",
                "student": "Student"}.get(self.role, self.role.title())


class FoodItem(db.Model):
    """A type of food tracked by the system."""
    __tablename__ = "food_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    category = db.Column(db.String(80), nullable=False, default="general")
    low_stock_threshold = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Inventory quantities (kept on the same row for simplicity in V1)
    warehouse_quantity = db.Column(db.Integer, nullable=False, default=0)
    locker_quantity = db.Column(db.Integer, nullable=False, default=0)

    # Nutrition (optional; "Calories not listed" if unset)
    calories_per_serving = db.Column(db.Integer, nullable=True)
    serving_size = db.Column(db.String(60), nullable=True)

    @property
    def is_low_stock(self) -> bool:
        return self.locker_quantity <= self.low_stock_threshold

    @property
    def calories_display(self) -> str:
        if self.calories_per_serving is None:
            return "Calories not listed"
        return f"{self.calories_per_serving} kcal / serving"


class InventoryLog(db.Model):
    """An audit-log entry created on every inventory change."""
    __tablename__ = "inventory_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey("food_items.id"), nullable=False)
    food_name = db.Column(db.String(120), nullable=False)
    action_type = db.Column(db.String(40), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    source_location = db.Column(db.String(40), nullable=True)
    destination_location = db.Column(db.String(40), nullable=True)
    performed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    performed_by_user_name = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    note = db.Column(db.String(255), nullable=True)

    # Snapshot of stock immediately AFTER the action (nullable for old rows).
    warehouse_qty_after = db.Column(db.Integer, nullable=True)
    locker_qty_after = db.Column(db.Integer, nullable=True)


class Distribution(db.Model):
    """A single 'pickup' event: one student takes one or more foods at once."""
    __tablename__ = "distributions"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    student_name = db.Column(db.String(120), nullable=False)
    performed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    performed_by_user_name = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    note = db.Column(db.String(255), nullable=True)

    items = db.relationship(
        "DistributionItem",
        backref="distribution",
        cascade="all, delete-orphan",
        order_by="DistributionItem.id",
    )


class DistributionItem(db.Model):
    """A single food line within a Distribution event."""
    __tablename__ = "distribution_items"

    id = db.Column(db.Integer, primary_key=True)
    distribution_id = db.Column(db.Integer, db.ForeignKey("distributions.id"), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey("food_items.id"), nullable=False)
    food_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    locker_qty_after = db.Column(db.Integer, nullable=True)
    warehouse_qty_after = db.Column(db.Integer, nullable=True)


# =========================================================================== #
# Version 2: Announcements                                                    #
# =========================================================================== #
class Announcement(db.Model):
    """Official lounge announcement posted by staff.

    Visibility is filtered at the database level (see `visible_to`) so we
    never load rows the current user shouldn't see — same idea as picking
    the right index/key set for a query in a data structures course.
    """
    __tablename__ = "announcements"

    PRIORITIES = ("normal", "important", "urgent")
    AUDIENCES = ("everyone", "all_students", "sub_food_students",
                 "staff_only", "specific_students")

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    content = db.Column(db.Text, nullable=False)

    author_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Snapshot of the author's name at post time (so renaming a user later
    # doesn't rewrite history).
    author_name = db.Column(db.String(120), nullable=False)

    priority = db.Column(db.String(20), nullable=False, default="normal")
    target_audience = db.Column(db.String(30), nullable=False, default="everyone")
    is_published = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    reactions = db.relationship(
        "AnnouncementReaction",
        backref="announcement",
        cascade="all, delete-orphan",
    )
    recipients = db.relationship(
        "AnnouncementRecipient",
        backref="announcement",
        cascade="all, delete-orphan",
    )

    # ----- Visibility helper (DB-side filter) -----
    @classmethod
    def visible_to(cls, user):
        """Return a query of announcements the given user is allowed to see.

        - Students never see unpublished announcements.
        - Audience filter is applied in SQL — never in Python — so large
          announcement tables stay efficient.
        - For `specific_students`, only the listed recipients see the post.
        """
        q = cls.query
        if user is None or not user.is_authenticated:
            return q.filter(db.false())

        if user.is_staff:
            # Staff see everything (published or not, all audiences).
            return q.order_by(cls.created_at.desc())

        # Students: only published, and only audiences they belong to.
        allowed = ["everyone", "all_students"]
        if user.is_sub_food_member:
            allowed.append("sub_food_students")

        # `specific_students` is allowed only when this user has a row in the
        # AnnouncementRecipient join table. We OR that into the audience filter
        # by building a subquery — single SQL round-trip, indexed lookup.
        recipient_ids = (db.session.query(AnnouncementRecipient.announcement_id)
                         .filter(AnnouncementRecipient.student_user_id == user.id))
        return (q.filter_by(is_published=True)
                 .filter(db.or_(
                     cls.target_audience.in_(allowed),
                     db.and_(cls.target_audience == "specific_students",
                             cls.id.in_(recipient_ids)),
                 ))
                 .order_by(cls.created_at.desc()))

    def recipient_user_ids(self) -> list[int]:
        """Helper for the staff edit form: which student ids are selected."""
        return [r.student_user_id for r in self.recipients]

    # ----- Display helpers (used by templates) -----
    @property
    def priority_label(self) -> str:
        return {"normal": "Normal", "important": "Important",
                "urgent": "Urgent"}.get(self.priority, self.priority.title())

    @property
    def priority_badge_class(self) -> str:
        return {
            "normal": "bg-secondary",
            "important": "bg-info text-dark",
            "urgent": "bg-danger",
        }.get(self.priority, "bg-secondary")

    @property
    def audience_label(self) -> str:
        return {
            "everyone": "Everyone",
            "all_students": "All students",
            "sub_food_students": "Sub-food students",
            "staff_only": "Staff only",
            "specific_students": "Specific students",
        }.get(self.target_audience, self.target_audience)

    @property
    def recipient_names(self) -> list[str]:
        """Display names of the targeted students (snapshot at post time)."""
        return [r.student_name for r in self.recipients]

    def reaction_counts(self) -> dict:
        """{emoji: count} dict — O(n) over this announcement's reactions."""
        # Dict (hash map) → O(1) lookup per emoji while counting.
        counts = {e: 0 for e in AnnouncementReaction.EMOJIS}
        for r in self.reactions:
            counts[r.emoji] = counts.get(r.emoji, 0) + 1
        return counts

    def reaction_for(self, user) -> str | None:
        """Which emoji the given user picked, or None."""
        if user is None or not user.is_authenticated:
            return None
        for r in self.reactions:
            if r.user_id == user.id:
                return r.emoji
        return None


class AnnouncementReaction(db.Model):
    """Single reaction on an announcement. One per (user, announcement)."""
    __tablename__ = "announcement_reactions"

    EMOJIS = ("👍", "❤️", "✅", "👀")

    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(
        db.Integer, db.ForeignKey("announcements.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    emoji = db.Column(db.String(8), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("announcement_id", "user_id",
                            name="uq_user_announcement_reaction"),
    )


class AnnouncementRecipient(db.Model):
    """Targeted recipient of an announcement when its `target_audience` is
    `specific_students`. Acts as a join table between announcements and the
    student users picked by staff, with a name snapshot for history."""
    __tablename__ = "announcement_recipients"

    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(
        db.Integer, db.ForeignKey("announcements.id"), nullable=False)
    student_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Snapshot of the student's display name at post time.
    student_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("announcement_id", "student_user_id",
                            name="uq_announcement_recipient"),
    )


# =========================================================================== #
# Version 2: Requests to International Department (support tickets)           #
# =========================================================================== #
class SupportRequest(db.Model):
    """A student-submitted question/request handled by admins or managers.

    This is intentionally a SUPPORT TICKET, not a borrowing record — the
    physical-item borrowing module remains a future feature.
    """
    __tablename__ = "support_requests"

    CATEGORIES = ("Food", "Dormitory", "Documents", "School life",
                  "Health", "Other")
    STATUSES = ("submitted", "in_review", "resolved", "rejected")

    id = db.Column(db.Integer, primary_key=True)
    student_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False)
    student_name = db.Column(db.String(120), nullable=False)

    category = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="submitted")

    admin_response = db.Column(db.Text, nullable=True)
    handled_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True)
    handled_by_name = db.Column(db.String(120), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    # ----- Display helpers (used by templates) -----
    @property
    def status_label(self) -> str:
        return {"submitted": "Submitted", "in_review": "In review",
                "resolved": "Resolved",
                "rejected": "Rejected"}.get(self.status, self.status.title())

    @property
    def status_badge_class(self) -> str:
        return {
            "submitted": "bg-secondary",
            "in_review": "bg-info text-dark",
            "resolved": "bg-success",
            "rejected": "bg-danger",
        }.get(self.status, "bg-secondary")

    @property
    def has_response(self) -> bool:
        return bool(self.admin_response and self.admin_response.strip())


# =========================================================================== #
# Version 3: Borrowing system                                                 #
# =========================================================================== #
class BorrowableItem(db.Model):
    """A shared physical item (umbrella, charger, etc.) that students can
    request to borrow. Quantity tracking is kept on the row for simplicity:
    `available_quantity` is the live count of items not currently lent out.
    """
    __tablename__ = "borrowable_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="general")
    description = db.Column(db.Text, nullable=True)

    total_quantity = db.Column(db.Integer, nullable=False, default=0)
    available_quantity = db.Column(db.Integer, nullable=False, default=0)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )


class BorrowRequest(db.Model):
    """A student request to borrow N copies of an item until a chosen date.
    Status flows through: pending → approved → returned (or rejected).
    Quantity stock changes are enforced inside the borrowing blueprint so
    `available_quantity` never goes negative or exceeds `total_quantity`.
    """
    __tablename__ = "borrow_requests"

    STATUSES = ("pending", "approved", "rejected", "returned")

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("borrowable_items.id"),
                        nullable=False)
    # Snapshot of the item name at request time (so renames don't rewrite history).
    item_name = db.Column(db.String(120), nullable=False)

    student_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                nullable=False)
    student_name = db.Column(db.String(120), nullable=False)

    quantity = db.Column(db.Integer, nullable=False, default=1)
    borrow_until_date = db.Column(db.Date, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="pending")

    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    returned_at = db.Column(db.DateTime, nullable=True)

    handled_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                   nullable=True)
    handled_by_name = db.Column(db.String(120), nullable=True)
    staff_note = db.Column(db.Text, nullable=True)

    item = db.relationship("BorrowableItem", lazy="joined")

    @property
    def status_label(self) -> str:
        return {"pending": "Pending", "approved": "Approved",
                "rejected": "Rejected",
                "returned": "Returned"}.get(self.status, self.status.title())

    @property
    def status_badge_class(self) -> str:
        return {
            "pending": "bg-secondary",
            "approved": "bg-success",
            "rejected": "bg-danger",
            "returned": "bg-info text-dark",
        }.get(self.status, "bg-secondary")


# =========================================================================== #
# Version 3: Cleaning teams & sessions                                        #
# =========================================================================== #
class CleaningTeam(db.Model):
    """A named group of student users that can be assigned to a cleaning
    session. A student may belong to multiple teams."""
    __tablename__ = "cleaning_teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                   nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    members = db.relationship(
        "CleaningTeamMember", backref="team",
        cascade="all, delete-orphan", order_by="CleaningTeamMember.student_name",
    )
    sessions = db.relationship(
        "CleaningSession", backref="team",
        order_by="CleaningSession.scheduled_date.desc()",
    )


class CleaningTeamMember(db.Model):
    """Membership row joining a student user to a CleaningTeam.
    UniqueConstraint enforces one row per (team, student) — O(1) lookup
    on whether a student is in a given team via that index."""
    __tablename__ = "cleaning_team_members"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("cleaning_teams.id"),
                        nullable=False)
    student_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                nullable=False)
    # Snapshot so removed/renamed users don't break old views.
    student_name = db.Column(db.String(120), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("team_id", "student_user_id",
                            name="uq_team_member"),
    )


class CleaningSession(db.Model):
    """A scheduled cleaning event for one team, broken down into subtasks.

    V3.1 workflow:
      scheduled  → students can mark subtasks done
      marked_done → all subtasks done by team, awaiting staff approval
      approved   → staff has signed off, session is closed
      postponed  → staff rescheduled to a new date range; students can
                   keep working (treated like `scheduled` for actions)
      cancelled  → session won't run

    `start_date`/`end_date` model the date *range* a session can be worked
    on. `scheduled_date` is kept for backward compatibility (mirrors
    `start_date`)."""
    __tablename__ = "cleaning_sessions"

    STATUSES = ("scheduled", "marked_done", "approved", "postponed", "cancelled")
    # Statuses where students can still mark subtasks done.
    ACTIVE_STATUSES = ("scheduled", "postponed")

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(160), nullable=True)

    team_id = db.Column(db.Integer, db.ForeignKey("cleaning_teams.id"),
                        nullable=False)
    # Snapshot of the team name at session-creation time.
    team_name = db.Column(db.String(120), nullable=False)

    # Legacy single-day field, kept in sync with start_date for back-compat.
    scheduled_date = db.Column(db.Date, nullable=False)
    # New date-range fields.
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    start_time = db.Column(db.String(10), nullable=True)  # "HH:MM"
    end_time = db.Column(db.String(10), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="scheduled")

    # Postpone bookkeeping (additive; never required for legacy rows).
    postpone_count = db.Column(db.Integer, nullable=False, default=0)
    postpone_note = db.Column(db.Text, nullable=True)
    last_postponed_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by_name = db.Column(db.String(120), nullable=True)

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                   nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False,
        default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    tasks = db.relationship(
        "CleaningTask", backref="session",
        cascade="all, delete-orphan", order_by="CleaningTask.id",
    )

    @property
    def status_label(self) -> str:
        return {
            "scheduled": "Scheduled",
            "marked_done": "Awaiting approval",
            "approved": "Approved",
            "postponed": "Postponed",
            "cancelled": "Cancelled",
        }.get(self.status, self.status.title())

    @property
    def status_badge_class(self) -> str:
        return {
            "scheduled": "bg-secondary",
            "marked_done": "bg-warning text-dark",
            "approved": "bg-success",
            "postponed": "bg-info text-dark",
            "cancelled": "bg-danger",
        }.get(self.status, "bg-secondary")

    @property
    def is_active(self) -> bool:
        """Students can interact with the session in this state."""
        return self.status in self.ACTIVE_STATUSES

    @property
    def date_range_label(self) -> str:
        """Human-readable date range. Falls back to legacy single date."""
        s = self.start_date or self.scheduled_date
        e = self.end_date or self.scheduled_date
        if s == e:
            return s.strftime("%b %d, %Y")
        if s.year == e.year:
            return f"{s.strftime('%b %d')} – {e.strftime('%b %d, %Y')}"
        return f"{s.strftime('%b %d, %Y')} – {e.strftime('%b %d, %Y')}"

    @property
    def task_progress(self) -> tuple[int, int]:
        """(verified_count, total_count) — used for progress display."""
        total = len(self.tasks)
        verified = sum(1 for t in self.tasks if t.status == "verified_done")
        return verified, total

    @property
    def all_tasks_done(self) -> bool:
        """True when every subtask is either marked_done or verified_done.
        Empty task lists return False so a brand-new session doesn't auto-flip."""
        if not self.tasks:
            return False
        return all(t.status in ("marked_done", "verified_done")
                   for t in self.tasks)


class CleaningTask(db.Model):
    """A single subtask within a CleaningSession.
    Flow: assigned → marked_done (by student) → verified_done (by staff).
    Staff may also mark a task 'missed'."""
    __tablename__ = "cleaning_tasks"

    STATUSES = ("assigned", "marked_done", "verified_done", "missed")

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("cleaning_sessions.id"),
                           nullable=False)
    task_name = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="assigned")

    student_note = db.Column(db.Text, nullable=True)
    marked_done_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                       nullable=True)
    marked_done_by_name = db.Column(db.String(120), nullable=True)
    marked_done_at = db.Column(db.DateTime, nullable=True)

    verified_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                                    nullable=True)
    verified_by_name = db.Column(db.String(120), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)

    @property
    def status_label(self) -> str:
        return {
            "assigned": "Assigned",
            "marked_done": "Marked done",
            "verified_done": "Verified",
            "missed": "Missed",
        }.get(self.status, self.status.title())

    @property
    def status_badge_class(self) -> str:
        return {
            "assigned": "bg-secondary",
            "marked_done": "bg-warning text-dark",
            "verified_done": "bg-success",
            "missed": "bg-danger",
        }.get(self.status, "bg-secondary")
