import os

os.environ["DB_NAME"] = "travel_test"
os.environ["FLASK_DEBUG"] = "0"
os.environ["JWT_SECRET_KEY"] = "test"

import pytest
from app import app
from config.database import db
from models.user import User
from models.employee import Employee
from models.enums import Role
from werkzeug.security import generate_password_hash
from sqlalchemy import text


@pytest.fixture(scope="session")
def test_app():
    # Make sure we're using travel_test
    assert "travel_test" in app.config["SQLALCHEMY_DATABASE_URI"]

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False

    with app.app_context():
        # Drop all and create all
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        db.drop_all()
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        db.create_all()
        yield app


@pytest.fixture
def client(test_app):
    return test_app.test_client()


@pytest.fixture
def test_db(test_app):
    with test_app.app_context():
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        yield db
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def seeded_db(test_db):
    pw_hash = generate_password_hash("Test@1234")

    u1 = User(
        username="emp1",
        email="emp1@test.com",
        password_hash=pw_hash,
        role=Role.EMPLOYEE,
        is_active=True,
    )
    u2 = User(
        username="mgr1",
        email="mgr1@test.com",
        password_hash=pw_hash,
        role=Role.MANAGER,
        is_active=True,
    )
    u3 = User(
        username="fin1",
        email="fin1@test.com",
        password_hash=pw_hash,
        role=Role.FINANCE,
        is_active=True,
    )

    test_db.session.add_all([u1, u2, u3])
    test_db.session.commit()

    e1 = Employee(
        user_id=u1.id, emp_code="E001", full_name="Employee One", department="IT"
    )
    e2 = Employee(
        user_id=u2.id, emp_code="M001", full_name="Manager One", department="IT"
    )
    test_db.session.add_all([e1, e2])
    test_db.session.commit()

    e1.manager_id = e2.id
    test_db.session.commit()

    return test_db


@pytest.fixture
def logged_in_employee(client, seeded_db):
    client.post(
        "/auth/login?portal=user", data={"username": "emp1", "password": "Test@1234"}
    )
    return client
