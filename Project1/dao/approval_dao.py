from config.database import db
from models.approval_history import ApprovalHistory


class ApprovalDAO:
    def get_for_claim(self, claim_id):
        return (
            ApprovalHistory.query.filter_by(claim_id=claim_id)
            .order_by(ApprovalHistory.acted_at)
            .all()
        )

    def save(self, history_row):
        db.session.add(history_row)
        return history_row
