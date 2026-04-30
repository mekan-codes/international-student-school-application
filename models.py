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
    AUDIENCES = ("everyone", "all_students", "sub_food_students", "staff_only")

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

    # ----- Visibility helper (DB-side filter) -----
    @classmethod
    def visible_to(cls, user):
        """Return a query of announcements the given user is allowed to see.

        - Students never see unpublished announcements.
        - Audience filter is applied in SQL — never in Python — so large
          announcement tables stay efficient.
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
        return (q.filter_by(is_published=True)
                 .filter(cls.target_audience.in_(allowed))
                 .order_by(cls.created_at.desc()))

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
        }.get(self.target_audience, self.target_audience)

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
