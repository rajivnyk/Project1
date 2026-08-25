"""Regression guards for bugs found during the full-codebase audit.

Each test here maps to a defect that was reachable from the UI and produced a
500 (or silently stranded data) before it was fixed.
"""

import unittest
from datetime import date, timedelta
from config.database import db
from models.enums import TravelStatus, ClaimStatus
from models.travel_request import TravelRequest
from models.expense_claim import ExpenseClaim
from tests.base import BaseTestCase


class TravelStatusCrashTests(BaseTestCase):
    """`tr.status.name` blew up: status is a plain str column, not an Enum."""

    def _payload(self):
        return {
            "purpose": "Client visit",
            "destination_city": "Mumbai",
            "from_date": date.today().isoformat(),
            "to_date": (date.today() + timedelta(days=1)).isoformat(),
            "estimated_cost": "5000",
        }

    def test_create_travel_request_does_not_500(self):
        self.login_as_employee()
        resp = self.client.post(
            "/travel/new", data=self._payload(), follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"submitted for manager approval", resp.data.lower())

    def test_managerless_employee_travel_is_auto_approved(self):
        self.employee.manager_id = None
        db.session.commit()
        self.login_as_employee()
        resp = self.client.post(
            "/travel/new", data=self._payload(), follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"auto-approved", resp.data.lower())
        tr = TravelRequest.query.filter_by(employee_id=self.employee.id).first()
        self.assertEqual(tr.status, TravelStatus.APPROVED)


class BankingGateTests(BaseTestCase):
    """The banking-details gate must redirect, never crash."""

    def test_expense_new_redirects_when_bank_details_missing(self):
        self.employee.bank_account_no = None
        self.employee.ifsc_code = None
        db.session.commit()
        self.login_as_employee()
        resp = self.client.get("/expense/new", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"banking details", resp.data)

    def test_travel_new_redirects_when_bank_details_missing(self):
        self.employee.ifsc_code = None
        db.session.commit()
        self.login_as_employee()
        resp = self.client.get("/travel/new", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"banking details", resp.data)

    def test_expense_new_allowed_when_bank_details_present(self):
        self.login_as_employee()
        resp = self.client.get("/expense/new")
        self.assertEqual(resp.status_code, 200)


