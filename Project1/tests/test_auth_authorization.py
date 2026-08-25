import unittest
from tests.base import BaseTestCase


class AuthenticationTests(BaseTestCase):

    def test_login_success_sets_cookies_and_redirects(self):
        resp = self.login("emp1", portal="user")
        self.assertEqual(resp.status_code, 302)
        set_cookie_headers = "".join(resp.headers.get_all("Set-Cookie"))
        self.assertIn("access_token", set_cookie_headers)
        self.assertIn("refresh_token", set_cookie_headers)

    def test_login_success_json_returns_tokens(self):
        resp = self.login_json("emp1", portal="user")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        self.assertEqual(body["user"]["username"], "emp1")

    def test_login_wrong_password_fails(self):
        resp = self.login_json("emp1", password="WrongPass1", portal="user")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid username or password", resp.get_json()["message"])

    def test_login_unknown_username_fails(self):
        resp = self.login_json("nosuchuser", portal="user")
        self.assertEqual(resp.status_code, 401)

    def test_login_locks_account_after_5_failed_attempts(self):
        for _ in range(5):
            self.login_json("emp1", password="WrongPass1", portal="user")
        resp = self.login_json("emp1", portal="user")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("locked", resp.get_json()["message"].lower())

    def test_login_wrong_portal_role_rejected(self):
        resp = self.login_json("mgr1", portal="user")
        self.assertEqual(resp.status_code, 403)
        self.assertIn(
            "This portal is for EMPLOYEE accounts", resp.get_json()["message"]
        )

    def test_admin_bypasses_portal_restriction(self):
        resp = self.login_json("admin1", portal="user")
        self.assertEqual(resp.status_code, 200)

    def test_logout_clears_session(self):
        self.login_as_employee()
        self.client.get("/auth/logout")
        resp = self.client.get("/auth/home", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 401)

    def test_me_endpoint_reflects_logged_in_user(self):
        self.login_as_employee()
        resp = self.client.get("/auth/me")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["username"], "emp1")


class AuthorizationTests(BaseTestCase):

    def test_protected_route_without_token_returns_401_json(self):
        resp = self.client.get("/auth/me", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 401)

    def test_protected_route_without_token_redirects_html(self):
        resp = self.client.get("/employee/dashboard", headers={"Accept": "text/html"})
        self.assertIn(resp.status_code, (302, 401))

    def test_employee_cannot_access_manager_dashboard(self):
        self.login_as_employee()
        resp = self.client.get(
            "/manager/dashboard", headers={"Accept": "application/json"}
        )
        self.assertEqual(resp.status_code, 403)

    def test_employee_cannot_access_finance_dashboard(self):
        self.login_as_employee()
        resp = self.client.get(
            "/finance/dashboard", headers={"Accept": "application/json"}
        )
        self.assertEqual(resp.status_code, 403)

    def test_employee_cannot_access_admin_users(self):
        self.login_as_employee()
        resp = self.client.get("/admin/users", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_access_manager_dashboard(self):
        self.login_as_manager()
        resp = self.client.get("/manager/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_finance_can_access_finance_dashboard(self):
        self.login_as_finance()
        resp = self.client.get("/finance/dashboard")
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_access_admin_users(self):
        self.login_as_admin()
        resp = self.client.get("/admin/users")
        self.assertEqual(resp.status_code, 200)

    def test_manager_cannot_verify_finance_claims(self):
        self.login_as_manager()
        resp = self.client.post(
            "/finance/claim/1/verify",
            data={"decision": "approve"},
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 403)


class TokenRefreshTests(BaseTestCase):

    def test_refresh_without_token_is_rejected(self):
        resp = self.client.post("/auth/refresh", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 401)

    def test_refresh_with_access_token_only_is_rejected(self):
        login_resp = self.login_json("emp1", portal="user")
        access = login_resp.get_json()["access_token"]
        resp = self.client.post(
            "/auth/refresh", json={}, headers={"Authorization": f"Bearer {access}"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_refresh_with_valid_refresh_token_issues_new_access_token(self):
        login_resp = self.login_json("emp1", portal="user")
        refresh = login_resp.get_json()["refresh_token"]
        resp = self.client.post(
            "/auth/refresh", json={}, headers={"Authorization": f"Bearer {refresh}"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access_token", resp.get_json())

    def test_new_access_token_from_refresh_actually_works(self):
        login_resp = self.login_json("emp1", portal="user")
        refresh = login_resp.get_json()["refresh_token"]
        new_access = self.client.post(
            "/auth/refresh", json={}, headers={"Authorization": f"Bearer {refresh}"}
        ).get_json()["access_token"]
        resp = self.client.get(
            "/auth/me", headers={"Authorization": f"Bearer {new_access}"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["username"], "emp1")


if __name__ == "__main__":
    unittest.main()
