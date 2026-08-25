import os

# Force these even if a dao/config/app import earlier in a test module's import
# list already triggered python-dotenv to populate os.environ from .env first
# (dotenv only fills in unset keys, so a plain setdefault() here would lose the
# race and silently point tests at the dev database).
os.environ["DB_NAME"] = "travel_test"
os.environ["FLASK_DEBUG"] = "0"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unittest-suite"

import unittest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import app as flask_app
from config.database import db
from models.user import User
from models.employee import Employee
from models.expense_category import ExpenseCategory
from models.expense_policy import ExpensePolicy
from models.enums import Role

flask_app.config["TESTING"] = True
flask_app.config["JWT_COOKIE_CSRF_PROTECT"] = False
flask_app.config["WTF_CSRF_ENABLED"] = False

PASSWORD = "Test@1234"

PDF_BYTES = b"%PDF-1.4\n" + b"0" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64
BAD_MAGIC_BYTES_PDF_EXT = b"not-a-real-pdf" + b"0" * 64


class BaseTestCase(unittest.TestCase):
    """Shared unittest base. Runs against the real 'travel_test' MySQL database
    (same one tests/conftest.py's pytest fixtures target) so FK/unique constraints
    are exercised for real rather than mocked away."""

    @classmethod
    def setUpClass(cls):
        assert (
            "travel_test" in flask_app.config["SQLALCHEMY_DATABASE_URI"]
        ), "Refusing to run destructive tests against a non-test database"
        cls.app = flask_app
        with cls.app.app_context():
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            db.drop_all()
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            db.create_all()

    def setUp(self):
        # A fresh app context per test (rather than one shared for the whole
        # class) matters here: Flask's `g` lives on the app context, and the
        # test client reuses whatever app context is already active instead
        # of pushing its own. A class-wide context would let g.user from one
        # test's login leak into a later, unrelated request.
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.session.rollback()
        self._clean_tables()
        self._seed_baseline()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _clean_tables(self):
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    def _seed_baseline(self):
        pw = generate_password_hash(PASSWORD)

        self.admin_user = User(
            username="admin1",
            email="admin1@test.com",
            password_hash=pw,
            role=Role.ADMIN,
            is_active=True,
        )
        self.finance_user = User(
            username="fin1",
            email="fin1@test.com",
            password_hash=pw,
            role=Role.FINANCE,
            is_active=True,
        )
        self.manager_user = User(
            username="mgr1",
            email="mgr1@test.com",
            password_hash=pw,
            role=Role.MANAGER,
            is_active=True,
        )
        self.other_manager_user = User(
            username="mgr2",
            email="mgr2@test.com",
            password_hash=pw,
            role=Role.MANAGER,
            is_active=True,
        )
        self.employee_user = User(
            username="emp1",
            email="emp1@test.com",
            password_hash=pw,
            role=Role.EMPLOYEE,
            is_active=True,
        )
        self.other_employee_user = User(
            username="emp2",
            email="emp2@test.com",
            password_hash=pw,
            role=Role.EMPLOYEE,
            is_active=True,
        )
        db.session.add_all(
            [
                self.admin_user,
                self.finance_user,
                self.manager_user,
                self.other_manager_user,
                self.employee_user,
                self.other_employee_user,
            ]
        )
        db.session.commit()

        self.manager = Employee(
            user_id=self.manager_user.id,
            emp_code="M001",
            full_name="Manager One",
            department="IT",
            grade="G4",
            bank_account_no="1111222233",
            ifsc_code="HDFC0009999",
        )
        self.other_manager = Employee(
            user_id=self.other_manager_user.id,
            emp_code="M002",
            full_name="Manager Two",
            department="Sales",
            grade="G4",
            bank_account_no="4444555566",
            ifsc_code="ICIC0008888",
        )
        db.session.add_all([self.manager, self.other_manager])
        db.session.commit()

        # Bank details are set because /expense/new and /travel/new gate on
        # them; tests that specifically exercise that gate clear them first.
        self.employee = Employee(
            user_id=self.employee_user.id,
            emp_code="E001",
            full_name="Employee One",
            department="IT",
            grade="G3",
            manager_id=self.manager.id,
            bank_account_no="1234567890",
            ifsc_code="HDFC0001234",
        )
        self.other_employee = Employee(
            user_id=self.other_employee_user.id,
            emp_code="E002",
            full_name="Employee Two",
            department="Sales",
            grade="G3",
            manager_id=self.other_manager.id,
            bank_account_no="9876543210",
            ifsc_code="ICIC0004321",
        )
        db.session.add_all([self.employee, self.other_employee])
        db.session.commit()

        self.category = ExpenseCategory(
            code="TRAVEL",
            name="Travel",
            requires_receipt=False,
            default_limit=Decimal("2000.00"),
            is_active=True,
        )
        self.category_hotel = ExpenseCategory(
            code="HOTEL",
            name="Accommodation",
            requires_receipt=True,
            default_limit=Decimal("5000.00"),
            is_active=True,
        )
        db.session.add_all([self.category, self.category_hotel])
        db.session.commit()

        self.policy = ExpensePolicy(
            category_id=self.category.id,
            grade="G3",
            max_amount_per_day=Decimal("1500.00"),
            max_amount_per_claim=Decimal("3000.00"),
            receipt_required_above=Decimal("1000.00"),
            effective_from=date.today() - timedelta(days=30),
        )
        db.session.add(self.policy)
        db.session.commit()

    # -- HTTP helpers --
    def login(self, username, password=PASSWORD, portal="user"):
        return self.client.post(
            f"/auth/login?portal={portal}",
            data={"username": username, "password": password},
        )

    def login_json(self, username, password=PASSWORD, portal="user"):
        return self.client.post(
            f"/auth/login?portal={portal}",
            json={"username": username, "password": password},
        )

    def login_as_employee(self):
        return self.login("emp1", portal="user")

    def login_as_manager(self):
        return self.login("mgr1", portal="manager")

    def login_as_other_manager(self):
        return self.login("mgr2", portal="manager")

    def login_as_finance(self):
        return self.login("fin1", portal="finance")

    def login_as_admin(self):
        return self.login("admin1", portal="admin")


if __name__ == "__main__":
    unittest.main()
