import unittest
from datetime import date, timedelta
from decimal import Decimal
from dao.user_dao import UserDAO
from dao.employee_dao import EmployeeDAO
from dao.claim_dao import ClaimDAO
from dao.item_dao import ItemDAO
from dao.category_dao import CategoryDAO
from dao.policy_dao import PolicyDAO
from dao.receipt_dao import ReceiptDAO
from dao.travel_dao import TravelDAO
from models.user import User
from models.expense_claim import ExpenseClaim
from models.expense_item import ExpenseItem
from models.expense_category import ExpenseCategory
from models.expense_policy import ExpensePolicy
from models.enums import ClaimStatus, Role
from werkzeug.security import generate_password_hash
from tests.base import BaseTestCase


class UserDaoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.dao = UserDAO()

    def test_get_by_username_found(self):
        self.assertEqual(self.dao.get_by_username("emp1").id, self.employee_user.id)

    def test_get_by_username_not_found(self):
        self.assertIsNone(self.dao.get_by_username("ghost"))

    def test_get_by_email_case_insensitive(self):
        self.assertEqual(
            self.dao.get_by_email("EMP1@TEST.COM").id, self.employee_user.id
        )

    def test_save_persists_new_user(self):
        user = self.dao.save(
            User(
                username="newbie",
                email="newbie@test.com",
                password_hash=generate_password_hash("x"),
                role=Role.EMPLOYEE,
            )
        )
        self.assertIsNotNone(user.id)
        self.assertEqual(self.dao.get_by_id(user.id).username, "newbie")

    def test_get_all_returns_seeded_users(self):
        self.assertGreaterEqual(len(self.dao.get_all()), 6)


class EmployeeDaoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.dao = EmployeeDAO()

    def test_reportee_ids_returns_direct_reports_only(self):
        ids = self.dao.reportee_ids(self.manager.id)
        self.assertEqual(ids, [self.employee.id])

    def test_reportee_ids_empty_for_no_reports(self):
        self.assertEqual(self.dao.reportee_ids(self.employee.id), [])

    def test_get_reportees_excludes_inactive(self):
        self.employee.is_active = False
        from config.database import db

        db.session.commit()
        self.assertEqual(self.dao.get_reportees(self.manager.id), [])

    def test_get_by_user_finds_linked_employee(self):
        emp = self.dao.get_by_user(self.employee_user.id)
        self.assertEqual(emp.id, self.employee.id)


class ClaimDaoTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.dao = ClaimDAO()

    def _make_claim(self, no, title, status=ClaimStatus.DRAFT, amount=1000):
        return self.dao.save(
            ExpenseClaim(
                claim_no=no,
                employee_id=self.employee.id,
                title=title,
                claim_date=date.today(),
                period_from=date.today(),
                period_to=date.today(),
                status=status,
                total_amount=amount,
            )
        )

    def test_get_by_employee_orders_newest_first(self):
        # created_at is a MySQL DATETIME with second precision, so two rows
        # inserted in the same second would tie; set explicit timestamps a
        # minute apart to test the ORDER BY behavior deterministically.
        from datetime import datetime, timedelta as _timedelta

        older = self._make_claim("CLM-D-0001", "First")
        newer = self._make_claim("CLM-D-0002", "Second")
        older.created_at = datetime.utcnow() - _timedelta(minutes=5)
        newer.created_at = datetime.utcnow()
        from config.database import db

        db.session.commit()
        claims = self.dao.get_by_employee(self.employee.id)
        self.assertEqual(claims[0].title, "Second")

    def test_get_by_employee_filters_by_status(self):
        self._make_claim("CLM-D-0003", "Draft claim", status=ClaimStatus.DRAFT)
        self._make_claim("CLM-D-0004", "Submitted claim", status=ClaimStatus.SUBMITTED)
        submitted = self.dao.get_by_employee(
            self.employee.id, status=ClaimStatus.SUBMITTED
        )
        self.assertEqual(len(submitted), 1)
        self.assertEqual(submitted[0].title, "Submitted claim")

    def test_get_by_status_returns_matching_claims(self):
        self._make_claim(
            "CLM-D-0005", "Verified one", status=ClaimStatus.FINANCE_VERIFIED
        )
        results = self.dao.get_by_status(ClaimStatus.FINANCE_VERIFIED)
        self.assertEqual(len(results), 1)

    def test_get_pending_for_manager_scoped_to_reportees(self):
        self._make_claim("CLM-D-0006", "Team claim", status=ClaimStatus.SUBMITTED)
        results = self.dao.get_pending_for_manager(
            [self.employee.id], ClaimStatus.SUBMITTED
        )
        self.assertEqual(len(results), 1)

    def test_get_pending_for_manager_empty_reportee_list(self):
        self.assertEqual(
            self.dao.get_pending_for_manager([], ClaimStatus.SUBMITTED), []
        )

    def test_search_by_keyword_matches_title(self):
        self._make_claim("CLM-D-0007", "Conference travel Mumbai")
        page = self.dao.search(keyword="Mumbai")
        self.assertEqual(page.total, 1)

    def test_search_by_status_filter(self):
        self._make_claim("CLM-D-0008", "A", status=ClaimStatus.DRAFT)
        self._make_claim("CLM-D-0009", "B", status=ClaimStatus.SUBMITTED)
        page = self.dao.search(status=ClaimStatus.SUBMITTED)
        self.assertEqual(page.total, 1)

    def test_search_pagination(self):
        for i in range(15):
            self._make_claim(f"CLM-P-{i:04d}", f"Paged {i}")
        page1 = self.dao.search(page=1, per_page=10)
        page2 = self.dao.search(page=2, per_page=10)
        self.assertEqual(len(page1.items), 10)
        self.assertEqual(len(page2.items), 5)

    def test_recalc_total_sums_items(self):
        claim = self._make_claim("CLM-D-0010", "Sum test")
        item_dao = ItemDAO()
        item_dao.save(
            ExpenseItem(
                claim_id=claim.id,
                category_id=self.category.id,
                expense_date=date.today(),
                description="x",
                amount=Decimal("100"),
                amount_in_base=Decimal("100"),
            )
        )
        item_dao.save(
            ExpenseItem(
                claim_id=claim.id,
                category_id=self.category.id,
                expense_date=date.today(),
                description="y",
                amount=Decimal("50"),
                amount_in_base=Decimal("50"),
            )
        )
        self.assertEqual(self.dao.recalc_total(claim.id), Decimal("150.00"))

    def test_delete_removes_claim(self):
        claim = self._make_claim("CLM-D-0011", "To delete")
        claim_id = claim.id
        self.dao.delete(claim)
        self.assertIsNone(self.dao.get_by_id(claim_id))


