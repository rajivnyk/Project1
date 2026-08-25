from datetime import date, timedelta
from models.travel_request import TravelRequest
from models.approval_history import ApprovalHistory
from models.enums import TravelStatus, Action
from util.helpers import generate_sequence
from util.validators import require, to_decimal, to_date, validate_date_range


class TravelService:
    def __init__(self, travel_dao, approval_dao):
        self.travel_dao = travel_dao
        self.approval_dao = approval_dao

    def create(self, employee, data):
        from_date = to_date(data.get("from_date"), "From date")
        to_date_ = to_date(data.get("to_date"), "To date")
        validate_date_range(from_date, to_date_, "Travel dates")
        if from_date < (date.today() - timedelta(days=2)):
            raise ValueError("Travel start date cannot be more than 2 days in the past")
        tr = TravelRequest(
            request_no=generate_sequence("TR", TravelRequest, "request_no"),
            employee_id=employee.id,
            purpose=require(data.get("purpose"), "Purpose"),
            destination_city=require(data.get("destination_city"), "Destination city"),
            destination_country=data.get("destination_country", "India"),
            from_date=from_date,
            to_date=to_date_,
            mode_of_travel=data.get("mode_of_travel"),
            estimated_cost=to_decimal(data.get("estimated_cost"), "Estimated cost"),
            status=(
                TravelStatus.APPROVED
                if employee.manager_id is None
                else TravelStatus.SUBMITTED
            ),
        )
        return self.travel_dao.save(tr)

    def decide(self, request_id, manager_employee, manager_user, approve, remarks):
        tr = self.travel_dao.get_by_id(request_id)
        if tr is None:
            raise ValueError("Travel request not found")
        if tr.employee.manager_id != manager_employee.id:
            raise ValueError("This request is not from your team")
        if tr.status != TravelStatus.SUBMITTED:
            raise ValueError(f"Request is already {tr.status}")
        if not approve and not (remarks or "").strip():
            raise ValueError("A reason is mandatory when rejecting")
        old = tr.status
        tr.status = TravelStatus.APPROVED if approve else TravelStatus.REJECTED
        tr.approver_id = manager_user.id
        tr.remarks = remarks
        self.approval_dao.save(
            ApprovalHistory(
                entity_type="TRAVEL",
                travel_request_id=tr.id,
                level=1,
                action=Action.APPROVED if approve else Action.REJECTED,
                old_status=old,
                new_status=tr.status,
                actor_id=manager_user.id,
                comments=remarks,
            )
        )
        self.travel_dao.update()
        return tr

    def cancel(self, request_id, employee, user, reason=None):
        tr = self.travel_dao.get_by_id(request_id)
        if tr is None:
            raise ValueError("Travel request not found")
        if tr.employee_id != employee.id:
            raise ValueError("You may only cancel your own travel requests")
        if tr.status != TravelStatus.SUBMITTED:
            raise ValueError(
                f"Request is {tr.status}; only a SUBMITTED request can be cancelled"
            )
        old = tr.status
        tr.status = TravelStatus.CANCELLED
        tr.remarks = reason or tr.remarks
        self.approval_dao.save(
            ApprovalHistory(
                entity_type="TRAVEL",
                travel_request_id=tr.id,
                level=0,
                action=Action.CANCELLED,
                old_status=old,
                new_status=tr.status,
                actor_id=user.id,
                comments=reason,
            )
        )
        self.travel_dao.update()
        return tr
