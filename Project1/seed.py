from app import app
from config.database import db
from models.user import User
from models.employee import Employee
from models.enums import Role
from werkzeug.security import generate_password_hash
from util.helpers import generate_sequence

SEED_ACCOUNTS = [
    # (username,   email,                     password,        role,          full_name,      department,   designation)
    (
        "manager1",
        "manager1@company.com",
        "Manager@1234",
        Role.MANAGER,
        "Rajiv Kumar",
        "Operations",
        "Team Manager",
    ),
    (
        "manager2",
        "manager2@company.com",
        "Manager@1234",
        Role.MANAGER,
        "Anita Singh",
        "HR",
        "HR Manager",
    ),
    (
        "finance1",
        "finance1@company.com",
        "Finance@1234",
        Role.FINANCE,
        "Priya Sharma",
        "Finance",
        "Finance Officer",
    ),
    (
        "finance2",
        "finance2@company.com",
        "Finance@1234",
        Role.FINANCE,
        "Rahul Mehta",
        "Finance",
        "Senior Accountant",
    ),
    (
        "admin1",
        "admin1@company.com",
        "Admin@1234",
        Role.ADMIN,
        "System Admin",
        "IT",
        "Administrator",
    ),
]


def seed():
    with app.app_context():
        db.create_all()
        print("\n=== Seed Accounts ===")
        for username, email, password, role, full_name, dept, desig in SEED_ACCOUNTS:
            if User.query.filter_by(username=username).first():
                print(f"  [SKIP] {username!r} already exists")
                continue
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                role=role,
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()  # get user.id
            emp = Employee(
                user_id=user.id,
                emp_code=generate_sequence("EMP", Employee, "emp_code"),
                full_name=full_name,
                department=dept,
                designation=desig,
                grade="G5",
            )
            db.session.add(emp)
            db.session.commit()
            print(f"  [OK]   {role:<10}  username={username!r}   password={password!r}")
        print("=====================\n")
        print("Login URLs:")
        print("  Manager Portal : http://127.0.0.1:5000/auth/login?portal=manager")
        print("  Finance Portal : http://127.0.0.1:5000/auth/login?portal=finance")
        print("  Employee Portal: http://127.0.0.1:5000/auth/login?portal=user\n")


if __name__ == "__main__":
    seed()
