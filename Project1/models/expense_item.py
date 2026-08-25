from decimal import Decimal
from config.database import db


class ExpenseItem(db.Model):
    __tablename__ = "expense_items"
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(
        db.Integer,
        db.ForeignKey("expense_claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id = db.Column(
        db.Integer, db.ForeignKey("expense_categories.id"), nullable=False
    )
    expense_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default="INR")
    exchange_rate = db.Column(db.Numeric(10, 4), default=Decimal("1.0000"))
    amount_in_base = db.Column(db.Numeric(12, 2), nullable=False)
    approved_amount = db.Column(db.Numeric(12, 2), nullable=True)
    vendor = db.Column(db.String(120))
    city = db.Column(db.String(80))
    policy_violation = db.Column(db.Boolean, default=False)
    violation_reason = db.Column(db.String(255))
    reviewer_comments = db.Column(db.String(255), nullable=True)
    claim = db.relationship("ExpenseClaim", back_populates="items")
    category = db.relationship("ExpenseCategory")
    receipts = db.relationship("ExpenseReceipt", back_populates="item")

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.expense_date.isoformat(),
            "category": self.category.name if self.category else None,
            "description": self.description,
            "amount_in_base": float(self.amount_in_base),
            "approved_amount": (
                float(self.approved_amount)
                if self.approved_amount is not None
                else None
            ),
            "violation": self.policy_violation,
            "violation_reason": self.violation_reason,
            "reviewer_comments": self.reviewer_comments,
        }
