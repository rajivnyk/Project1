from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from dao.claim_dao import ClaimDAO
from dao.employee_dao import EmployeeDAO
from dao.travel_dao import TravelDAO
from dao.approval_dao import ApprovalDAO
from service.approval_service import ApprovalService
from service.travel_service import TravelService
from models.enums import ClaimStatus, Action
from util.jwt_decorators import jwt_role_required
from util.helpers import apply_item_reviews

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")

claim_dao, employee_dao, travel_dao = ClaimDAO(), EmployeeDAO(), TravelDAO()
approval_service = ApprovalService(ApprovalDAO())
travel_service = TravelService(travel_dao, ApprovalDAO())


@manager_bp.route("/dashboard")
@jwt_role_required("MANAGER", "ADMIN")
def dashboard():
    if g.employee is None:
        flash("No employee profile is linked to your account.", "danger")
        return redirect(url_for("auth.home"))
    ids = employee_dao.reportee_ids(g.employee.id)
    return render_template(
        "manager_dashboard.html",
        claims=claim_dao.get_pending_for_manager(ids, ClaimStatus.SUBMITTED),
        trips=travel_dao.get_pending_for_manager(ids),
        team=employee_dao.get_reportees(g.employee.id),
    )


@manager_bp.route("/claim/<int:claim_id>/decide", methods=["POST"])
@jwt_role_required("MANAGER", "ADMIN")
def decide_claim(claim_id):
    approve = request.form.get("decision") == "approve"
    try:
        claim = claim_dao.get_by_id(claim_id)
        if claim is None:
            raise ValueError("Claim not found")
        approval_service.assert_is_manager_of(g.employee, claim)
        if approve:
            apply_item_reviews(request.form, claim, default_to_claimed=True)
            from config.database import db

            db.session.commit()
        approval_service.transition(
            claim,
            ClaimStatus.MANAGER_APPROVED if approve else ClaimStatus.MANAGER_REJECTED,
            g.user,
            Action.APPROVED if approve else Action.REJECTED,
            comments=request.form.get("comments"),
        )
        flash(
            f"Claim {claim.claim_no} {'approved' if approve else 'rejected'}.",
            "success",
        )
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("manager.dashboard"))


@manager_bp.route("/travel/<int:request_id>/decide", methods=["POST"])
@jwt_role_required("MANAGER", "ADMIN")
def decide_travel(request_id):
    try:
        travel_service.decide(
            request_id,
            g.employee,
            g.user,
            request.form.get("decision") == "approve",
            request.form.get("remarks"),
        )
        flash("Travel request updated.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("manager.dashboard"))
