from datetime import datetime
from decimal import Decimal
from config.database import db
from models.enums import ClaimStatus


class ExpenseClaim(db.Model):
    __tablename__ = "expense_claims"
    __table_args__ = (db.Index("idx_claim_employee_status", "employee_id", "status"),)
    id = db.Column(db.Integer, primary_key=True)
    claim_no = db.Column(db.String(20), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    travel_request_id = db.Column(db.Integer, db.ForeignKey("travel_requests.id"))
    title = db.Column(db.String(150), nullable=False)
    claim_date = db.Column(db.Date, nullable=False)
    period_from = db.Column(db.Date)
    period_to = db.Column(db.Date)
    total_amount = db.Column(db.Numeric(12, 2), default=Decimal("0.00"))
    status = db.Column(
        db.String(30), nullable=False, default=ClaimStatus.DRAFT, index=True
    )
    policy_flag = db.Column(db.Boolean, default=False)
    violation_count = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee = db.relationship("Employee")
    travel_request = db.relationship("TravelRequest")
    items = db.relationship(
        "ExpenseItem", back_populates="claim", cascade="all, delete-orphan"
    )
    receipts = db.relationship(
        "ExpenseReceipt", back_populates="claim", cascade="all, delete-orphan"
    )
    history = db.relationship(
        "ApprovalHistory", back_populates="claim", order_by="ApprovalHistory.acted_at"
    )
    reimbursement = db.relationship(
        "Reimbursement", back_populates="claim", uselist=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "claim_no": self.claim_no,
            "title": self.title,
            "employee": self.employee.full_name if self.employee else None,
            "claim_date": self.claim_date.isoformat(),
            "total_amount": float(self.total_amount or 0),
            "status": self.status,
            "items": len(self.items),
            "policy_flag": self.policy_flag,
        }
