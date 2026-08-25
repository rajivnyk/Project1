from config.database import db
from models.expense_claim import ExpenseClaim
from models.expense_item import ExpenseItem
from models.expense_category import ExpenseCategory
from models.enums import ClaimStatus


class ReportService:
    def __init__(self, claim_dao):
        self.claim_dao = claim_dao

    def employee_summary(self, employee_id):
        rows = self.claim_dao.summary_by_status(employee_id)
        total_claims = pending_claims = approved_claims = 0
        total_amount = 0.0
        approved_statuses = (
            ClaimStatus.MANAGER_APPROVED,
            ClaimStatus.FINANCE_VERIFIED,
            ClaimStatus.REIMBURSED,
        )
        for status, count, amount in rows:
            total_claims += count
            total_amount += float(amount)
            if status == ClaimStatus.SUBMITTED:
                pending_claims += count
            elif status in approved_statuses:
                approved_claims += count
        return {
            "total_claims": total_claims,
            "pending_claims": pending_claims,
            "approved_claims": approved_claims,
            "total_amount": total_amount,
        }

    def category_breakdown(self, employee_id=None):
        q = (
            db.session.query(
                ExpenseCategory.name,
                db.func.count(ExpenseItem.id),
                db.func.coalesce(db.func.sum(ExpenseItem.amount_in_base), 0),
            )
            .join(ExpenseItem, ExpenseItem.category_id == ExpenseCategory.id)
            .join(ExpenseClaim, ExpenseItem.claim_id == ExpenseClaim.id)
        )
        if employee_id:
            q = q.filter(ExpenseClaim.employee_id == employee_id)
        return [
            {"category": n, "count": c, "amount": float(a)}
            for n, c, a in q.group_by(ExpenseCategory.name)
        ]
