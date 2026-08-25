import unittest
from datetime import date
from decimal import Decimal
from dao.item_dao import ItemDAO
from dao.policy_dao import PolicyDAO
from dao.claim_dao import ClaimDAO
from service.policy_service import PolicyService
from models.expense_claim import ExpenseClaim
from models.expense_item import ExpenseItem
from models.enums import ClaimStatus
from tests.base import BaseTestCase


class PolicyValidationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.item_dao = ItemDAO()
        self.claim_dao = ClaimDAO()
        self.service = PolicyService(PolicyDAO(), self.item_dao)
        self.claim = ExpenseClaim(
            claim_no="CLM-TEST-001",
            employee_id=self.employee.id,
            title="Policy test claim",
            claim_date=date.today(),
            period_from=date.today(),
            period_to=date.today(),
            status=ClaimStatus.DRAFT,
        )
        self.claim_dao.save(self.claim)

    def _item(self, category_id, amount, save=True):
        item = ExpenseItem(
            claim_id=self.claim.id,
            category_id=category_id,
            expense_date=date.today(),
            description="test item",
            amount=Decimal(amount),
            amount_in_base=Decimal(amount),
        )
        if save:
            self.item_dao.save(item)
        return item

    def test_item_within_all_limits_has_no_violations(self):
        item = self._item(self.category.id, "500")
        violations = self.service.evaluate_item(item, "G3", self.claim.id)
        self.assertEqual(violations, [])

    def test_item_over_per_claim_limit_flagged_high(self):
        item = self._item(self.category.id, "3500")
        violations = self.service.evaluate_item(item, "G3", self.claim.id)
        codes = [v["code"] for v in violations]
        self.assertIn("OVER_CLAIM_LIMIT", codes)
        self.assertEqual(
            violations[codes.index("OVER_CLAIM_LIMIT")]["severity"], "HIGH"
        )

    def test_two_items_same_day_over_daily_limit_flagged(self):
        self._item(self.category.id, "900")
        item2 = self._item(self.category.id, "900")
        violations = self.service.evaluate_item(item2, "G3", self.claim.id)
        codes = [v["code"] for v in violations]
        self.assertIn("OVER_DAILY_LIMIT", codes)

    def test_item_over_receipt_threshold_without_receipt_flagged(self):
        item = self._item(self.category.id, "1200")
        violations = self.service.evaluate_item(item, "G3", self.claim.id)
        codes = [v["code"] for v in violations]
        self.assertIn("MISSING_RECEIPT", codes)

    def test_item_under_receipt_threshold_no_receipt_needed(self):
        item = self._item(self.category.id, "800")
        violations = self.service.evaluate_item(item, "G3", self.claim.id)
        codes = [v["code"] for v in violations]
        self.assertNotIn("MISSING_RECEIPT", codes)

    def test_category_without_active_policy_uses_default_limit(self):
        item = self._item(self.category_hotel.id, "6000")
        violations = self.service.evaluate_item(item, "G3", self.claim.id)
        codes = [v["code"] for v in violations]
        self.assertIn("OVER_DEFAULT_LIMIT", codes)
        self.assertEqual(
            violations[codes.index("OVER_DEFAULT_LIMIT")]["severity"], "MEDIUM"
        )

    def test_category_without_policy_under_default_limit_ok(self):
        item = self._item(self.category_hotel.id, "4000")
        violations = self.service.evaluate_item(item, "G3", self.claim.id)
        self.assertEqual(violations, [])

    def test_wrong_grade_has_no_matching_policy_falls_back_to_default(self):
        item = self._item(self.category.id, "2500")
        violations = self.service.evaluate_item(item, "G5", self.claim.id)
        codes = [v["code"] for v in violations]
        self.assertIn("OVER_DEFAULT_LIMIT", codes)

    def test_evaluate_claim_aggregates_all_item_violations(self):
        self._item(self.category.id, "3500")
        self._item(self.category.id, "1200")
        violations = self.service.evaluate_claim(self.claim)
        self.assertGreaterEqual(len(violations), 2)
        self.assertTrue(self.claim.policy_flag)
        self.assertEqual(self.claim.violation_count, len(violations))

    def test_evaluate_claim_marks_items_with_violation_flag(self):
        self._item(self.category.id, "3500")
        self.service.evaluate_claim(self.claim)
        flagged_items = [i for i in self.claim.items if i.policy_violation]
        self.assertEqual(len(flagged_items), 1)
        self.assertIsNotNone(flagged_items[0].violation_reason)

    def test_evaluate_claim_with_no_violations_leaves_flag_false(self):
        self._item(self.category.id, "500")
        self.service.evaluate_claim(self.claim)
        self.assertFalse(self.claim.policy_flag)
        self.assertEqual(self.claim.violation_count, 0)


if __name__ == "__main__":
    unittest.main()
