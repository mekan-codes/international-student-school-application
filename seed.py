"""
Seed/demo data. Runs once at startup if the database is empty.
"""
from models import db, User, FoodItem


def seed_database() -> None:
    """Insert demo accounts and food items if none exist yet."""
    if User.query.first():
        return  # already seeded

    # ----- Users -----
    admin = User(name="Admin User", email="admin@school.com",
                 role="admin", is_sub_food_member=False)
    admin.set_password("admin123")

    s1 = User(name="Student One", student_id="S001",
              email="student1@school.com", role="student",
              is_sub_food_member=True)
    s1.set_password("student123")

    s2 = User(name="Student Two", student_id="S002",
              email="student2@school.com", role="student",
              is_sub_food_member=False)
    s2.set_password("student123")

    s3 = User(name="Student Three", student_id="S003",
              email="student3@school.com", role="student",
              is_sub_food_member=True)
    s3.set_password("student123")

    db.session.add_all([admin, s1, s2, s3])

    # ----- Food items with starting inventory -----
    foods = [
        FoodItem(name="chicken mayo", category="protein",
                 low_stock_threshold=2,
                 warehouse_quantity=20, locker_quantity=5),
        FoodItem(name="rice", category="grain",
                 low_stock_threshold=3,
                 warehouse_quantity=30, locker_quantity=8),
        FoodItem(name="noodles", category="grain",
                 low_stock_threshold=3,
                 warehouse_quantity=15, locker_quantity=2),
    ]
    db.session.add_all(foods)

    db.session.commit()
