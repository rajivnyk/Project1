from datetime import datetime
from config.database import db


class ApprovalHistory(db.Model):
    __tablename__ = "approval_history"
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(20), nullable=False)
    claim_id = db.Column(db.Integer, db.ForeignKey("expense_claims.id"))
    travel_request_id = db.Column(db.Integer, db.ForeignKey("travel_requests.id"))
    level = db.Column(db.SmallInteger, nullable=False, default=1)
    action = db.Column(db.String(20), nullable=False)
    old_status = db.Column(db.String(30))
    new_status = db.Column(db.String(30))
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comments = db.Column(db.String(500))
    acted_at = db.Column(db.DateTime, default=datetime.utcnow)
    claim = db.relationship("ExpenseClaim", back_populates="history")
    actor = db.relationship("User")
