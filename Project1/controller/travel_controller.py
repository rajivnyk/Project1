from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from dao.travel_dao import TravelDAO
from dao.approval_dao import ApprovalDAO
from service.travel_service import TravelService
from models.enums import TravelStatus
from util.jwt_decorators import jwt_role_required

travel_bp = Blueprint("travel", __name__, url_prefix="/travel")

travel_dao = TravelDAO()
travel_service = TravelService(travel_dao, ApprovalDAO())


def _banking_incomplete():
    """True when the logged-in user has no employee record or no bank details."""
    return (
        g.employee is None or not g.employee.bank_account_no or not g.employee.ifsc_code
    )


@travel_bp.route("/new", methods=["GET", "POST"])
@jwt_role_required("EMPLOYEE", "MANAGER")
def new_request():
    if _banking_incomplete():
        flash(
            "You must complete your banking details in your profile before requesting travel.",
            "warning",
        )
        return redirect(url_for("employee.profile"))
    if request.method == "POST":
        try:
            tr = travel_service.create(g.employee, request.form)
            if tr.status == TravelStatus.APPROVED:
                flash(
                    f"Travel request {tr.request_no} auto-approved (no manager assigned).",
                    "success",
                )
            else:
                flash(
                    f"Travel request {tr.request_no} submitted for manager approval.",
                    "success",
                )
            return redirect(url_for("travel.my_requests"))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template("travel_request_form.html")


@travel_bp.route("/my-requests")
@jwt_role_required("EMPLOYEE", "MANAGER")
def my_requests():
    if g.employee is None:
        flash("No employee profile is linked to your account.", "danger")
        return redirect(url_for("auth.home"))
    return render_template(
        "travel_list.html", requests=travel_dao.get_by_employee(g.employee.id)
    )


@travel_bp.route("/<int:request_id>/cancel", methods=["POST"])
@jwt_role_required("EMPLOYEE", "MANAGER")
def cancel(request_id):
    try:
        tr = travel_service.cancel(
            request_id, g.employee, g.user, request.form.get("reason")
        )
        flash(f"{tr.request_no} has been cancelled.", "info")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("travel.my_requests"))
