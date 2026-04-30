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
