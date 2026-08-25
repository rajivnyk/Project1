from flask import Blueprint, render_template, g
from dao.claim_dao import ClaimDAO
from service.report_service import ReportService
from util.jwt_decorators import jwt_required

report_bp = Blueprint("report", __name__, url_prefix="/reports")

report_service = ReportService(ClaimDAO())


@report_bp.route("/")
@jwt_required
def index():
    if g.user.role in ("FINANCE", "ADMIN"):
        scope = None
    elif g.employee is None:
        scope = -1  # matches no employee, so the report comes back empty
    else:
        scope = g.employee.id
    return render_template(
        "reports.html", breakdown=report_service.category_breakdown(scope)
    )
