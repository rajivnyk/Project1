from datetime import date
from models.reimbursement import Reimbursement
from models.enums import ClaimStatus, Action
from util.helpers import generate_sequence, money


class FinanceService:
    def __init__(self, claim_dao, reimbursement_dao, approval_service):
        self.claim_dao = claim_dao
        self.reimbursement_dao = reimbursement_dao
        self.approval_service = approval_service

    def pending_verification(self):
        return self.claim_dao.get_by_status(ClaimStatus.MANAGER_APPROVED)

    def verify(self, claim_id, finance_user, approve, comments):
        claim = self.claim_dao.get_by_id(claim_id)
        if claim is None:
            raise ValueError("Claim not found")
        target = (
            ClaimStatus.FINANCE_VERIFIED if approve else ClaimStatus.FINANCE_REJECTED
        )
        action = Action.VERIFIED if approve else Action.REJECTED
        return self.approval_service.transition(
            claim, target, finance_user, action, comments
        )

    def process_reimbursement(self, claim_id, finance_user, data):
        claim = self.claim_dao.get_by_id(claim_id)
        if claim is None:
            raise ValueError("Claim not found")
        if claim.status != ClaimStatus.FINANCE_VERIFIED:
            raise ValueError(
                f"Only verified claims can be paid; this one is {claim.status}"
            )
        if self.reimbursement_dao.get_by_claim(claim.id):
            raise ValueError("This claim has already been reimbursed")
        approved_total = sum(
            (
                item.approved_amount
                if item.approved_amount is not None
                else item.amount_in_base
            )
            for item in claim.items
        )
        advance = (
            claim.travel_request.advance_required
            if claim.travel_request and claim.travel_request.advance_required
            else 0
        )
        claimed = money(claim.total_amount)
        manual_deduction = money(data.get("deducted_amount", 0))
        if manual_deduction < 0:
            raise ValueError("Manual deduction cannot be negative")
        final_approved = money(approved_total) - manual_deduction - money(advance)
        if final_approved < 0:
            final_approved = 0
        if manual_deduction > 0 and not (data.get("deduction_reason") or "").strip():
            raise ValueError(
                "A deduction reason is mandatory if you specify a manual deduction"
            )
        reimb = Reimbursement(
            claim_id=claim.id,
            reference_no=generate_sequence("REIMB", Reimbursement, "reference_no"),
            claimed_amount=claimed,
            approved_amount=final_approved,
            deducted_amount=manual_deduction + money(advance),
            deduction_reason=data.get("deduction_reason"),
            payment_mode=data.get("payment_mode", "NEFT"),
            payment_date=date.today(),
            transaction_ref=data.get("transaction_ref"),
            status="PAID",
            paid_by=finance_user.id,
        )
        self.reimbursement_dao.save(reimb)
        self.approval_service.transition(
            claim,
            ClaimStatus.REIMBURSED,
            finance_user,
            Action.REIMBURSED,
            comments=f"Paid Rs.{reimb.approved_amount} via {reimb.payment_mode} ({reimb.reference_no})",
        )
        return reimb
