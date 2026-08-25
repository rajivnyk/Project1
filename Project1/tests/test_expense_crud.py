import unittest
from datetime import date, timedelta
from decimal import Decimal
from dao.claim_dao import ClaimDAO
from dao.item_dao import ItemDAO
from dao.category_dao import CategoryDAO
from dao.policy_dao import PolicyDAO
from dao.approval_dao import ApprovalDAO
from service.policy_service import PolicyService
from service.approval_service import ApprovalService
from service.expense_service import ExpenseService
from models.enums import ClaimStatus
from tests.base import BaseTestCase


class ExpenseCrudTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.claim_dao = ClaimDAO()
        self.item_dao = ItemDAO()
        self.category_dao = CategoryDAO()
        policy_service = PolicyService(PolicyDAO(), self.item_dao)
        approval_service = ApprovalService(ApprovalDAO())
        self.service = ExpenseService(
            self.claim_dao,
            self.item_dao,
            self.category_dao,
            policy_service,
            approval_service,
        )

    def _claim_data(self, **overrides):
        data = {
            "title": "August travel expenses",
            "period_from": (date.today() - timedelta(days=5)).isoformat(),
            "period_to": date.today().isoformat(),
        }
        data.update(overrides)
        return data

    def _item_data(self, **overrides):
        data = {
            "category_id": str(self.category.id),
            "expense_date": date.today().isoformat(),
            "description": "Taxi fare",
            "amount": "500",
            "currency": "INR",
        }
        data.update(overrides)
        return data

    # -- Create --
    def test_create_claim_success(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        self.assertEqual(claim.status, ClaimStatus.DRAFT)
        self.assertTrue(claim.claim_no.startswith("CLM-"))
        self.assertEqual(claim.total_amount, 0)

    def test_create_claim_missing_title_fails(self):
        with self.assertRaises(ValueError):
            self.service.create_claim(self.employee, self._claim_data(title=""))

    def test_create_claim_invalid_period_fails(self):
        with self.assertRaises(ValueError):
            self.service.create_claim(
                self.employee,
                self._claim_data(
                    period_from=date.today().isoformat(),
                    period_to=(date.today() - timedelta(days=1)).isoformat(),
                ),
            )

    # -- Read / ownership --
    def test_get_owned_claim_success(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        fetched = self.service.get_owned_claim(claim.id, self.employee)
        self.assertEqual(fetched.id, claim.id)

    def test_get_owned_claim_wrong_owner_fails(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        with self.assertRaises(ValueError):
            self.service.get_owned_claim(claim.id, self.other_employee)

    def test_get_owned_claim_not_found_fails(self):
        with self.assertRaises(ValueError):
            self.service.get_owned_claim(999999, self.employee)

    # -- Update (items) --
    def test_add_item_success(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        item = self.service.add_item(claim, self._item_data())
        self.assertEqual(item.amount_in_base, Decimal("500.00"))
        self.assertEqual(claim.total_amount, Decimal("500.00"))

    def test_add_item_recalculates_claim_total(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        self.service.add_item(claim, self._item_data(amount="500"))
        self.service.add_item(claim, self._item_data(amount="300", description="Meal"))
        self.assertEqual(claim.total_amount, Decimal("800.00"))

    def test_add_item_invalid_category_fails(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        with self.assertRaises(ValueError):
            self.service.add_item(claim, self._item_data(category_id="999999"))

    def test_add_item_future_date_fails(self):
        claim = self.service.create_claim(
            self.employee,
            self._claim_data(period_to=(date.today() + timedelta(days=10)).isoformat()),
        )
        with self.assertRaises(ValueError):
            self.service.add_item(
                claim,
                self._item_data(
                    expense_date=(date.today() + timedelta(days=1)).isoformat()
                ),
            )

    def test_add_item_outside_claim_period_fails(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        with self.assertRaises(ValueError):
            self.service.add_item(
                claim,
                self._item_data(
                    expense_date=(date.today() - timedelta(days=100)).isoformat()
                ),
            )

    def test_add_item_zero_amount_fails(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        with self.assertRaises(ValueError):
            self.service.add_item(claim, self._item_data(amount="0"))

    # -- Delete (items) --
    def test_delete_item_success(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        item = self.service.add_item(claim, self._item_data())
        self.service.delete_item(claim, item.id)
        self.assertEqual(claim.total_amount, Decimal("0.00"))

    def test_delete_item_not_on_claim_fails(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        other_claim = self.service.create_claim(self.other_employee, self._claim_data())
        item = self.service.add_item(other_claim, self._item_data())
        with self.assertRaises(ValueError):
            self.service.delete_item(claim, item.id)

    # -- is_editable --
    def test_draft_claim_is_editable(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        self.assertTrue(self.service.is_editable(claim))

    def test_submitted_claim_is_not_editable(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        self.service.add_item(claim, self._item_data(amount="100"))
        self.service.submit_claim(claim.id, self.employee, self.employee_user)
        self.assertFalse(self.service.is_editable(claim))

    def test_add_item_to_non_editable_claim_blocked_via_owned_claim(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        self.service.add_item(claim, self._item_data(amount="100"))
        self.service.submit_claim(claim.id, self.employee, self.employee_user)
        with self.assertRaises(ValueError):
            self.service.get_owned_claim(claim.id, self.employee, editable_only=True)

    # -- Submit --
    def test_submit_claim_without_items_fails(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        with self.assertRaises(ValueError):
            self.service.submit_claim(claim.id, self.employee, self.employee_user)

    def test_submit_claim_without_manager_auto_approves_to_finance(self):
        # Nobody could ever action a SUBMITTED claim from a managerless
        # employee, so the manager step is skipped rather than stranding it.
        claim = self.service.create_claim(self.other_employee, self._claim_data())
        self.other_employee.manager_id = None
        self.service.add_item(claim, self._item_data())
        result = self.service.submit_claim(
            claim.id, self.other_employee, self.other_employee_user
        )
        self.assertEqual(result.status, ClaimStatus.MANAGER_APPROVED)

    def test_submit_claim_without_manager_sets_approved_amounts(self):
        claim = self.service.create_claim(self.other_employee, self._claim_data())
        self.other_employee.manager_id = None
        self.service.add_item(claim, self._item_data(amount="750"))
        result = self.service.submit_claim(
            claim.id, self.other_employee, self.other_employee_user
        )
        self.assertTrue(all(i.approved_amount is not None for i in result.items))

    def test_submit_claim_with_manager_waits_for_manager(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        self.service.add_item(claim, self._item_data(amount="100"))
        result = self.service.submit_claim(claim.id, self.employee, self.employee_user)
        self.assertEqual(result.status, ClaimStatus.SUBMITTED)

    def test_submit_claim_success(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        self.service.add_item(claim, self._item_data(amount="500"))
        result = self.service.submit_claim(claim.id, self.employee, self.employee_user)
        self.assertEqual(result.status, ClaimStatus.SUBMITTED)
        self.assertIsNotNone(result.submitted_at)

    # -- Cancel --
    def test_cancel_draft_claim(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        result = self.service.cancel_claim(
            claim.id, self.employee, self.employee_user, "changed my mind"
        )
        self.assertEqual(result.status, ClaimStatus.CANCELLED)

    def test_cancel_someone_elses_claim_fails(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        with self.assertRaises(ValueError):
            self.service.cancel_claim(
                claim.id, self.other_employee, self.other_employee_user, "not mine"
            )

    # -- my_claims / claim_detail visibility --
    def test_my_claims_filters_by_status(self):
        c1 = self.service.create_claim(
            self.employee, self._claim_data(title="Draft one")
        )
        c2 = self.service.create_claim(
            self.employee, self._claim_data(title="Draft two")
        )
        self.service.add_item(c2, self._item_data(amount="100"))
        self.service.submit_claim(c2.id, self.employee, self.employee_user)

        drafts = self.service.my_claims(self.employee, ClaimStatus.DRAFT)
        submitted = self.service.my_claims(self.employee, ClaimStatus.SUBMITTED)
        self.assertEqual([c.id for c in drafts], [c1.id])
        self.assertEqual([c.id for c in submitted], [c2.id])

    def test_claim_detail_owner_can_view(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        result = self.service.claim_detail(claim.id, self.employee_user, self.employee)
        self.assertEqual(result.id, claim.id)

    def test_claim_detail_manager_of_owner_can_view(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        result = self.service.claim_detail(claim.id, self.manager_user, self.manager)
        self.assertEqual(result.id, claim.id)

    def test_claim_detail_unrelated_employee_cannot_view(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        with self.assertRaises(ValueError):
            self.service.claim_detail(
                claim.id, self.other_employee_user, self.other_employee
            )

    def test_claim_detail_finance_can_view_any(self):
        claim = self.service.create_claim(self.employee, self._claim_data())
        result = self.service.claim_detail(claim.id, self.finance_user, None)
        self.assertEqual(result.id, claim.id)


class ExpenseHttpRouteTests(BaseTestCase):

    def test_new_claim_route_creates_draft(self):
        self.login_as_employee()
        resp = self.client.post(
            "/expense/new",
            data={
                "title": "Route created claim",
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Now add your expenses", resp.data)

    def test_my_claims_route_lists_claims(self):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": "Visible claim",
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        resp = self.client.get("/expense/my-claims")
        self.assertIn(b"Visible claim", resp.data)

    def test_other_employee_cannot_view_claim_detail_via_route(self):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": "Private claim",
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        from models.expense_claim import ExpenseClaim

        claim = ExpenseClaim.query.filter_by(title="Private claim").first()

        intruder = self.app.test_client()
        intruder.post(
            "/auth/login?portal=user",
            data={"username": "emp2", "password": "Test@1234"},
        )
        resp = intruder.get(f"/expense/{claim.id}", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(b"Private claim", resp.data)


if __name__ == "__main__":
    unittest.main()
