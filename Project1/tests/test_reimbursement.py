import unittest
from datetime import date
from decimal import Decimal
from dao.claim_dao import ClaimDAO
from dao.reimbursement_dao import ReimbursementDAO
from dao.approval_dao import ApprovalDAO
from service.approval_service import ApprovalService
from service.finance_service import FinanceService
from models.expense_claim import ExpenseClaim
from models.expense_item import ExpenseItem
from models.travel_request import TravelRequest
from models.enums import ClaimStatus, TravelStatus
from tests.base import BaseTestCase


class ReimbursementCalculationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.claim_dao = ClaimDAO()
        self.reimbursement_dao = ReimbursementDAO()
        approval_service = ApprovalService(ApprovalDAO())
        self.service = FinanceService(
            self.claim_dao, self.reimbursement_dao, approval_service
        )
        self._seq = 0

    def _verified_claim(self, items_amount=(10000, 5000), advance=0, travel=True):
        self._seq += 1
        tr = None
        if travel:
            tr = TravelRequest(
                request_no=f"TR-RB-{self._seq:04d}",
                employee_id=self.employee.id,
                purpose="trip",
                destination_city="Pune",
                from_date=date.today(),
                to_date=date.today(),
                estimated_cost=1000,
                advance_required=Decimal(str(advance)),
                status=TravelStatus.APPROVED,
            )
        claim = ExpenseClaim(
            claim_no=f"CLM-RB-{self._seq:04d}",
            employee_id=self.employee.id,
            title="Reimb test",
            claim_date=date.today(),
            period_from=date.today(),
            period_to=date.today(),
            status=ClaimStatus.FINANCE_VERIFIED,
            travel_request=tr,
        )
        claim.total_amount = sum(items_amount)
        claim.items = [
            ExpenseItem(
                category_id=self.category.id,
                expense_date=date.today(),
                description="item",
                amount=Decimal(a),
                amount_in_base=Decimal(a),
                approved_amount=Decimal(a),
            )
            for a in items_amount
        ]
        return self.claim_dao.save(claim)

    def test_reimburse_with_no_advance_no_deduction(self):
        claim = self._verified_claim((10000, 5000), advance=0)
        reimb = self.service.process_reimbursement(
            claim.id,
            self.finance_user,
            {"payment_mode": "NEFT", "transaction_ref": "REF1"},
        )
        self.assertEqual(reimb.approved_amount, Decimal("15000.00"))
        self.assertEqual(reimb.deducted_amount, Decimal("0.00"))
        self.assertEqual(claim.status, ClaimStatus.REIMBURSED)

    def test_reimburse_deducts_travel_advance(self):
        claim = self._verified_claim((10000, 5000), advance=3000)
        reimb = self.service.process_reimbursement(
            claim.id,
            self.finance_user,
            {"payment_mode": "NEFT", "transaction_ref": "REF2"},
        )
        self.assertEqual(reimb.approved_amount, Decimal("12000.00"))
        self.assertEqual(reimb.deducted_amount, Decimal("3000.00"))

    def test_reimburse_with_manual_deduction_requires_reason(self):
        claim = self._verified_claim((10000, 5000), advance=0)
        with self.assertRaises(ValueError) as ctx:
            self.service.process_reimbursement(
                claim.id,
                self.finance_user,
                {"deducted_amount": "1000", "payment_mode": "NEFT"},
            )
        self.assertIn("deduction reason is mandatory", str(ctx.exception))

    def test_reimburse_with_manual_deduction_and_reason(self):
        claim = self._verified_claim((10000, 5000), advance=0)
        reimb = self.service.process_reimbursement(
            claim.id,
            self.finance_user,
            {
                "deducted_amount": "1000",
                "deduction_reason": "policy cap",
                "payment_mode": "NEFT",
                "transaction_ref": "REF3",
            },
        )
        self.assertEqual(reimb.approved_amount, Decimal("14000.00"))
        self.assertEqual(reimb.deducted_amount, Decimal("1000.00"))

    def test_reimburse_combines_advance_and_manual_deduction(self):
        claim = self._verified_claim((10000, 5000), advance=2000)
        reimb = self.service.process_reimbursement(
            claim.id,
            self.finance_user,
            {
                "deducted_amount": "1000",
                "deduction_reason": "damage",
                "payment_mode": "NEFT",
                "transaction_ref": "REF4",
            },
        )
        self.assertEqual(reimb.approved_amount, Decimal("12000.00"))
        self.assertEqual(reimb.deducted_amount, Decimal("3000.00"))

    def test_negative_manual_deduction_rejected(self):
        claim = self._verified_claim((10000, 5000), advance=0)
        with self.assertRaises(ValueError):
            self.service.process_reimbursement(
                claim.id, self.finance_user, {"deducted_amount": "-500"}
            )

    def test_deduction_larger_than_claim_floors_at_zero(self):
        claim = self._verified_claim((1000,), advance=0)
        reimb = self.service.process_reimbursement(
            claim.id,
            self.finance_user,
            {
                "deducted_amount": "5000",
                "deduction_reason": "overpaid advance previously",
                "payment_mode": "NEFT",
            },
        )
        self.assertEqual(reimb.approved_amount, Decimal("0.00"))

    def test_uses_approved_amount_over_claimed_amount(self):
        claim = self._verified_claim((10000,), advance=0)
        claim.items[0].approved_amount = Decimal("8000.00")
        reimb = self.service.process_reimbursement(
            claim.id, self.finance_user, {"payment_mode": "NEFT"}
        )
        self.assertEqual(reimb.approved_amount, Decimal("8000.00"))

    def test_falls_back_to_claimed_amount_when_not_approved_individually(self):
        claim = self._verified_claim((10000,), advance=0)
        claim.items[0].approved_amount = None
        reimb = self.service.process_reimbursement(
            claim.id, self.finance_user, {"payment_mode": "NEFT"}
        )
        self.assertEqual(reimb.approved_amount, Decimal("10000.00"))

    def test_only_finance_verified_claims_can_be_paid(self):
        claim = self._verified_claim((5000,), advance=0)
        claim.status = ClaimStatus.MANAGER_APPROVED
        with self.assertRaises(ValueError) as ctx:
            self.service.process_reimbursement(claim.id, self.finance_user, {})
        self.assertIn("Only verified claims", str(ctx.exception))

    def test_double_reimbursement_rejected(self):
        # After the first payment the claim status flips to REIMBURSED, so the
        # second call is actually stopped by the FINANCE_VERIFIED-only guard
        # (the "already been reimbursed" DAO check is a second line of defense
        # for the case where the status update didn't stick).
        claim = self._verified_claim((5000,), advance=0)
        self.service.process_reimbursement(
            claim.id, self.finance_user, {"payment_mode": "NEFT"}
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.process_reimbursement(
                claim.id, self.finance_user, {"payment_mode": "NEFT"}
            )
        self.assertIn("Only verified claims can be paid", str(ctx.exception))

    def test_double_reimbursement_still_rejected_if_status_out_of_sync(self):
        claim = self._verified_claim((5000,), advance=0)
        self.service.process_reimbursement(
            claim.id, self.finance_user, {"payment_mode": "NEFT"}
        )
        claim.status = ClaimStatus.FINANCE_VERIFIED
        from config.database import db

        db.session.commit()
        with self.assertRaises(ValueError) as ctx:
            self.service.process_reimbursement(
                claim.id, self.finance_user, {"payment_mode": "NEFT"}
            )
        self.assertIn("already been reimbursed", str(ctx.exception))

    def test_reimbursement_reference_no_is_unique_and_prefixed(self):
        claim1 = self._verified_claim((1000,), advance=0)
        claim2 = self._verified_claim((2000,), advance=0)
        r1 = self.service.process_reimbursement(claim1.id, self.finance_user, {})
        r2 = self.service.process_reimbursement(claim2.id, self.finance_user, {})
        self.assertTrue(r1.reference_no.startswith("REIMB-"))
        self.assertNotEqual(r1.reference_no, r2.reference_no)

    def test_no_travel_request_means_no_advance_deducted(self):
        claim = self._verified_claim((5000,), advance=0, travel=False)
        reimb = self.service.process_reimbursement(claim.id, self.finance_user, {})
        self.assertEqual(reimb.approved_amount, Decimal("5000.00"))


if __name__ == "__main__":
    unittest.main()
