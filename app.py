"""
International Lounge — Main Application Entry Point
Version 1: Substitute Food Management Module
"""
import os
from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, current_user, login_required

from models import db, User
from auth import auth_bp
from admin import admin_bp
from student import student_bp
from profile import profile_bp
from seed import seed_database


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
        return User.query.get(int(user_id))

    # ----- Blueprints -----
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(profile_bp)

    # ----- Root route: redirect based on role -----
    @app.route("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("student.dashboard"))

    # ----- Future-module placeholders (Coming soon) -----
    @app.route("/coming-soon/<module>")
    @login_required
    def coming_soon(module):
        modules = {
            "borrowing": "Borrowing",
            "requests": "Requests to International Department",
            "announcements": "Announcements",
            "chat": "Common Group Chat",
            "cleaning": "Cleaning Sessions",
        }
        title = modules.get(module, "Coming soon")
        return render_template("coming_soon.html", module_title=title)

    # ----- Initialize DB and seed data -----
    with app.app_context():
        db.create_all()
        seed_database()

    return app


app = create_app()


if __name__ == "__main__":
    # Frontend served by Flask on port 5000, host 0.0.0.0 for Replit preview
    app.run(host="0.0.0.0", port=5000, debug=True)
