from datetime import date
from config.database import db


class ExpensePolicy(db.Model):
    __tablename__ = "expense_policies"
    __table_args__ = (
        db.UniqueConstraint(
            "category_id", "grade", "effective_from", name="uq_policy_cat_grade_from"
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(
        db.Integer, db.ForeignKey("expense_categories.id"), nullable=False
    )
    grade = db.Column(db.String(10), nullable=False)
    max_amount_per_day = db.Column(db.Numeric(10, 2), nullable=False)
    max_amount_per_claim = db.Column(db.Numeric(10, 2), nullable=False)
    receipt_required_above = db.Column(db.Numeric(10, 2), default=0)
    requires_prior_approval = db.Column(db.Boolean, default=False)
    effective_from = db.Column(db.Date, nullable=False, default=date.today)
    effective_to = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    category = db.relationship("ExpenseCategory")