class AdminRobustnessTests(BaseTestCase):
    """admin routes had no None-checks or input validation at all."""

    def test_toggle_missing_user_does_not_500(self):
        self.login_as_admin()
        resp = self.client.post("/admin/users/999999/toggle", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"User not found", resp.data)

    def test_toggle_existing_user_flips_active_flag(self):
        self.login_as_admin()
        was_active = self.employee_user.is_active
        self.client.post(
            f"/admin/users/{self.employee_user.id}/toggle", follow_redirects=True
        )
        db.session.refresh(self.employee_user)
        self.assertNotEqual(self.employee_user.is_active, was_active)

    def test_policy_with_non_numeric_amount_does_not_500(self):
        self.login_as_admin()
        resp = self.client.post(
            "/admin/policies",
            data={
                "category_id": str(self.category.id),
                "grade": "G3",
                "max_amount_per_day": "abc",
                "max_amount_per_claim": "500",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"must be a number", resp.data)

    def test_policy_with_unknown_category_does_not_500(self):
        self.login_as_admin()
        resp = self.client.post(
            "/admin/policies",
            data={
                "category_id": "999999",
                "grade": "G3",
                "max_amount_per_day": "100",
                "max_amount_per_claim": "500",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Category not found", resp.data)

    def test_valid_policy_is_saved(self):
        self.login_as_admin()
        resp = self.client.post(
            "/admin/policies",
            data={
                "category_id": str(self.category_hotel.id),
                "grade": "G2",
                "max_amount_per_day": "1000",
                "max_amount_per_claim": "4000",
                "receipt_required_above": "500",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Policy saved", resp.data)


class ItemReviewParsingTests(BaseTestCase):
    """float() on a blank/garbage approved_amount used to raise mid-request."""

    def _submitted_claim(self, title="Review parse claim"):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": title,
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        claim = ExpenseClaim.query.filter_by(title=title).first()
        self.client.post(
            f"/expense/{claim.id}/item/add",
            data={
                "category_id": str(self.category.id),
                "expense_date": date.today().isoformat(),
                "description": "Taxi",
                "amount": "500",
            },
        )
        self.client.post(f"/expense/{claim.id}/submit")
        return ExpenseClaim.query.get(claim.id)

    def _manager_client(self):
        c = self.app.test_client()
        c.post(
            "/auth/login?portal=manager",
            data={"username": "mgr1", "password": "Test@1234"},
        )
        return c

    def test_blank_approved_amount_defaults_to_claimed(self):
        claim = self._submitted_claim("Blank amount claim")
        item_id = claim.items[0].id
        resp = self._manager_client().post(
            f"/manager/claim/{claim.id}/decide",
            data={"decision": "approve", f"approved_amount_{item_id}": ""},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        refreshed = ExpenseClaim.query.get(claim.id)
        self.assertEqual(refreshed.status, ClaimStatus.MANAGER_APPROVED)
        self.assertEqual(
            refreshed.items[0].approved_amount, refreshed.items[0].amount_in_base
        )

    def test_garbage_approved_amount_does_not_500(self):
        claim = self._submitted_claim("Garbage amount claim")
        item_id = claim.items[0].id
        resp = self._manager_client().post(
            f"/manager/claim/{claim.id}/decide",
            data={"decision": "approve", f"approved_amount_{item_id}": "not-a-number"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"must be a number", resp.data)
        self.assertEqual(ExpenseClaim.query.get(claim.id).status, ClaimStatus.SUBMITTED)

    def test_explicit_approved_amount_is_honoured(self):
        claim = self._submitted_claim("Explicit amount claim")
        item_id = claim.items[0].id
        self._manager_client().post(
            f"/manager/claim/{claim.id}/decide",
            data={"decision": "approve", f"approved_amount_{item_id}": "300"},
            follow_redirects=True,
        )
        refreshed = ExpenseClaim.query.get(claim.id)
        self.assertEqual(float(refreshed.items[0].approved_amount), 300.00)


class NoEmployeeProfileTests(BaseTestCase):
    """FINANCE/ADMIN users have no Employee row; those routes must not crash."""

    def test_finance_can_open_employee_profile_page(self):
        self.login_as_finance()
        resp = self.client.get("/employee/profile", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_finance_posting_profile_does_not_500(self):
        self.login_as_finance()
        resp = self.client.post(
            "/employee/profile", data={"full_name": "Nope"}, follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)

    def test_finance_can_open_reports(self):
        self.login_as_finance()
        self.assertEqual(self.client.get("/reports/").status_code, 200)

    def test_admin_analytics_endpoints_do_not_500(self):
        self.login_as_admin()
        for path in (
            "/api/analytics/spend-by-category",
            "/api/analytics/monthly-trend",
            "/api/analytics/policy-violations",
            "/api/analytics/turnaround",
            "/api/analytics/top-spenders",
            "/api/analytics/overdue",
            "/api/analytics/budget-utilization",
        ):
            self.assertEqual(self.client.get(path).status_code, 200, msg=path)

    def test_analytics_tolerates_bad_query_params(self):
        self.login_as_admin()
        self.assertEqual(
            self.client.get("/api/analytics/monthly-trend?months=abc").status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/analytics/monthly-trend?months=0").status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/analytics/top-spenders?limit=0").status_code, 200
        )


class ChangePasswordTests(BaseTestCase):
    """New route: must not 500 on missing/None form fields."""

    def test_change_password_page_renders(self):
        self.login_as_employee()
        self.assertEqual(self.client.get("/auth/change-password").status_code, 200)

    def test_change_password_with_empty_fields_does_not_500(self):
        self.login_as_employee()
        resp = self.client.post("/auth/change-password", data={}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_change_password_mismatch_is_reported(self):
        self.login_as_employee()
        resp = self.client.post(
            "/auth/change-password",
            data={
                "old_password": "Test@1234",
                "new_password": "NewPass123",
                "confirm_password": "Different123",
            },
            follow_redirects=True,
        )
        self.assertIn(b"do not match", resp.data)

    def test_change_password_wrong_current_is_reported(self):
        self.login_as_employee()
        resp = self.client.post(
            "/auth/change-password",
            data={
                "old_password": "WrongOne1",
                "new_password": "NewPass123",
                "confirm_password": "NewPass123",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Current password is incorrect", resp.data)

    def test_change_password_too_short_is_reported(self):
        self.login_as_employee()
        resp = self.client.post(
            "/auth/change-password",
            data={
                "old_password": "Test@1234",
                "new_password": "short",
                "confirm_password": "short",
            },
            follow_redirects=True,
        )
        self.assertIn(b"at least 8 characters", resp.data)

    def test_change_password_success(self):
        self.login_as_employee()
        resp = self.client.post(
            "/auth/change-password",
            data={
                "old_password": "Test@1234",
                "new_password": "BrandNew123",
                "confirm_password": "BrandNew123",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        fresh = self.app.test_client()
        ok = fresh.post(
            "/auth/login?portal=user",
            json={"username": "emp1", "password": "BrandNew123"},
        )
        self.assertEqual(ok.status_code, 200)


if __name__ == "__main__":
    unittest.main()


class ClaimDetailTemplateTests(BaseTestCase):
    """claim_detail.html used claim.approval_history / .created_at, which don't
    exist on the model (it's claim.history / .acted_at) -- crashed under
    StrictUndefined whenever a rejected claim's detail page was opened."""

    def _rejected_claim(self):
        from dao.claim_dao import ClaimDAO
        from dao.item_dao import ItemDAO
        from dao.category_dao import CategoryDAO
        from dao.policy_dao import PolicyDAO
        from dao.approval_dao import ApprovalDAO
        from service.policy_service import PolicyService
        from service.approval_service import ApprovalService
        from service.expense_service import ExpenseService

        claim_dao, item_dao, category_dao = ClaimDAO(), ItemDAO(), CategoryDAO()
        policy_service = PolicyService(PolicyDAO(), item_dao)
        approval_service = ApprovalService(ApprovalDAO())
        svc = ExpenseService(claim_dao, item_dao, category_dao, policy_service, approval_service)

        claim = svc.create_claim(self.employee, {
            "title": "Rejection view test",
            "period_from": date.today().isoformat(),
            "period_to": date.today().isoformat()})
        svc.add_item(claim, {
            "category_id": str(self.category.id),
            "expense_date": date.today().isoformat(),
            "description": "Cab", "amount": "500"})
        svc.submit_claim(claim.id, self.employee, self.employee_user)
        approval_service.assert_is_manager_of(self.manager, claim)
        approval_service.transition(claim, ClaimStatus.MANAGER_REJECTED, self.manager_user,
                                    "REJECTED", comments="Missing itemized bill")
        return claim.id

    def test_rejected_claim_detail_page_renders(self):
        claim_id = self._rejected_claim()
        self.login_as_employee()
        resp = self.client.get(f"/expense/{claim_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Claim Rejected", resp.data)
        self.assertIn(b"Missing itemized bill", resp.data)


class FinanceDashboardTitleTests(BaseTestCase):
    """finance_dashboard.html's {% block title %} used to swallow the entire
    reimburse-modal for-loop, dumping raw HTML into <title> and duplicating
    the modal markup. Verifies the title is clean and each modal id is unique."""

    def test_dashboard_title_is_clean(self):
        self.login_as_finance()
        resp = self.client.get("/finance/dashboard")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode()
        title_start = html.index("<title>") + len("<title>")
        title_end = html.index("</title>")
        title = html[title_start:title_end]
        self.assertNotIn("<div", title)
        self.assertNotIn("{%", title)
        self.assertLess(len(title), 80)

    def test_reimburse_modal_ids_are_not_duplicated(self):
        from dao.claim_dao import ClaimDAO
        from dao.item_dao import ItemDAO
        from dao.category_dao import CategoryDAO
        from dao.policy_dao import PolicyDAO
        from dao.approval_dao import ApprovalDAO
        from service.policy_service import PolicyService
        from service.approval_service import ApprovalService
        from service.expense_service import ExpenseService

        claim_dao, item_dao, category_dao = ClaimDAO(), ItemDAO(), CategoryDAO()
        policy_service = PolicyService(PolicyDAO(), item_dao)
        approval_service = ApprovalService(ApprovalDAO())
        svc = ExpenseService(claim_dao, item_dao, category_dao, policy_service, approval_service)

        claim = svc.create_claim(self.employee, {
            "title": "Ready to pay", "period_from": date.today().isoformat(),
            "period_to": date.today().isoformat()})
        svc.add_item(claim, {
            "category_id": str(self.category.id),
            "expense_date": date.today().isoformat(),
            "description": "Cab", "amount": "500"})
        claim.status = ClaimStatus.FINANCE_VERIFIED
        db.session.commit()

        self.login_as_finance()
        resp = self.client.get("/finance/dashboard")
        html = resp.data.decode()
        marker = f'id="reimburseModal{claim.id}"'
        self.assertEqual(html.count(marker), 1)