class CategoryAndPolicyDaoTests(BaseTestCase):
    def test_get_active_excludes_inactive_categories(self):
        from config.database import db

        inactive = ExpenseCategory(code="OLD", name="Retired", is_active=False)
        db.session.add(inactive)
        db.session.commit()
        active = CategoryDAO().get_active()
        self.assertNotIn(inactive.id, [c.id for c in active])

    def test_get_active_policy_within_effective_window(self):
        policy = PolicyDAO().get_active_policy(self.category.id, "G3")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.id, self.policy.id)

    def test_get_active_policy_none_before_effective_from(self):
        self.assertIsNone(
            PolicyDAO().get_active_policy(
                self.category.id,
                "G3",
                on_date=self.policy.effective_from - timedelta(days=1),
            )
        )

    def test_get_active_policy_none_after_effective_to(self):
        self.policy.effective_to = date.today() - timedelta(days=1)
        from config.database import db

        db.session.commit()
        self.assertIsNone(PolicyDAO().get_active_policy(self.category.id, "G3"))

    def test_get_active_policy_wrong_grade_returns_none(self):
        self.assertIsNone(PolicyDAO().get_active_policy(self.category.id, "G9"))


class ReceiptDaoTests(BaseTestCase):
    def test_get_by_checksum_finds_duplicate(self):
        from models.expense_receipt import ExpenseReceipt

        claim = ClaimDAO().save(
            ExpenseClaim(
                claim_no="CLM-CK-0001",
                employee_id=self.employee.id,
                title="checksum test",
                claim_date=date.today(),
                period_from=date.today(),
                period_to=date.today(),
                status=ClaimStatus.DRAFT,
            )
        )
        receipt = ReceiptDAO().save(
            ExpenseReceipt(
                claim_id=claim.id,
                original_filename="a.pdf",
                stored_filename="stored_a.pdf",
                file_path="stored_a.pdf",
                file_type="pdf",
                file_size=10,
                checksum_sha256="abc123",
                uploaded_by=self.employee_user.id,
            )
        )
        found = ReceiptDAO().get_by_checksum("abc123")
        self.assertEqual(found.id, receipt.id)

    def test_get_by_checksum_no_match_returns_none(self):
        self.assertIsNone(ReceiptDAO().get_by_checksum("does-not-exist"))


class TravelDaoTests(BaseTestCase):
    def test_get_approved_for_employee_filters_status(self):
        from models.travel_request import TravelRequest
        from models.enums import TravelStatus

        dao = TravelDAO()
        dao.save(
            TravelRequest(
                request_no="TR-DAO-0001",
                employee_id=self.employee.id,
                purpose="p",
                destination_city="c",
                from_date=date.today(),
                to_date=date.today(),
                estimated_cost=100,
                status=TravelStatus.APPROVED,
            )
        )
        dao.save(
            TravelRequest(
                request_no="TR-DAO-0002",
                employee_id=self.employee.id,
                purpose="p2",
                destination_city="c2",
                from_date=date.today(),
                to_date=date.today(),
                estimated_cost=100,
                status=TravelStatus.SUBMITTED,
            )
        )
        approved = dao.get_approved_for_employee(self.employee.id)
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0].request_no, "TR-DAO-0001")


if __name__ == "__main__":
    unittest.main()
