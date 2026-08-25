from flask import Blueprint, render_template, request, redirect, url_for, flash
from dao.user_dao import UserDAO
from dao.employee_dao import EmployeeDAO
from dao.category_dao import CategoryDAO
from dao.policy_dao import PolicyDAO
from service.auth_service import AuthService
from models.expense_policy import ExpensePolicy
from util.jwt_decorators import jwt_role_required
from util.validators import require, to_decimal

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

user_dao, employee_dao = UserDAO(), EmployeeDAO()
category_dao, policy_dao = CategoryDAO(), PolicyDAO()
auth_service = AuthService(user_dao, employee_dao)


@admin_bp.route("/users")
@jwt_role_required("ADMIN")
def users():
    return render_template(
        "admin_users.html", users=user_dao.get_all(), employees=employee_dao.get_all()
    )


@admin_bp.route("/users/create", methods=["POST"])
@jwt_role_required("ADMIN")
def create_user():
    try:
        auth_service.register(request.form, created_by_admin=True)
        flash("User created.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@jwt_role_required("ADMIN")
def toggle_user(user_id):
    user = user_dao.get_by_id(user_id)
    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for("admin.users"))
    user.is_active = not user.is_active
    user.failed_attempts = 0
    user_dao.update()
    flash(
        f"{user.username} is now {'active' if user.is_active else 'disabled'}.", "info"
    )
    return redirect(url_for("admin.users"))


@admin_bp.route("/policies", methods=["GET", "POST"])
@jwt_role_required("ADMIN")
def policies():
    if request.method == "POST":
        try:
            category_id = int(require(request.form.get("category_id"), "Category"))
            if category_dao.get_by_id(category_id) is None:
                raise ValueError("Category not found")
            policy_dao.save(
                ExpensePolicy(
                    category_id=category_id,
                    grade=require(request.form.get("grade"), "Grade"),
                    max_amount_per_day=to_decimal(
                        request.form.get("max_amount_per_day"), "Max amount per day"
                    ),
                    max_amount_per_claim=to_decimal(
                        request.form.get("max_amount_per_claim"), "Max amount per claim"
                    ),
                    receipt_required_above=to_decimal(
                        request.form.get("receipt_required_above") or 0,
                        "Receipt required above",
                        min_value=0,
                    ),
                )
            )
            flash("Policy saved.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("admin.policies"))
    return render_template(
        "admin_policies.html",
        policies=policy_dao.get_all(),
        categories=category_dao.get_active(),
    )
