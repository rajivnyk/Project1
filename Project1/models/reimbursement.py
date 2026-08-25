from datetime import datetime
from config.database import db


class Reimbursement(db.Model):
    __tablename__ = "reimbursements"
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(
        db.Integer, db.ForeignKey("expense_claims.id"), unique=True, nullable=False
    )
    reference_no = db.Column(db.String(30), unique=True, nullable=False)
    claimed_amount = db.Column(db.Numeric(12, 2), nullable=False)
    approved_amount = db.Column(db.Numeric(12, 2), nullable=False)
    deducted_amount = db.Column(db.Numeric(12, 2), default=0)
    deduction_reason = db.Column(db.String(255))
    payment_mode = db.Column(db.String(20), default="NEFT")
    payment_date = db.Column(db.Date)
    transaction_ref = db.Column(db.String(60))
    status = db.Column(db.String(20), default="PAID")
    paid_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    claim = db.relationship("ExpenseClaim", back_populates="reimbursement")
