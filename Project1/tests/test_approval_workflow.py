import unittest
from datetime import date
from dao.approval_dao import ApprovalDAO
from dao.claim_dao import ClaimDAO
from service.approval_service import ApprovalService
from models.expense_claim import ExpenseClaim
from models.enums import ClaimStatus, Action
from tests.base import BaseTestCase


class ApprovalStateMachineTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.approval_dao = ApprovalDAO()
        self.claim_dao = ClaimDAO()
        self.service = ApprovalService(self.approval_dao)
        self._seq = 0

    def _claim(self, status=ClaimStatus.DRAFT):
        self._seq += 1
        claim = ExpenseClaim(
            claim_no=f"CLM-AP-{self._seq:04d}",
            employee_id=self.employee.id,
            title="Approval test",
            claim_date=date.today(),
            period_from=date.today(),
            period_to=date.today(),
            status=status,
        )
        return self.claim_dao.save(claim)

    def test_draft_to_submitted_is_valid(self):
        claim = self._claim(ClaimStatus.DRAFT)
        result = self.service.transition(
            claim, ClaimStatus.SUBMITTED, self.employee_user, Action.SUBMITTED
        )
        self.assertEqual(result.status, ClaimStatus.SUBMITTED)
        self.assertIsNotNone(result.submitted_at)

    def test_submitted_to_manager_approved_is_valid(self):
        claim = self._claim(ClaimStatus.SUBMITTED)
        result = self.service.transition(
            claim, ClaimStatus.MANAGER_APPROVED, self.manager_user, Action.APPROVED
        )
        self.assertEqual(result.status, ClaimStatus.MANAGER_APPROVED)

    def test_manager_approved_to_finance_verified_is_valid(self):
        claim = self._claim(ClaimStatus.MANAGER_APPROVED)
        result = self.service.transition(
            claim, ClaimStatus.FINANCE_VERIFIED, self.finance_user, Action.VERIFIED
        )
        self.assertEqual(result.status, ClaimStatus.FINANCE_VERIFIED)

    def test_finance_verified_to_reimbursed_is_valid(self):
        claim = self._claim(ClaimStatus.FINANCE_VERIFIED)
        result = self.service.transition(
            claim, ClaimStatus.REIMBURSED, self.finance_user, Action.REIMBURSED
        )
        self.assertEqual(result.status, ClaimStatus.REIMBURSED)

    def test_draft_to_manager_approved_skipping_submit_is_invalid(self):
        claim = self._claim(ClaimStatus.DRAFT)
        with self.assertRaises(ValueError):
            self.service.transition(
                claim, ClaimStatus.MANAGER_APPROVED, self.manager_user, Action.APPROVED
            )

    def test_reimbursed_is_a_terminal_state(self):
        claim = self._claim(ClaimStatus.REIMBURSED)
        with self.assertRaises(ValueError):
            self.service.transition(
                claim, ClaimStatus.SUBMITTED, self.employee_user, Action.SUBMITTED
            )

    def test_rejected_claim_cannot_move_further(self):
        claim = self._claim(ClaimStatus.MANAGER_REJECTED)
        with self.assertRaises(ValueError):
            self.service.transition(
                claim, ClaimStatus.FINANCE_VERIFIED, self.finance_user, Action.VERIFIED
            )

    def test_reject_without_comments_fails(self):
        claim = self._claim(ClaimStatus.SUBMITTED)
        with self.assertRaises(ValueError) as ctx:
            self.service.transition(
                claim,
                ClaimStatus.MANAGER_REJECTED,
                self.manager_user,
                Action.REJECTED,
                comments="",
            )
        self.assertIn("reason is mandatory", str(ctx.exception))

    def test_reject_with_comments_succeeds(self):
        claim = self._claim(ClaimStatus.SUBMITTED)
        result = self.service.transition(
            claim,
            ClaimStatus.MANAGER_REJECTED,
            self.manager_user,
            Action.REJECTED,
            comments="Missing bills",
        )
        self.assertEqual(result.status, ClaimStatus.MANAGER_REJECTED)

    def test_transition_writes_approval_history_row(self):
        claim = self._claim(ClaimStatus.SUBMITTED)
        self.service.transition(
            claim,
            ClaimStatus.MANAGER_APPROVED,
            self.manager_user,
            Action.APPROVED,
            comments="Looks fine",
        )
        history = self.approval_dao.get_for_claim(claim.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].action, Action.APPROVED)
        self.assertEqual(history[0].old_status, ClaimStatus.SUBMITTED)
        self.assertEqual(history[0].new_status, ClaimStatus.MANAGER_APPROVED)
        self.assertEqual(history[0].actor_id, self.manager_user.id)

    def test_assert_is_manager_of_passes_for_real_manager(self):
        claim = self._claim(ClaimStatus.SUBMITTED)
        self.service.assert_is_manager_of(self.manager, claim)

    def test_assert_is_manager_of_blocks_unrelated_manager(self):
        claim = self._claim(ClaimStatus.SUBMITTED)
        with self.assertRaises(ValueError):
            self.service.assert_is_manager_of(self.other_manager, claim)


