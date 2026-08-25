from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from dao.claim_dao import ClaimDAO
from dao.item_dao import ItemDAO
from dao.category_dao import CategoryDAO
from dao.policy_dao import PolicyDAO
from dao.approval_dao import ApprovalDAO
from dao.travel_dao import TravelDAO
from dao.receipt_dao import ReceiptDAO
from service.expense_service import ExpenseService
from service.policy_service import PolicyService
from service.approval_service import ApprovalService
from service.file_service import FileService
from service.analytics_service import AnalyticsService
from models.enums import ClaimStatus
from util.jwt_decorators import jwt_role_required, jwt_required

expense_bp = Blueprint("expense", __name__, url_prefix="/expense")

claim_dao, item_dao, category_dao = ClaimDAO(), ItemDAO(), CategoryDAO()
policy_service = PolicyService(PolicyDAO(), item_dao)
approval_service = ApprovalService(ApprovalDAO())
expense_service = ExpenseService(
    claim_dao, item_dao, category_dao, policy_service, approval_service
)
file_service = FileService(ReceiptDAO())
travel_dao = TravelDAO()
analytics_service = AnalyticsService()


def _banking_incomplete():
    """True when the logged-in user has no employee record or no bank details."""
    return (
        g.employee is None or not g.employee.bank_account_no or not g.employee.ifsc_code
    )


@expense_bp.route("/new", methods=["GET", "POST"])
@jwt_role_required("EMPLOYEE", "MANAGER")
def new_claim():
    if _banking_incomplete():
        flash(
            "You must complete your banking details in your profile before submitting expenses.",
            "warning",
        )
        return redirect(url_for("employee.profile"))
    if request.method == "POST":
        try:
            claim = expense_service.create_claim(g.employee, request.form)
            flash(f"Claim {claim.claim_no} created. Now add your expenses.", "success")
            return redirect(url_for("expense.edit_claim", claim_id=claim.id))
        except ValueError as e:
            flash(str(e), "danger")
    return render_template(
        "expense_form.html", trips=travel_dao.get_approved_for_employee(g.employee.id)
    )


@expense_bp.route("/<int:claim_id>/edit")
@jwt_role_required("EMPLOYEE", "MANAGER")
def edit_claim(claim_id):
    try:
        claim = expense_service.get_owned_claim(claim_id, g.employee)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("expense.my_claims"))
    return render_template(
        "claim_edit.html",
        claim=claim,
        categories=category_dao.get_active(),
        is_editable=expense_service.is_editable(claim),
    )


@expense_bp.route("/<int:claim_id>/item/add", methods=["POST"])
@jwt_role_required("EMPLOYEE", "MANAGER")
def add_item(claim_id):
    try:
        claim = expense_service.get_owned_claim(
            claim_id, g.employee, editable_only=True
        )
        expense_service.add_item(claim, request.form)
        flash("Expense added.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("expense.edit_claim", claim_id=claim_id))


@expense_bp.route("/<int:claim_id>/item/<int:item_id>/delete", methods=["POST"])
@jwt_role_required("EMPLOYEE", "MANAGER")
def delete_item(claim_id, item_id):
    try:
        claim = expense_service.get_owned_claim(
            claim_id, g.employee, editable_only=True
        )
        expense_service.delete_item(claim, item_id)
        flash("Expense removed.", "info")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("expense.edit_claim", claim_id=claim_id))


@expense_bp.route("/<int:claim_id>/receipt", methods=["POST"])
@jwt_role_required("EMPLOYEE", "MANAGER")
def upload_receipt(claim_id):
    try:
        claim = expense_service.get_owned_claim(
            claim_id, g.employee, editable_only=True
        )
        file_service.save_receipt(
            request.files.get("receipt"), claim, request.form.get("item_id"), g.user
        )
        flash("Receipt uploaded.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("expense.edit_claim", claim_id=claim_id))


@expense_bp.route("/<int:claim_id>/submit", methods=["POST"])
@jwt_role_required("EMPLOYEE", "MANAGER")
def submit(claim_id):
    try:
        claim = expense_service.submit_claim(claim_id, g.employee, g.user)
        if claim.status == ClaimStatus.MANAGER_APPROVED:
            flash(f"{claim.claim_no} submitted directly to Finance.", "success")
        else:
            flash(f"{claim.claim_no} submitted to your manager.", "success")
        return redirect(url_for("expense.my_claims"))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("expense.edit_claim", claim_id=claim_id))


@expense_bp.route("/<int:claim_id>/cancel", methods=["POST"])
@jwt_role_required("EMPLOYEE", "MANAGER")
def cancel(claim_id):
    try:
        claim = expense_service.cancel_claim(
            claim_id, g.employee, g.user, request.form.get("reason")
        )
        flash(f"{claim.claim_no} has been cancelled.", "info")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("expense.my_claims"))


@expense_bp.route("/my-claims")
@jwt_role_required("EMPLOYEE", "MANAGER")
def my_claims():
    if g.employee is None:
        flash("No employee profile is linked to your account.", "danger")
        return redirect(url_for("auth.home"))
    return render_template(
        "my_claims.html",
        claims=expense_service.my_claims(g.employee, request.args.get("status")),
    )


@expense_bp.route("/<int:claim_id>")
@jwt_required
def detail(claim_id):
    try:
        claim = expense_service.claim_detail(claim_id, g.user, g.employee)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("expense.my_claims"))
    duplicate_warnings = analytics_service.find_possible_duplicates(claim)
    return render_template(
        "claim_detail.html", claim=claim, duplicate_warnings=duplicate_warnings
    )


@expense_bp.route("/receipt/<int:receipt_id>/download")
@jwt_required
def download_receipt(receipt_id):
    try:
        return file_service.download(receipt_id, g.user, g.employee)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("expense.my_claims"))
