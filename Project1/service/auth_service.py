from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config.database import db
from models.user import User
from models.employee import Employee
from models.enums import Role
from util.helpers import generate_sequence

MAX_ATTEMPTS = 5


class AuthService:
    def __init__(self, user_dao, employee_dao):
        self.user_dao = user_dao
        self.employee_dao = employee_dao

    def _hash_password(self, raw_password):
        return generate_password_hash(raw_password, method="pbkdf2:sha256")

    def _verify_password(self, user, raw_password):
        return check_password_hash(user.password_hash, raw_password)

    def authenticate(self, username, password):
        if not username or not password:
            raise ValueError("Username and password are required")
        user = self.user_dao.get_by_username(username) or self.user_dao.get_by_email(
            username
        )
        if user is None or not self._verify_password(user, password):
            if user is not None:
                user.failed_attempts += 1
                if user.failed_attempts >= MAX_ATTEMPTS:
                    user.is_active = False
                self.user_dao.update()
            raise ValueError("Invalid username or password")
        if not user.is_active:
            raise ValueError("Account locked. Contact the administrator.")
        user.failed_attempts = 0
        user.last_login_at = datetime.utcnow()
        self.user_dao.update()
        return user

    def register(self, data, created_by_admin=False):
        username = (data.get("username") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        if not username:
            raise ValueError("Username is required")
        if not email or "@" not in email:
            raise ValueError("A valid email is required")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if password != data.get("confirm_password", password):
            raise ValueError("Passwords do not match")
        if self.user_dao.get_by_username(username):
            raise ValueError("That username is already taken")
        if self.user_dao.get_by_email(email):
            raise ValueError("That email is already registered")
        role = data.get("role", Role.EMPLOYEE)
        if role not in Role.ALL:
            raise ValueError("Invalid role")
        if role != Role.EMPLOYEE and not created_by_admin:
            raise ValueError("Only an administrator may create that role")
        manager_id = data.get("manager_id") or None
        if manager_id:
            manager_employee = self.employee_dao.get_by_id(manager_id)
            if manager_employee is None:
                raise ValueError("Selected reporting manager was not found")
            manager_role = manager_employee.user.role if manager_employee.user else None
            if manager_role not in (Role.MANAGER, Role.ADMIN):
                raise ValueError(
                    f"{manager_employee.full_name} cannot be set as a reporting manager "
                    f"(role is {manager_role or 'unknown'}). Only MANAGER or ADMIN accounts "
                    "may be selected as a reporting manager."
                )
            if manager_employee.is_active is False:
                raise ValueError(
                    f"{manager_employee.full_name} is an inactive account and cannot be assigned as a reporting manager"
                )
        user = User(
            username=username,
            email=email,
            role=role,
            password_hash=self._hash_password(password),
        )
        db.session.add(user)
        db.session.flush()
        employee = Employee(
            user_id=user.id,
            emp_code=generate_sequence("EMP", Employee, "emp_code"),
            full_name=(data.get("full_name") or "").strip() or "Unnamed",
            department=(data.get("department") or "General").strip(),
            designation=data.get("designation"),
            grade=data.get("grade", "G3"),
            manager_id=manager_id,
            contact_number=data.get("contact_number"),
        )
        db.session.add(employee)
        db.session.commit()
        return user

    def change_password(self, user, old_password, new_password):
        if not old_password or not new_password:
            raise ValueError("Both the current and the new password are required")
        if not self._verify_password(user, old_password):
            raise ValueError("Current password is incorrect")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")
        if new_password == old_password:
            raise ValueError("The new password must be different from the current one")
        user.password_hash = self._hash_password(new_password)
        self.user_dao.update()
        return True
