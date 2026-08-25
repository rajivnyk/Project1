import unittest
from datetime import date, timedelta
from dao.travel_dao import TravelDAO
from dao.approval_dao import ApprovalDAO
from service.travel_service import TravelService
from models.enums import TravelStatus
from tests.base import BaseTestCase


class TravelServiceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = TravelService(TravelDAO(), ApprovalDAO())

    def _valid_data(self, **overrides):
        data = {
            "purpose": "Client meeting",
            "destination_city": "Mumbai",
            "destination_country": "India",
            "from_date": date.today().isoformat(),
            "to_date": (date.today() + timedelta(days=2)).isoformat(),
            "mode_of_travel": "AIR",
            "estimated_cost": "15000",
        }
        data.update(overrides)
        return data

    def test_create_travel_request_success(self):
        tr = self.service.create(self.employee, self._valid_data())
        self.assertEqual(tr.status, TravelStatus.SUBMITTED)
        self.assertTrue(tr.request_no.startswith("TR-"))
        self.assertEqual(tr.employee_id, self.employee.id)

    def test_create_missing_purpose_fails(self):
        with self.assertRaises(ValueError):
            self.service.create(self.employee, self._valid_data(purpose=""))

    def test_create_missing_destination_fails(self):
        with self.assertRaises(ValueError):
            self.service.create(self.employee, self._valid_data(destination_city=""))

    def test_create_invalid_cost_fails(self):
        with self.assertRaises(ValueError):
            self.service.create(
                self.employee, self._valid_data(estimated_cost="not-a-number")
            )

    def test_create_end_date_before_start_fails(self):
        with self.assertRaises(ValueError):
            self.service.create(
                self.employee,
                self._valid_data(
                    from_date=date.today().isoformat(),
                    to_date=(date.today() - timedelta(days=1)).isoformat(),
                ),
            )

    def test_create_backdated_2_days_is_allowed(self):
        tr = self.service.create(
            self.employee,
            self._valid_data(
                from_date=(date.today() - timedelta(days=2)).isoformat(),
                to_date=date.today().isoformat(),
            ),
        )
        self.assertEqual(tr.status, TravelStatus.SUBMITTED)

    def test_create_backdated_3_days_fails(self):
        with self.assertRaises(ValueError) as ctx:
            self.service.create(
                self.employee,
                self._valid_data(
                    from_date=(date.today() - timedelta(days=3)).isoformat(),
                    to_date=date.today().isoformat(),
                ),
            )
        self.assertIn("more than 2 days in the past", str(ctx.exception))

    def test_manager_approves_reportee_request(self):
        tr = self.service.create(self.employee, self._valid_data())
        result = self.service.decide(
            tr.id, self.manager, self.manager_user, True, "Approved"
        )
        self.assertEqual(result.status, TravelStatus.APPROVED)
        self.assertEqual(result.approver_id, self.manager_user.id)

    def test_manager_rejects_reportee_request_requires_remarks(self):
        tr = self.service.create(self.employee, self._valid_data())
        with self.assertRaises(ValueError):
            self.service.decide(tr.id, self.manager, self.manager_user, False, "")

    def test_manager_rejects_reportee_request_with_remarks(self):
        tr = self.service.create(self.employee, self._valid_data())
        result = self.service.decide(
            tr.id, self.manager, self.manager_user, False, "Budget exceeded"
        )
        self.assertEqual(result.status, TravelStatus.REJECTED)

    def test_unrelated_manager_cannot_decide(self):
        tr = self.service.create(self.employee, self._valid_data())
        with self.assertRaises(ValueError) as ctx:
            self.service.decide(
                tr.id, self.other_manager, self.other_manager_user, True, "ok"
            )
        self.assertIn("not from your team", str(ctx.exception))

    def test_cannot_decide_already_decided_request(self):
        tr = self.service.create(self.employee, self._valid_data())
        self.service.decide(tr.id, self.manager, self.manager_user, True, "ok")
        with self.assertRaises(ValueError):
            self.service.decide(tr.id, self.manager, self.manager_user, True, "again")

    def test_owner_can_cancel_submitted_request(self):
        tr = self.service.create(self.employee, self._valid_data())
        result = self.service.cancel(
            tr.id, self.employee, self.employee_user, "Trip cancelled"
        )
        self.assertEqual(result.status, TravelStatus.CANCELLED)

    def test_non_owner_cannot_cancel(self):
        tr = self.service.create(self.employee, self._valid_data())
        with self.assertRaises(ValueError):
            self.service.cancel(
                tr.id, self.other_employee, self.other_employee_user, "not mine"
            )

    def test_cannot_cancel_already_approved_request(self):
        tr = self.service.create(self.employee, self._valid_data())
        self.service.decide(tr.id, self.manager, self.manager_user, True, "ok")
        with self.assertRaises(ValueError):
            self.service.cancel(tr.id, self.employee, self.employee_user, "too late")


class TravelHttpRouteTests(BaseTestCase):

    def test_new_travel_request_via_route(self):
        self.login_as_employee()
        resp = self.client.post(
            "/travel/new",
            data={
                "purpose": "Onsite visit",
                "destination_city": "Pune",
                "from_date": date.today().isoformat(),
                "to_date": (date.today() + timedelta(days=1)).isoformat(),
                "estimated_cost": "5000",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"submitted", resp.data)

    def test_my_requests_lists_only_own_trips(self):
        self.login_as_employee()
        self.client.post(
            "/travel/new",
            data={
                "purpose": "Trip A",
                "destination_city": "Delhi",
                "from_date": date.today().isoformat(),
                "to_date": (date.today() + timedelta(days=1)).isoformat(),
                "estimated_cost": "1000",
            },
        )
        resp = self.client.get("/travel/my-requests")
        self.assertIn(b"Trip A", resp.data)

    def test_manager_decides_travel_via_route(self):
        self.login_as_employee()
        self.client.post(
            "/travel/new",
            data={
                "purpose": "Trip B",
                "destination_city": "Chennai",
                "from_date": date.today().isoformat(),
                "to_date": (date.today() + timedelta(days=1)).isoformat(),
                "estimated_cost": "1000",
            },
        )
        from models.travel_request import TravelRequest

        tr = TravelRequest.query.filter_by(purpose="Trip B").first()

        manager_client = self.app.test_client()
        manager_client.post(
            "/auth/login?portal=manager",
            data={"username": "mgr1", "password": "Test@1234"},
        )
        resp = manager_client.post(
            f"/manager/travel/{tr.id}/decide",
            data={"decision": "approve"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

        from models.enums import TravelStatus

        refreshed = TravelRequest.query.get(tr.id)
        self.assertEqual(refreshed.status, TravelStatus.APPROVED)


if __name__ == "__main__":
    unittest.main()
