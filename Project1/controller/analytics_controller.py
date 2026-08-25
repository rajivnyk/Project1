from flask import Blueprint, render_template, jsonify, g, request
from dao.employee_dao import EmployeeDAO
from service.analytics_service import AnalyticsService
from util.jwt_decorators import jwt_required

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")
api_bp = Blueprint("analytics_api", __name__, url_prefix="/api/analytics")

employee_dao = EmployeeDAO()
analytics_service = AnalyticsService()


def _scope_ids():
    """Return (employee_ids or None, is_company_wide) for the current user.

    None means "no filter" (company-wide). An empty list means "nothing is
    visible", which is what a user without a linked employee record gets.
    """
    role = g.user.role
    if role in ("FINANCE", "ADMIN"):
        return None, True
    if g.employee is None:
        return [], False
    if role == "MANAGER":
        ids = employee_dao.reportee_ids(g.employee.id)
        ids.append(g.employee.id)
        return ids, False
    return [g.employee.id], False


@analytics_bp.route("/")
@jwt_required
def dashboard():
    return render_template("analytics.html", role=g.user.role)


@api_bp.route("/spend-by-category")
@jwt_required
def spend_by_category():
    ids, _ = _scope_ids()
    return jsonify(analytics_service.spend_by_category(ids))


@api_bp.route("/monthly-trend")
@jwt_required
def monthly_trend():
    ids, _ = _scope_ids()
    months = request.args.get("months", 6, type=int)
    if months < 1:
        months = 1
    return jsonify(analytics_service.monthly_trend(ids, months=months))


@api_bp.route("/policy-violations")
@jwt_required
def policy_violations():
    ids, _ = _scope_ids()
    return jsonify(analytics_service.policy_violation_breakdown(ids))


@api_bp.route("/turnaround")
@jwt_required
def turnaround():
    ids, _ = _scope_ids()
    return jsonify(analytics_service.turnaround_stats(ids))


@api_bp.route("/top-spenders")
@jwt_required
def top_spenders():
    if g.user.role not in ("FINANCE", "ADMIN"):
        return jsonify(error="Forbidden for this role."), 403
    limit = request.args.get("limit", 8, type=int)
    if limit < 1:
        limit = 1
    return jsonify(analytics_service.top_spenders(limit=limit))


@api_bp.route("/overdue")
@jwt_required
def overdue():
    if g.user.role == "EMPLOYEE":
        return jsonify(error="Forbidden for this role."), 403
    ids, _ = _scope_ids()
    return jsonify(analytics_service.overdue_approvals(ids))


@api_bp.route("/budget-utilization")
@jwt_required
def budget_utilization():
    if not g.employee:
        return jsonify([])
    return jsonify(analytics_service.budget_utilization(g.employee))
