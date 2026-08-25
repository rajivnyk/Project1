from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    g,
)
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
    get_jwt_identity,
)
from dao.user_dao import UserDAO
from dao.employee_dao import EmployeeDAO
from service.auth_service import AuthService
from models.enums import Role

# NOTE: jwt_required here is the local wrapper from util.jwt_decorators, not
# flask_jwt_extended's. It calls the flask_jwt_extended one and then loads
# g.user / g.employee, so every view below can rely on those being populated.
from util.jwt_decorators import jwt_required, jwt_role_required

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

user_dao = UserDAO()
emp_dao = EmployeeDAO()
auth_svc = AuthService(user_dao, emp_dao)

PORTAL_ROLES = {
    "user": Role.EMPLOYEE,
    "manager": Role.MANAGER,
    "finance": Role.FINANCE,
    "admin": Role.ADMIN,
}


def _home_for(role):
    """After login, redirect to the role-appropriate dashboard."""
    mapping = {
        Role.EMPLOYEE: "employee.dashboard",
        Role.MANAGER: "manager.dashboard",
        Role.FINANCE: "finance.dashboard",
        Role.ADMIN: "admin.users",
    }
    return url_for(mapping.get(role, "auth.home"))


def _set_auth_cookies(resp, access_token, refresh_token):
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp


def _clear_auth_cookies(resp):
    unset_jwt_cookies(resp)
    return resp


@auth_bp.route("/login", methods=["GET", "POST"])
@auth_bp.route("/login-page", methods=["GET"], endpoint="login_page")
def login():
    """
    GET  -> serves the portal login page based on the ?portal= param.
    POST -> authenticates and issues JWTs.
              JSON body : returns { access_token, refresh_token, user }
              Form body : sets HTTP-only cookies and redirects to the dashboard
    """
    portal = (request.args.get("portal") or "user").lower()

    if request.method == "GET":
        template_map = {
            "user": "login_user.html",
            "manager": "login_manager.html",
            "finance": "login_finance.html",
            "admin": "login_admin.html",
        }
        return render_template(
            template_map.get(portal, "login_user.html"), portal=portal
        )

    data = request.get_json(silent=True) if request.is_json else request.form
    data = data if data is not None else {}
    portal = (data.get("portal") or request.args.get("portal", "user")).lower()
    expected_role = PORTAL_ROLES.get(portal)

    try:
        user = auth_svc.authenticate(data.get("username"), data.get("password"))
    except ValueError as exc:
        if request.is_json:
            return jsonify({"message": str(exc)}), 401
        flash(str(exc), "danger")
        return redirect(url_for("auth.login", portal=portal))

    if expected_role and user.role not in (expected_role, Role.ADMIN):
        msg = f"This portal is for {expected_role} accounts. Your role is {user.role}."
        if request.is_json:
            return jsonify({"message": msg}), 403
        flash(msg, "danger")
        return redirect(url_for("auth.login", portal=portal))

    access = create_access_token(
        identity=str(user.id), additional_claims={"role": user.role}
    )
    refresh = create_refresh_token(identity=str(user.id))

    if request.is_json:
        return jsonify(
            {
                "message": "Login successful",
                "access_token": access,
                "refresh_token": refresh,
                "user": user.to_dict(),
            }
        )

    resp = redirect(_home_for(user.role))
    _set_auth_cookies(resp, access, refresh)
    flash(f"Welcome back, {user.username}!", "success")
    return resp


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Issues a new access token from a still-valid refresh token."""
    identity = get_jwt_identity()
    user = user_dao.get_by_id(int(identity))
    if not user or not user.is_active:
        return jsonify({"message": "Invalid user account."}), 401

    new_access = create_access_token(
        identity=identity, additional_claims={"role": user.role}
    )

    if request.is_json:
        return jsonify({"access_token": new_access, "message": "Token refreshed"})

    resp = jsonify({"message": "Token refreshed via cookie"})
    set_access_cookies(resp, new_access)
    return resp


@auth_bp.route("/logout")
def logout():
    resp = redirect(url_for("auth.login_page"))
    _clear_auth_cookies(resp)
    flash("You have been logged out.", "info")
    return resp


@auth_bp.route("/home")
@jwt_required
def home():
    return render_template("home.html", username=g.user.username, role=g.user.role)


@auth_bp.route("/me")
@jwt_required
def me():
    return jsonify(
        {
            "id": g.user.id,
            "username": g.user.username,
            "role": g.user.role,
            "employee": g.employee.to_dict() if g.employee else None,
        }
    )


@auth_bp.route("/manager/register", methods=["GET", "POST"])
@jwt_role_required("MANAGER", "ADMIN")
def manager_register():
    """Only MANAGER (or ADMIN) may create employee accounts."""
    if request.method == "POST":
        try:
            auth_svc.register(request.form, created_by_admin=True)
            flash("Employee registered successfully.", "success")
            return redirect(url_for("manager.dashboard"))
        except ValueError as exc:
            flash(str(exc), "danger")
    return render_template("manager_register.html", managers=emp_dao.get_all())


@auth_bp.route("/manager/remove/<int:emp_id>", methods=["POST"])
@jwt_role_required("MANAGER", "ADMIN")
def manager_remove_employee(emp_id):
    """Deactivates (soft-deletes) an employee - MANAGER / ADMIN only."""
    emp = emp_dao.get_by_id(emp_id)
    if emp is None:
        flash("Employee not found.", "danger")
        return redirect(url_for("manager.dashboard"))
    emp.is_active = False
    if emp.user:
        emp.user.is_active = False
    from config.database import db

    db.session.commit()
    flash(f"{emp.full_name} has been deactivated.", "success")
    return redirect(url_for("manager.dashboard"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@jwt_required
def change_password():
    if request.method == "GET":
        return render_template("change_password.html")

    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if new_password != confirm_password:
        flash("New passwords do not match", "danger")
        return redirect(url_for("auth.change_password"))

    try:
        auth_svc.change_password(g.user, old_password, new_password)
        flash("Password successfully updated. Please log in again.", "success")
        return redirect(url_for("auth.logout"))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("auth.change_password"))
