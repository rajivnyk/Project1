from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from dao.claim_dao import ClaimDAO
from dao.travel_dao import TravelDAO
from dao.employee_dao import EmployeeDAO
from service.report_service import ReportService
from service.employee_service import EmployeeService
from util.jwt_decorators import jwt_role_required, jwt_required

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")

claim_dao, travel_dao, employee_dao = ClaimDAO(), TravelDAO(), EmployeeDAO()
report_service = ReportService(claim_dao)
employee_service = EmployeeService(employee_dao)


@employee_bp.route("/dashboard")
@jwt_role_required("EMPLOYEE", "MANAGER")
def dashboard():
    if g.employee is None:
        flash("No employee profile is linked to your account.", "danger")
        return redirect(url_for("auth.home"))
    return render_template(
        "dashboard_employee.html",
        summary=report_service.employee_summary(g.employee.id),
        recent=claim_dao.get_by_employee(g.employee.id)[:5],
        trips=travel_dao.get_by_employee(g.employee.id)[:5],
    )


@employee_bp.route("/profile", methods=["GET", "POST"])
@jwt_required
def profile():
    if g.employee is None:
        flash("No employee profile is linked to your account.", "warning")
        return redirect(url_for("auth.home"))
    if request.method == "POST":
        try:
            employee_service.update_profile(g.employee, request.form)
            flash("Profile updated.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("employee.profile"))
    return render_template("profile.html", employee=g.employee)
