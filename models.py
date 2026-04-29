"""
Database models for International Student School Support App.
Uses Flask-SQLAlchemy with SQLite for simple, persistent storage.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Represents both admins and students. Role determines access."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=True)  # null for admins
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # 'admin' or 'student'
    is_sub_food_member = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


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

    @property
    def is_low_stock(self) -> bool:
        return self.locker_quantity <= self.low_stock_threshold


class InventoryLog(db.Model):
    """An audit-log entry created on every inventory change."""
    __tablename__ = "inventory_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    food_id = db.Column(db.Integer, db.ForeignKey("food_items.id"), nullable=False)
    food_name = db.Column(db.String(120), nullable=False)
    action_type = db.Column(db.String(40), nullable=False)
    # add_to_warehouse | transfer_to_locker | adjust_warehouse | adjust_locker
    quantity = db.Column(db.Integer, nullable=False)
    source_location = db.Column(db.String(40), nullable=True)
    destination_location = db.Column(db.String(40), nullable=True)
    performed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    performed_by_user_name = db.Column(db.String(120), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    note = db.Column(db.String(255), nullable=True)
