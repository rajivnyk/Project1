from sqlalchemy import or_
from config.database import db
from models.expense_claim import ExpenseClaim
from models.employee import Employee


class ClaimDAO:
    def get_all(self):
        return ExpenseClaim.query.all()

    def get_by_id(self, claim_id):
        return ExpenseClaim.query.get(claim_id)

    def get_by_employee(self, employee_id, status=None):
        q = ExpenseClaim.query.filter_by(employee_id=employee_id)
        if status:
            q = q.filter(ExpenseClaim.status == status)
        return q.order_by(ExpenseClaim.created_at.desc()).all()

    def get_pending_for_manager(self, reportee_ids, status):
        if not reportee_ids:
            return []
        return (
            ExpenseClaim.query.filter(
                ExpenseClaim.employee_id.in_(reportee_ids),
                ExpenseClaim.status == status,
            )
            .order_by(ExpenseClaim.submitted_at.asc())
            .all()
        )

    def get_by_status(self, status):
        return (
            ExpenseClaim.query.filter_by(status=status)
            .order_by(ExpenseClaim.submitted_at.asc())
            .all()
        )

    def search(self, keyword=None, status=None, employee_id=None, page=1, per_page=10):
        q = ExpenseClaim.query.join(Employee, ExpenseClaim.employee_id == Employee.id)
        if keyword:
            like = f"%{keyword}%"
            q = q.filter(
                or_(
                    ExpenseClaim.claim_no.like(like),
                    ExpenseClaim.title.like(like),
                    Employee.full_name.like(like),
                )
            )
        if status:
            q = q.filter(ExpenseClaim.status == status)
        if employee_id:
            q = q.filter(ExpenseClaim.employee_id == employee_id)
        return q.order_by(ExpenseClaim.claim_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    def recalc_total(self, claim_id):
        from models.expense_item import ExpenseItem

        return (
            db.session.query(
                db.func.coalesce(db.func.sum(ExpenseItem.amount_in_base), 0)
            )
            .filter(ExpenseItem.claim_id == claim_id)
            .scalar()
        )

    def summary_by_status(self, employee_id=None):
        q = db.session.query(
            ExpenseClaim.status,
            db.func.count(ExpenseClaim.id),
            db.func.coalesce(db.func.sum(ExpenseClaim.total_amount), 0),
        )
        if employee_id:
            q = q.filter(ExpenseClaim.employee_id == employee_id)
        return q.group_by(ExpenseClaim.status).all()

    def save(self, claim):
        db.session.add(claim)
        db.session.commit()
        return claim

    def update(self):
        db.session.commit()

    def delete(self, claim):
        db.session.delete(claim)
        db.session.commit()
