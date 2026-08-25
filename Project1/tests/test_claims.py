from models.employee import Employee
import pytest
from models.expense_claim import ExpenseClaim
from models.expense_item import ExpenseItem
from models.enums import ClaimStatus
from datetime import date


def test_claim_creation(test_app, test_db, seeded_db):
    employee = seeded_db.session.query(Employee).first()
    claim = ExpenseClaim(
        claim_no="CLAIM-001",
        employee_id=employee.id,
        title="Test Claim",
        claim_date=date.today(),
        period_from=date.today(),
        period_to=date.today(),
        status=ClaimStatus.DRAFT,
        total_amount=5000.00,
    )
    test_db.session.add(claim)
    test_db.session.commit()

    saved = ExpenseClaim.query.filter_by(claim_no="CLAIM-001").first()
    assert saved is not None
    assert saved.title == "Test Claim"
    assert saved.status == ClaimStatus.DRAFT


def test_claim_item_relationship(test_app, test_db, seeded_db):
    claim = ExpenseClaim.query.filter_by(claim_no="CLAIM-001").first()
    if not claim:
        pytest.skip("Previous test didn't save claim")

    item = ExpenseItem(
        claim_id=claim.id,
        category_id=1,
        expense_date=date.today(),
        description="Hotel Stay",
        amount_in_base=2500.00,
    )
    test_db.session.add(item)
    test_db.session.commit()

    assert len(claim.items) == 1
    assert claim.items[0].description == "Hotel Stay"
