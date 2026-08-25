from datetime import datetime, timedelta, date
from decimal import Decimal
from config.database import db
from models.expense_claim import ExpenseClaim
from models.expense_item import ExpenseItem
from models.expense_category import ExpenseCategory
from models.employee import Employee
from models.approval_history import ApprovalHistory
from models.expense_policy import ExpensePolicy
from models.enums import ClaimStatus


def _scoped(query, employee_ids, employee_col):
    if employee_ids is not None:
        query = query.filter(employee_col.in_(employee_ids))
    return query


class AnalyticsService:
    def spend_by_category(self, employee_ids=None):
        q = (
            db.session.query(
                ExpenseCategory.name,
                db.func.count(ExpenseItem.id),
                db.func.coalesce(db.func.sum(ExpenseItem.amount_in_base), 0),
            )
            .join(ExpenseItem, ExpenseItem.category_id == ExpenseCategory.id)
            .join(ExpenseClaim, ExpenseItem.claim_id == ExpenseClaim.id)
            .filter(ExpenseClaim.status != ClaimStatus.CANCELLED)
        )
        q = _scoped(q, employee_ids, ExpenseClaim.employee_id)
        rows = (
            q.group_by(ExpenseCategory.name)
            .order_by(db.func.sum(ExpenseItem.amount_in_base).desc())
            .all()
        )
        return [{"category": n, "count": c, "amount": float(a)} for n, c, a in rows]

    def monthly_trend(self, employee_ids=None, months=6):
        cutoff = date.today().replace(day=1)
        for _ in range(months - 1):
            cutoff = (cutoff.replace(day=1) - timedelta(days=1)).replace(day=1)
        month_expr = db.func.date_format(ExpenseClaim.claim_date, "%Y-%m")
        q = db.session.query(
            month_expr,
            db.func.count(db.distinct(ExpenseClaim.id)),
            db.func.coalesce(db.func.sum(ExpenseClaim.total_amount), 0),
        ).filter(
            ExpenseClaim.claim_date >= cutoff,
            ExpenseClaim.status != ClaimStatus.CANCELLED,
        )
        q = _scoped(q, employee_ids, ExpenseClaim.employee_id)
        rows = q.group_by(month_expr).order_by(month_expr).all()
        return [{"month": m, "count": c, "amount": float(a)} for m, c, a in rows]

    def top_spenders(self, limit=8):
        rows = (
            db.session.query(
                Employee.full_name,
                Employee.department,
                db.func.count(db.distinct(ExpenseClaim.id)),
                db.func.coalesce(db.func.sum(ExpenseClaim.total_amount), 0),
            )
            .join(ExpenseClaim, ExpenseClaim.employee_id == Employee.id)
            .filter(ExpenseClaim.status != ClaimStatus.CANCELLED)
            .group_by(Employee.id)
            .order_by(db.func.sum(ExpenseClaim.total_amount).desc())
            .limit(limit)
            .all()
        )
        return [
            {"employee": n, "department": d, "claims": c, "amount": float(a)}
            for n, d, c, a in rows
        ]

    def policy_violation_breakdown(self, employee_ids=None):
        q = (
            db.session.query(ExpenseCategory.name, db.func.count(ExpenseItem.id))
            .join(ExpenseItem, ExpenseItem.category_id == ExpenseCategory.id)
            .join(ExpenseClaim, ExpenseItem.claim_id == ExpenseClaim.id)
            .filter(ExpenseItem.policy_violation.is_(True))
        )
        q = _scoped(q, employee_ids, ExpenseClaim.employee_id)
        rows = (
            q.group_by(ExpenseCategory.name)
            .order_by(db.func.count(ExpenseItem.id).desc())
            .all()
        )
        return [{"category": n, "violations": c} for n, c in rows]

    def turnaround_stats(self, employee_ids=None):
        q = (
            db.session.query(ApprovalHistory, ExpenseClaim.employee_id)
            .join(ExpenseClaim, ApprovalHistory.claim_id == ExpenseClaim.id)
            .filter(ApprovalHistory.entity_type == "CLAIM")
        )
        q = _scoped(q, employee_ids, ExpenseClaim.employee_id)
        by_claim = {}
        for hist, emp_id in q.all():
            by_claim.setdefault(hist.claim_id, {})[hist.new_status] = hist.acted_at
        mgr_hours, fin_hours = [], []
        for cid, stages in by_claim.items():
            submitted = stages.get(ClaimStatus.SUBMITTED)
            mgr_decided = stages.get(ClaimStatus.MANAGER_APPROVED) or stages.get(
                ClaimStatus.MANAGER_REJECTED
            )
            fin_decided = stages.get(ClaimStatus.FINANCE_VERIFIED) or stages.get(
                ClaimStatus.FINANCE_REJECTED
            )
            if submitted and mgr_decided:
                mgr_hours.append((mgr_decided - submitted).total_seconds() / 3600)
            if stages.get(ClaimStatus.MANAGER_APPROVED) and fin_decided:
                fin_hours.append(
                    (fin_decided - stages[ClaimStatus.MANAGER_APPROVED]).total_seconds()
                    / 3600
                )

        def avg(vals):
            return round(sum(vals) / len(vals), 1) if vals else None

        return {
            "avg_manager_decision_hours": avg(mgr_hours),
            "manager_decisions_counted": len(mgr_hours),
            "avg_finance_decision_hours": avg(fin_hours),
            "finance_decisions_counted": len(fin_hours),
        }

    def overdue_approvals(
        self, employee_ids=None, manager_sla_hours=48, finance_sla_hours=48
    ):
        now = datetime.utcnow()
        results = []
        q = ExpenseClaim.query.filter(ExpenseClaim.status == ClaimStatus.SUBMITTED)
        q = _scoped(q, employee_ids, ExpenseClaim.employee_id)
        for c in q.all():
            if c.submitted_at:
                hours = (now - c.submitted_at).total_seconds() / 3600
                if hours > manager_sla_hours:
                    results.append(
                        {
                            "claim_no": c.claim_no,
                            "claim_id": c.id,
                            "employee": c.employee.full_name,
                            "stage": "Awaiting manager",
                            "hours_pending": round(hours, 1),
                        }
                    )
        q2 = ExpenseClaim.query.filter(
            ExpenseClaim.status == ClaimStatus.MANAGER_APPROVED
        )
        q2 = _scoped(q2, employee_ids, ExpenseClaim.employee_id)
        for c in q2.all():
            last = (
                ApprovalHistory.query.filter_by(
                    claim_id=c.id, new_status=ClaimStatus.MANAGER_APPROVED
                )
                .order_by(ApprovalHistory.acted_at.desc())
                .first()
            )
            when = last.acted_at if last else c.submitted_at
            if when:
                hours = (now - when).total_seconds() / 3600
                if hours > finance_sla_hours:
                    results.append(
                        {
                            "claim_no": c.claim_no,
                            "claim_id": c.id,
                            "employee": c.employee.full_name,
                            "stage": "Awaiting finance",
                            "hours_pending": round(hours, 1),
                        }
                    )
        return sorted(results, key=lambda r: -r["hours_pending"])

    def budget_utilization(self, employee):
        month_start = date.today().replace(day=1)
        rows = (
            db.session.query(
                ExpenseCategory.id,
                ExpenseCategory.name,
                db.func.coalesce(db.func.sum(ExpenseItem.amount_in_base), 0),
            )
            .join(ExpenseItem, ExpenseItem.category_id == ExpenseCategory.id)
            .join(ExpenseClaim, ExpenseItem.claim_id == ExpenseClaim.id)
            .filter(
                ExpenseClaim.employee_id == employee.id,
                ExpenseClaim.claim_date >= month_start,
                ExpenseClaim.status != ClaimStatus.CANCELLED,
            )
            .group_by(ExpenseCategory.id)
            .all()
        )
        spent_by_cat = {cid: (name, float(amt)) for cid, name, amt in rows}
        today = date.today()
        candidates = (
            ExpensePolicy.query.filter(
                ExpensePolicy.grade == employee.grade,
                ExpensePolicy.is_active.is_(True),
                ExpensePolicy.effective_from <= today,
            )
            .order_by(ExpensePolicy.effective_from.desc())
            .all()
        )
        policies_by_cat = {}
        for p in candidates:
            if p.effective_to and p.effective_to < today:
                continue
            policies_by_cat.setdefault(p.category_id, p)
        out = []
        for p in policies_by_cat.values():
            cid = p.category_id
            name, spent = spent_by_cat.get(cid, (p.category.name, 0.0))
            limit = float(p.max_amount_per_claim)
            pct = round(min(spent / limit * 100, 999), 1) if limit else 0
            out.append(
                {
                    "category": name,
                    "spent_this_month": spent,
                    "claim_limit": limit,
                    "pct_of_claim_limit": pct,
                }
            )
        return sorted(out, key=lambda r: -r["pct_of_claim_limit"])

    def find_possible_duplicates(self, claim, window_days=3):
        warnings = []
        other_items = (
            db.session.query(ExpenseItem, ExpenseClaim.claim_no)
            .join(ExpenseClaim, ExpenseItem.claim_id == ExpenseClaim.id)
            .filter(
                ExpenseClaim.employee_id == claim.employee_id,
                ExpenseClaim.id != claim.id,
                ExpenseClaim.status != ClaimStatus.CANCELLED,
            )
            .all()
        )
        for item in claim.items:
            for other, other_claim_no in other_items:
                if other.amount_in_base != item.amount_in_base:
                    continue
                same_vendor = (item.vendor or "").strip().lower() == (
                    other.vendor or ""
                ).strip().lower() and item.vendor
                date_close = (
                    abs((item.expense_date - other.expense_date).days) <= window_days
                )
                if same_vendor and date_close:
                    warnings.append(
                        f"'{item.description}' (Rs.{item.amount_in_base} on {item.expense_date}) looks like the "
                        f"same expense as an item on claim {other_claim_no} ({other.description}, "
                        f"Rs.{other.amount_in_base} on {other.expense_date}, vendor '{other.vendor}')."
                    )
        return warnings
