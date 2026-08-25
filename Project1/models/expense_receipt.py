from datetime import datetime
from config.database import db


class ExpenseReceipt(db.Model):
    __tablename__ = "expense_receipts"
    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(
        db.Integer,
        db.ForeignKey("expense_claims.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id = db.Column(db.Integer, db.ForeignKey("expense_items.id"))
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), unique=True, nullable=False)
    file_path = db.Column(db.String(400), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    checksum_sha256 = db.Column(db.String(64), nullable=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    claim = db.relationship("ExpenseClaim", back_populates="receipts")
    item = db.relationship("ExpenseItem", back_populates="receipts")
