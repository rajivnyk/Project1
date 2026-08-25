from config.database import db
from models.expense_item import ExpenseItem


class ItemDAO:
    def get_by_id(self, item_id):
        return ExpenseItem.query.get(item_id)

    def get_by_claim(self, claim_id):
        return (
            ExpenseItem.query.filter_by(claim_id=claim_id)
            .order_by(ExpenseItem.expense_date)
            .all()
        )

    def daily_total(self, claim_id, category_id, on_date, exclude_item_id=None):
        q = db.session.query(
            db.func.coalesce(db.func.sum(ExpenseItem.amount_in_base), 0)
        ).filter(
            ExpenseItem.claim_id == claim_id,
            ExpenseItem.category_id == category_id,
            ExpenseItem.expense_date == on_date,
        )
        if exclude_item_id:
            q = q.filter(ExpenseItem.id != exclude_item_id)
        return q.scalar()

    def save(self, item):
        db.session.add(item)
        db.session.commit()
        return item

    def delete(self, item):
        db.session.delete(item)
        db.session.commit()
