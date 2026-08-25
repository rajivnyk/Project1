from datetime import date
from decimal import Decimal
from config.database import db
from models.expense_claim import ExpenseClaim
from models.expense_item import ExpenseItem
from models.enums import ClaimStatus, Action
from util.helpers import generate_sequence, money
from util.validators import require, to_decimal, to_date, validate_date_range


class ExpenseService:
    def __init__(
        self, claim_dao, item_dao, category_dao, policy_service, approval_service
    ):
        self.claim_dao = claim_dao
        self.item_dao = item_dao
        self.category_dao = category_dao
        self.policy_service = policy_service
        self.approval_service = approval_service

    def create_claim(self, employee, data):
        title = require(data.get("title"), "Title")
        period_from = to_date(data.get("period_from"), "Period from")
        period_to = to_date(data.get("period_to"), "Period to")
        validate_date_range(period_from, period_to, "Claim period")
        claim = ExpenseClaim(
            claim_no=generate_sequence("CLM", ExpenseClaim, "claim_no"),
            employee_id=employee.id,
            travel_request_id=data.get("travel_request_id") or None,
            title=title,
            claim_date=date.today(),
            period_from=period_from,
            period_to=period_to,
            status=ClaimStatus.DRAFT,
        )
        return self.claim_dao.save(claim)

    def is_editable(self, claim):
        return claim.status in ClaimStatus.EDITABLE

    def get_owned_claim(self, claim_id, employee, editable_only=False):
        claim = self.claim_dao.get_by_id(claim_id)
        if claim is None:
            raise ValueError("Claim not found")
        if claim.employee_id != employee.id:
            raise ValueError("You may only work on your own claims")
        if editable_only and not self.is_editable(claim):
            raise ValueError(f"Claim is {claim.status} and can no longer be edited")
        return claim

    def add_item(self, claim, data):
        category_id = int(require(data.get("category_id"), "Category"))
        if self.category_dao.get_by_id(category_id) is None:
            raise ValueError("Category not found")
        expense_date = to_date(data.get("expense_date"), "Expense date")
        if claim.period_from and not (
            claim.period_from <= expense_date <= claim.period_to
        ):
            raise ValueError(
                f"Expense date must be between {claim.period_from} and {claim.period_to}"
            )
        if expense_date > date.today():
            raise ValueError("Expense date cannot be in the future")
        amount = to_decimal(data.get("amount"), "Amount")
        rate = to_decimal(
            data.get("exchange_rate", 1), "Exchange rate", min_value=Decimal("0.0001")
        )
        item = ExpenseItem(
            claim_id=claim.id,
            category_id=category_id,
            expense_date=expense_date,
            description=require(data.get("description"), "Description"),
            amount=amount,
            currency=data.get("currency", "INR").upper(),
            exchange_rate=rate,
            amount_in_base=money(amount * rate),
            vendor=data.get("vendor"),
            city=data.get("city"),
        )
        self.item_dao.save(item)
        self._recalculate_total(claim)
        return item

    def delete_item(self, claim, item_id):
        item = self.item_dao.get_by_id(item_id)
        if item is None or item.claim_id != claim.id:
            raise ValueError("Expense item not found on this claim")
        self.item_dao.delete(item)
        self._recalculate_total(claim)

    def _recalculate_total(self, claim):
        claim.total_amount = money(self.claim_dao.recalc_total(claim.id))
        self.claim_dao.update()

    def submit_claim(self, claim_id, employee, user):
        claim = self.get_owned_claim(claim_id, employee, editable_only=True)
        if not claim.items:
            raise ValueError("Add at least one expense item before submitting")
        # If the employee has no manager (e.g. a top-level manager), nobody can
        # ever act on the SUBMITTED claim, so the manager step is auto-approved
        # and the claim goes straight to Finance instead of being stuck forever.
        skip_manager = claim.employee.manager_id is None
        violations = self.policy_service.evaluate_claim(claim)
        blocking = [v for v in violations if v["severity"] == "HIGH"]
        if blocking:
            self.claim_dao.update()
            raise ValueError(
                "Fix these policy issues first: "
                + " ".join(v["message"] for v in blocking)
            )
        self._recalculate_total(claim)
        self.approval_service.transition(
            claim,
            ClaimStatus.SUBMITTED,
            user,
            Action.SUBMITTED,
            comments="Submitted for manager approval",
        )
        if skip_manager:
            for item in claim.items:
                if item.approved_amount is None:
                    item.approved_amount = item.amount_in_base
            self.approval_service.transition(
                claim,
                ClaimStatus.MANAGER_APPROVED,
                user,
                Action.APPROVED,
                comments="Auto-approved: no reporting manager assigned",
            )
        return claim

    def cancel_claim(self, claim_id, employee, user, reason):
        claim = self.get_owned_claim(claim_id, employee)
        return self.approval_service.transition(
            claim, ClaimStatus.CANCELLED, user, Action.CANCELLED, comments=reason
        )

    def my_claims(self, employee, status=None):
        return self.claim_dao.get_by_employee(employee.id, status)

    def claim_detail(self, claim_id, viewer_user, viewer_employee):
        claim = self.claim_dao.get_by_id(claim_id)
        if claim is None:
            raise ValueError("Claim not found")
        allowed = (
            claim.employee_id == getattr(viewer_employee, "id", None)
            or viewer_user.role in ("FINANCE", "ADMIN")
            or (
                viewer_user.role == "MANAGER"
                and viewer_employee
                and claim.employee.manager_id == viewer_employee.id
            )
        )
        if not allowed:
            raise ValueError("You are not allowed to view this claim")
        return claim