class ApprovalHttpRouteTests(BaseTestCase):

    def _submit_claim_as_employee(self, title="HTTP approval claim"):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": title,
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        from models.expense_claim import ExpenseClaim

        claim = ExpenseClaim.query.filter_by(title=title).first()
        self.client.post(
            f"/expense/{claim.id}/item/add",
            data={
                "category_id": str(self.category.id),
                "expense_date": date.today().isoformat(),
                "description": "Cab",
                "amount": "500",
            },
        )
        self.client.post(f"/expense/{claim.id}/submit")
        return claim.id

    def test_manager_approves_claim_via_route(self):
        claim_id = self._submit_claim_as_employee()
        manager_client = self.app.test_client()
        manager_client.post(
            "/auth/login?portal=manager",
            data={"username": "mgr1", "password": "Test@1234"},
        )
        resp = manager_client.post(
            f"/manager/claim/{claim_id}/decide",
            data={"decision": "approve", "comments": "ok"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        from models.expense_claim import ExpenseClaim

        self.assertEqual(
            ExpenseClaim.query.get(claim_id).status, ClaimStatus.MANAGER_APPROVED
        )

    def test_manager_rejects_claim_via_route_requires_comments(self):
        claim_id = self._submit_claim_as_employee(title="Reject me")
        manager_client = self.app.test_client()
        manager_client.post(
            "/auth/login?portal=manager",
            data={"username": "mgr1", "password": "Test@1234"},
        )
        resp = manager_client.post(
            f"/manager/claim/{claim_id}/decide",
            data={"decision": "reject"},
            follow_redirects=True,
        )
        from models.expense_claim import ExpenseClaim

        self.assertEqual(ExpenseClaim.query.get(claim_id).status, ClaimStatus.SUBMITTED)

    def test_unrelated_manager_cannot_decide_via_route(self):
        claim_id = self._submit_claim_as_employee(title="Not your team")
        other_mgr_client = self.app.test_client()
        other_mgr_client.post(
            "/auth/login?portal=manager",
            data={"username": "mgr2", "password": "Test@1234"},
        )
        other_mgr_client.post(
            f"/manager/claim/{claim_id}/decide",
            data={"decision": "approve"},
            follow_redirects=True,
        )
        from models.expense_claim import ExpenseClaim

        self.assertEqual(ExpenseClaim.query.get(claim_id).status, ClaimStatus.SUBMITTED)

    def test_finance_verifies_manager_approved_claim(self):
        claim_id = self._submit_claim_as_employee(title="For finance")
        manager_client = self.app.test_client()
        manager_client.post(
            "/auth/login?portal=manager",
            data={"username": "mgr1", "password": "Test@1234"},
        )
        manager_client.post(
            f"/manager/claim/{claim_id}/decide", data={"decision": "approve"}
        )

        finance_client = self.app.test_client()
        finance_client.post(
            "/auth/login?portal=finance",
            data={"username": "fin1", "password": "Test@1234"},
        )
        resp = finance_client.post(
            f"/finance/claim/{claim_id}/verify",
            data={"decision": "approve"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        from models.expense_claim import ExpenseClaim

        self.assertEqual(
            ExpenseClaim.query.get(claim_id).status, ClaimStatus.FINANCE_VERIFIED
        )

    def test_employee_cannot_verify_own_claim(self):
        claim_id = self._submit_claim_as_employee(title="Self verify attempt")
        resp = self.client.post(
            f"/finance/claim/{claim_id}/verify",
            data={"decision": "approve"},
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
