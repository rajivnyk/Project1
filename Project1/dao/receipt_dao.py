from config.database import db
from models.expense_receipt import ExpenseReceipt


class ReceiptDAO:
    def get_by_id(self, receipt_id):
        return ExpenseReceipt.query.get(receipt_id)

    def get_by_claim(self, claim_id):
        return ExpenseReceipt.query.filter_by(claim_id=claim_id).all()

    def get_by_checksum(self, checksum):
        return ExpenseReceipt.query.filter_by(checksum_sha256=checksum).first()

    def save(self, receipt):
        db.session.add(receipt)
        db.session.commit()
        return receipt
