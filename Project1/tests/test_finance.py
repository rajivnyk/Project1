import pytest
from service.finance_service import FinanceService
from models.expense_claim import ExpenseClaim
from models.expense_item import ExpenseItem
from models.travel_request import TravelRequest
from models.enums import ClaimStatus
from models.user import User


class MockClaimDAO:
    def __init__(self, claim):
        self.claim = claim

    def get_by_id(self, id):
        return self.claim


class MockReimbursementDAO:
    def get_by_claim(self, claim_id):
        return None

    def save(self, r):
        pass


class MockApprovalService:
    def transition(self, claim, target, user, action, comments):
        claim.status = target


def test_finance_service_deducts_advance():
    item1 = ExpenseItem(amount_in_base=10000, approved_amount=10000)
    item2 = ExpenseItem(amount_in_base=5000, approved_amount=5000)

    tr = TravelRequest(advance_required=3000)

    claim = ExpenseClaim(
        id=1,
        total_amount=15000,
        status=ClaimStatus.FINANCE_VERIFIED,
        travel_request=tr,
        items=[item1, item2],
    )

    dao = MockClaimDAO(claim)
    r_dao = MockReimbursementDAO()
    approval = MockApprovalService()

    service = FinanceService(dao, r_dao, approval)
    finance_user = User(id=2)

    # Process without extra manual deductions
    reimb = service.process_reimbursement(
        1,
        finance_user,
        {"deducted_amount": "0", "payment_mode": "NEFT", "transaction_ref": "REF123"},
    )

    # Total approved = 15000. Advance = 3000. Final should be 12000.
    assert float(reimb.approved_amount) == 12000.00
    assert float(reimb.deducted_amount) == 3000.00
    assert claim.status == ClaimStatus.REIMBURSED
