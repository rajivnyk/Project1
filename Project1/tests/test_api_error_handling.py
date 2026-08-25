import unittest
from datetime import date
from tests.base import BaseTestCase


class ApiErrorHandlingTests(BaseTestCase):

    def test_unknown_route_returns_404(self):
        resp = self.client.get("/this-route-does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def test_login_bad_json_body_returns_401_not_500(self):
        resp = self.client.post("/auth/login?portal=user", json={"username": "emp1"})
        self.assertEqual(resp.status_code, 401)

    def test_login_missing_credentials_returns_401(self):
        resp = self.client.post("/auth/login?portal=user", json={})
        self.assertEqual(resp.status_code, 401)

    def test_protected_json_endpoint_without_token_returns_401(self):
        resp = self.client.get(
            "/api/analytics/spend-by-category", headers={"Accept": "application/json"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_role_gated_json_endpoint_wrong_role_returns_403(self):
        self.login_as_employee()
        resp = self.client.get("/api/analytics/top-spenders")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("error", resp.get_json())

    def test_overdue_endpoint_forbidden_for_employee(self):
        self.login_as_employee()
        resp = self.client.get("/api/analytics/overdue")
        self.assertEqual(resp.status_code, 403)

    def test_overdue_endpoint_allowed_for_manager(self):
        self.login_as_manager()
        resp = self.client.get("/api/analytics/overdue")
        self.assertEqual(resp.status_code, 200)

    def test_verify_nonexistent_claim_shows_error_not_crash(self):
        self.login_as_finance()
        resp = self.client.post(
            "/finance/claim/999999/verify",
            data={"decision": "approve"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"not found", resp.data.lower())

    def test_reimburse_nonexistent_claim_shows_error_not_crash(self):
        self.login_as_finance()
        resp = self.client.post(
            "/finance/claim/999999/reimburse", data={}, follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"not found", resp.data.lower())

    def test_edit_nonexistent_claim_redirects_gracefully(self):
        self.login_as_employee()
        resp = self.client.get("/expense/999999/edit", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_create_claim_missing_title_reshows_form_not_500(self):
        self.login_as_employee()
        resp = self.client.post(
            "/expense/new",
            data={
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"required", resp.data.lower())

    def test_add_item_bad_amount_returns_error_not_500(self):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": "Bad amount test",
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        from models.expense_claim import ExpenseClaim

        claim = ExpenseClaim.query.filter_by(title="Bad amount test").first()
        resp = self.client.post(
            f"/expense/{claim.id}/item/add",
            data={
                "category_id": str(self.category.id),
                "expense_date": date.today().isoformat(),
                "description": "bad",
                "amount": "not-a-number",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"must be a number", resp.data)

    def test_manager_decide_invalid_claim_id_handled(self):
        self.login_as_manager()
        resp = self.client.post(
            "/manager/claim/999999/decide",
            data={"decision": "approve"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

    def test_travel_new_missing_required_fields_shows_error(self):
        self.login_as_employee()
        resp = self.client.post("/travel/new", data={}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"required", resp.data.lower())

    def test_malformed_expense_date_returns_error_not_500(self):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": "Date format test",
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        from models.expense_claim import ExpenseClaim

        claim = ExpenseClaim.query.filter_by(title="Date format test").first()
        resp = self.client.post(
            f"/expense/{claim.id}/item/add",
            data={
                "category_id": str(self.category.id),
                "expense_date": "23/08/2026",
                "description": "bad date",
                "amount": "100",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"valid date", resp.data)


if __name__ == "__main__":
    unittest.main()
