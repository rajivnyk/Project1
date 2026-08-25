import pytest
from datetime import date, timedelta
from service.travel_service import TravelService
from dao.travel_dao import TravelDAO
from dao.approval_dao import ApprovalDAO
from models.travel_request import TravelRequest
from models.employee import Employee
from models.enums import TravelStatus


class MockTravelDAO:
    def __init__(self):
        self.saved = []

    def save(self, tr):
        tr.id = len(self.saved) + 1
        self.saved.append(tr)
        return tr


class MockApprovalDAO:
    pass


def _valid_payload():
    return {
        "purpose": "Client meeting",
        "destination_city": "Mumbai",
        "destination_country": "India",
        "from_date": date.today().isoformat(),
        "to_date": (date.today() + timedelta(days=2)).isoformat(),
        "mode_of_travel": "AIR",
        "estimated_cost": "15000",
        "advance_required": "5000",
    }


def test_travel_service_create_goes_to_manager():
    service = TravelService(MockTravelDAO(), MockApprovalDAO())
    emp = Employee(id=1, manager_id=2)
    tr = service.create(emp, _valid_payload())
    assert tr.purpose == "Client meeting"
    assert tr.status == TravelStatus.SUBMITTED


def test_travel_service_create_auto_approves_without_manager():
    # A managerless employee has nobody who could ever approve the request,
    # so TravelService approves it up front instead of stranding it.
    service = TravelService(MockTravelDAO(), MockApprovalDAO())
    emp = Employee(id=1, manager_id=None)
    tr = service.create(emp, _valid_payload())
    assert tr.status == TravelStatus.APPROVED


def test_travel_service_backdate_2_days():
    service = TravelService(MockTravelDAO(), MockApprovalDAO())
    emp = Employee(id=1)
    # 2 days ago
    data = {
        "purpose": "Emergency",
        "destination_city": "Delhi",
        "from_date": (date.today() - timedelta(days=2)).isoformat(),
        "to_date": date.today().isoformat(),
        "estimated_cost": "100",
    }
    tr = service.create(emp, data)
    assert tr.purpose == "Emergency"


def test_travel_service_backdate_3_days_fails():
    service = TravelService(MockTravelDAO(), MockApprovalDAO())
    emp = Employee(id=1)
    # 3 days ago
    data = {
        "purpose": "Too late",
        "destination_city": "Pune",
        "from_date": (date.today() - timedelta(days=3)).isoformat(),
        "to_date": date.today().isoformat(),
        "estimated_cost": "100",
    }
    with pytest.raises(ValueError, match="more than 2 days in the past"):
        service.create(emp, data)
