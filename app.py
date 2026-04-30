"""
International Lounge — Main Application Entry Point
Version 1: Substitute Food Management Module
"""
import os
from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, current_user, login_required
from sqlalchemy import inspect, text

from models import db, User, Resource
from auth import auth_bp
from admin import admin_bp
from student import student_bp
from profile import profile_bp
from announcements import announcements_bp
from requests_bp import requests_bp
from borrowing import borrowing_bp
from cleaning import cleaning_bp
from resources import resources_bp
from seed import seed_database


def _migrate_schema() -> None:
    """Best-effort additive migration so we don't lose existing demo data
    when new columns are added. SQLite-friendly."""
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    statements = []

    if "users" in table_names:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "phone_number" not in user_cols:
            statements.append("ALTER TABLE users ADD COLUMN phone_number VARCHAR(40)")
        if "show_phone_number" not in user_cols:
            statements.append(
                "ALTER TABLE users ADD COLUMN show_phone_number BOOLEAN NOT NULL DEFAULT 0"
            )
        if "is_protected" not in user_cols:
            statements.append(
                "ALTER TABLE users ADD COLUMN is_protected BOOLEAN NOT NULL DEFAULT 0"
            )

    if "food_items" in table_names:
        food_cols = {c["name"] for c in inspector.get_columns("food_items")}
        if "calories_per_serving" not in food_cols:
            statements.append(
                "ALTER TABLE food_items ADD COLUMN calories_per_serving INTEGER"
            )
        if "serving_size" not in food_cols:
            statements.append(
                "ALTER TABLE food_items ADD COLUMN serving_size VARCHAR(60)"
            )

    if "inventory_logs" in table_names:
        log_cols = {c["name"] for c in inspector.get_columns("inventory_logs")}
        if "warehouse_qty_after" not in log_cols:
            statements.append(
                "ALTER TABLE inventory_logs ADD COLUMN warehouse_qty_after INTEGER"
            )
        if "locker_qty_after" not in log_cols:
            statements.append(
                "ALTER TABLE inventory_logs ADD COLUMN locker_qty_after INTEGER"
            )

    # V3.1 cleaning workflow: date range + postpone/approve bookkeeping.
    backfill_cleaning_dates = False
    if "cleaning_sessions" in table_names:
        sess_cols = {c["name"] for c in inspector.get_columns("cleaning_sessions")}
        if "start_date" not in sess_cols:
            statements.append("ALTER TABLE cleaning_sessions ADD COLUMN start_date DATE")
            backfill_cleaning_dates = True
        if "end_date" not in sess_cols:
            statements.append("ALTER TABLE cleaning_sessions ADD COLUMN end_date DATE")
            backfill_cleaning_dates = True
        if "postpone_count" not in sess_cols:
            statements.append(
                "ALTER TABLE cleaning_sessions "
                "ADD COLUMN postpone_count INTEGER NOT NULL DEFAULT 0"
            )
        if "postpone_note" not in sess_cols:
            statements.append("ALTER TABLE cleaning_sessions ADD COLUMN postpone_note TEXT")
        if "last_postponed_at" not in sess_cols:
            statements.append("ALTER TABLE cleaning_sessions ADD COLUMN last_postponed_at DATETIME")
        if "approved_at" not in sess_cols:
            statements.append("ALTER TABLE cleaning_sessions ADD COLUMN approved_at DATETIME")
        if "approved_by_name" not in sess_cols:
            statements.append("ALTER TABLE cleaning_sessions ADD COLUMN approved_by_name VARCHAR(120)")

    # V3.3: source_type on distributions table (student self-pickup tracking).
    if "distributions" in table_names:
        dist_cols = {c["name"] for c in inspector.get_columns("distributions")}
        if "source_type" not in dist_cols:
            statements.append(
                "ALTER TABLE distributions ADD COLUMN source_type VARCHAR(30) "
                "DEFAULT 'staff_recorded'"
            )

    if not statements:
        return
    with db.engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        # Backfill the new date-range columns from the legacy single-day
        # `scheduled_date` so existing demo sessions render correctly.
        if backfill_cleaning_dates:
            conn.execute(text(
                "UPDATE cleaning_sessions "
                "SET start_date = scheduled_date "
                "WHERE start_date IS NULL"
            ))
            conn.execute(text(
                "UPDATE cleaning_sessions "
                "SET end_date = scheduled_date "
                "WHERE end_date IS NULL"
            ))
        # Migrate any pre-existing 'completed' sessions to the new 'approved'
        # terminal state so the UI keeps showing them as done.
        conn.execute(text(
            "UPDATE cleaning_sessions SET status = 'approved' "
            "WHERE status = 'completed'"
        ))


def create_app():
    app = Flask(__name__)

    # ----- Configuration -----
    app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
    db_path = os.path.join(app.instance_path, "app.db")
    os.makedirs(app.instance_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ----- Extensions -----
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ----- Blueprints -----
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(profile_bp)
    app.register_blueprint(announcements_bp, url_prefix="/announcements")
    app.register_blueprint(requests_bp, url_prefix="/requests")
    app.register_blueprint(borrowing_bp, url_prefix="/borrowing")
    app.register_blueprint(cleaning_bp, url_prefix="/cleaning")
    app.register_blueprint(resources_bp, url_prefix="/resources")

    # ----- Root route: redirect based on role -----
    @app.route("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.is_staff:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("student.dashboard"))

    # ----- Future-module placeholders (Coming soon) -----
    # NOTE: `announcements` and `requests` graduated to real modules in V2,
    # so they're no longer listed here. Their old `/coming-soon/...` URLs
    # still resolve to the generic "Coming soon" screen for backward compat,
    # but the sidebar links to the real pages now.
    @app.route("/coming-soon/<module>")
    @login_required
    def coming_soon(module):
        modules = {
            "borrowing": "Borrowing",
            "chat": "Common Group Chat",
            "cleaning": "Cleaning Sessions",
        }
        title = modules.get(module, "Coming soon")
        return render_template("coming_soon.html", module_title=title)

    # ----- Initialize DB, run additive migration, seed data -----
    with app.app_context():
        db.create_all()
        _migrate_schema()
        seed_database()

    return app


app = create_app()


if __name__ == "__main__":
    # Frontend served by Flask on port 5000, host 0.0.0.0 for Replit preview
    app.run(host="0.0.0.0", port=5000, debug=True)
