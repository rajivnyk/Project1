from decimal import Decimal


class PolicyService:
    def __init__(self, policy_dao, item_dao):
        self.policy_dao = policy_dao
        self.item_dao = item_dao

    def evaluate_item(self, item, grade, claim_id=None):
        violations = []
        policy = self.policy_dao.get_active_policy(
            item.category_id, grade, item.expense_date
        )
        category = item.category
        amount = Decimal(item.amount_in_base)
        if policy is None:
            limit = Decimal(category.default_limit or 0)
            if limit and amount > limit:
                violations.append(
                    {
                        "code": "OVER_DEFAULT_LIMIT",
                        "severity": "MEDIUM",
                        "message": f"{category.name}: Rs.{amount} exceeds the default limit of Rs.{limit}",
                    }
                )
            return violations
        if amount > Decimal(policy.max_amount_per_claim):
            violations.append(
                {
                    "code": "OVER_CLAIM_LIMIT",
                    "severity": "MEDIUM",
                    "message": f"{category.name}: Rs.{amount} exceeds the per-claim limit of Rs.{policy.max_amount_per_claim} for grade {grade}",
                }
            )
        if claim_id:
            same_day = Decimal(
                self.item_dao.daily_total(
                    claim_id,
                    item.category_id,
                    item.expense_date,
                    exclude_item_id=item.id,
                )
            )
            if same_day + amount > Decimal(policy.max_amount_per_day):
                violations.append(
                    {
                        "code": "OVER_DAILY_LIMIT",
                        "severity": "MEDIUM",
                        "message": f"{category.name} on {item.expense_date}: total Rs.{same_day + amount} exceeds the daily limit of Rs.{policy.max_amount_per_day}",
                    }
                )
        needs_receipt = category.requires_receipt or amount > Decimal(
            policy.receipt_required_above or 0
        )
        has_general_receipt = any(r.item_id is None for r in item.claim.receipts) if item.claim else False
        if needs_receipt and not item.receipts and not has_general_receipt:
            violations.append(
                {
                    "code": "MISSING_RECEIPT",
                    "severity": "HIGH",
                    "message": f"{category.name}: a receipt is mandatory for Rs.{amount}",
                }
            )
        return violations

    def evaluate_claim(self, claim):
        grade = claim.employee.grade
        all_violations = []
        for item in claim.items:
            v = self.evaluate_item(item, grade, claim.id)
            item.policy_violation = bool(v)
            item.violation_reason = " | ".join(x["message"] for x in v) if v else None
            all_violations.extend(v)
        claim.policy_flag = bool(all_violations)
        claim.violation_count = len(all_violations)
        return all_violations
