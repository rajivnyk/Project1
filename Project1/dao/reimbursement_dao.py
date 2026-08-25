from config.database import db
from models.reimbursement import Reimbursement


class ReimbursementDAO:
    def get_by_claim(self, claim_id):
        return Reimbursement.query.filter_by(claim_id=claim_id).first()

    def save(self, reimbursement):
        db.session.add(reimbursement)
        return reimbursement
