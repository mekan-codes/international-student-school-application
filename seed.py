"""
Seed/demo data. Runs at startup. Idempotent — safe to call repeatedly.
"""
from models import db, User, FoodItem, Resource


def _ensure_user(*, email, name, password, role, **extras):
    """Create the user if missing. If they already exist, don't overwrite
    custom data — but always re-apply security-sensitive flags from the
    seed (e.g. is_protected) so demo admins stay protected even if the
    DB pre-existed before that column was added."""
    user = User.query.filter_by(email=email).first()
    if user:
        if extras.get("is_protected"):
            user.is_protected = True
        return user
    user = User(name=name, email=email, role=role, **extras)
    user.set_password(password)
    db.session.add(user)
    return user


def seed_database() -> None:
    """Insert demo accounts and food items if not already present."""
    has_users = User.query.first() is not None

    # Users (idempotent: each one only created if missing)
    _ensure_user(
        email="admin@school.com", name="Admin User",
        password="admin123", role="admin",
        is_sub_food_member=False, is_protected=True,
    )
    _ensure_user(
        email="manager@school.com", name="Manager User",
        password="manager123", role="manager",
        is_sub_food_member=False,
    )
    _ensure_user(
        email="student1@school.com", name="Student One",
        password="student123", role="student", student_id="S001",
        is_sub_food_member=True,
    )
    _ensure_user(
        email="student2@school.com", name="Student Two",
        password="student123", role="student", student_id="S002",
        is_sub_food_member=False,
    )
    _ensure_user(
        email="student3@school.com", name="Student Three",
        password="student123", role="student", student_id="S003",
        is_sub_food_member=True,
    )

    # Food items: only seed if there are no users yet (true first-run).
    if not has_users and FoodItem.query.first() is None:
        db.session.add_all([
            FoodItem(name="chicken mayo", category="protein",
                     low_stock_threshold=2,
                     warehouse_quantity=20, locker_quantity=5),
            FoodItem(name="rice", category="grain",
                     low_stock_threshold=3,
                     warehouse_quantity=30, locker_quantity=8),
            FoodItem(name="noodles", category="grain",
                     low_stock_threshold=3,
                     warehouse_quantity=15, locker_quantity=2),
        ])

    # Resources: seed placeholder cards if the table is empty.
    # Flush first so the admin user is available for the FK.
    db.session.flush()
    if Resource.query.first() is None:
        admin = User.query.filter_by(role="admin").first()
        if admin:
            db.session.add_all([
                Resource(
                    title="Common Drive 1",
                    description="Shared lounge documents, forms, and reference "
                                "materials for everyday use.",
                    url="https://example.com/common-drive-1",
                    is_active=True,
                    created_by_user_id=admin.id,
                ),
                Resource(
                    title="Common Drive 2",
                    description="Photo archives, event recordings, and other "
                                "large media files for the lounge community.",
                    url="https://example.com/common-drive-2",
                    is_active=True,
                    created_by_user_id=admin.id,
                ),
            ])

    db.session.commit()
