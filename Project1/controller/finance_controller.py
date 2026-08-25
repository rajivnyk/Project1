import csv
import io
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    g,
    Response,
)
from dao.claim_dao import ClaimDAO
from dao.reimbursement_dao import ReimbursementDAO
from dao.approval_dao import ApprovalDAO
from service.finance_service import FinanceService
from service.approval_service import ApprovalService
from service.report_service import ReportService
from models.enums import ClaimStatus
from util.jwt_decorators import jwt_role_required
from util.helpers import apply_item_reviews

finance_bp = Blueprint("finance", __name__, url_prefix="/finance")

claim_dao = ClaimDAO()
approval_service = ApprovalService(ApprovalDAO())
finance_service = FinanceService(claim_dao, ReimbursementDAO(), approval_service)
report_service = ReportService(claim_dao)


@finance_bp.route("/dashboard")
@jwt_role_required("FINANCE", "ADMIN")
def dashboard():
    return render_template(
        "finance_dashboard.html",
        pending=finance_service.pending_verification(),
        ready=claim_dao.get_by_status(ClaimStatus.FINANCE_VERIFIED),
        breakdown=report_service.category_breakdown(),
    )


@finance_bp.route("/claim/<int:claim_id>/verify", methods=["POST"])
@jwt_role_required("FINANCE")
def verify(claim_id):
    try:
        approve = request.form.get("decision") == "approve"
        if approve:
            claim = claim_dao.get_by_id(claim_id)
            if claim is None:
                raise ValueError("Claim not found")
            apply_item_reviews(request.form, claim, default_to_claimed=False)
            from config.database import db

            db.session.commit()
        finance_service.verify(claim_id, g.user, approve, request.form.get("comments"))
        flash("Verification recorded.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("finance.dashboard"))


@finance_bp.route("/claim/<int:claim_id>/reimburse", methods=["POST"])
@jwt_role_required("FINANCE")
def reimburse(claim_id):
    try:
        r = finance_service.process_reimbursement(claim_id, g.user, request.form)
        flash(
            f"Reimbursement {r.reference_no} of Rs.{r.approved_amount} recorded.",
            "success",
        )
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("finance.dashboard"))


@finance_bp.route("/search")
@jwt_role_required("FINANCE", "ADMIN")
def search():
    page = claim_dao.search(
        keyword=request.args.get("q"),
        status=request.args.get("status"),
        page=request.args.get("page", 1, type=int),
    )
    return render_template("search_claims.html", page=page, args=request.args)


@finance_bp.route("/search/export.csv")
@jwt_role_required("FINANCE", "ADMIN")
def search_csv():
    """Export every claim matching the current search filters as a CSV file,
    not just the current page -- handy for reconciliation outside the app."""
    all_matches = claim_dao.search(
        keyword=request.args.get("q"),
        status=request.args.get("status"),
        page=1,
        per_page=100000,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Claim No",
            "Employee",
            "Department",
            "Title",
            "Claim Date",
            "Total Amount",
            "Status",
            "Policy Flag",
            "Violation Count",
            "Submitted At",
        ]
    )
    for c in all_matches.items:
        writer.writerow(
            [
                c.claim_no,
                c.employee.full_name,
                c.employee.department,
                c.title,
                c.claim_date,
                c.total_amount,
                c.status,
                "Yes" if c.policy_flag else "No",
                c.violation_count,
                c.submitted_at or "",
            ]
        )
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=claims_export.csv"},
    )
