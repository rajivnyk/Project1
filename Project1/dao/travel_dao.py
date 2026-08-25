from config.database import db
from models.travel_request import TravelRequest
from models.enums import TravelStatus


class TravelDAO:
    def get_all(self):
        return TravelRequest.query.all()

    def get_by_id(self, request_id):
        return TravelRequest.query.get(request_id)

    def get_by_employee(self, employee_id):
        return (
            TravelRequest.query.filter_by(employee_id=employee_id)
            .order_by(TravelRequest.created_at.desc())
            .all()
        )

    def get_pending_for_manager(self, reportee_ids):
        if not reportee_ids:
            return []
        return TravelRequest.query.filter(
            TravelRequest.employee_id.in_(reportee_ids),
            TravelRequest.status == TravelStatus.SUBMITTED,
        ).all()

    def get_approved_for_employee(self, employee_id):
        return TravelRequest.query.filter_by(
            employee_id=employee_id, status=TravelStatus.APPROVED
        ).all()

    def save(self, travel_request):
        db.session.add(travel_request)
        db.session.commit()
        return travel_request

    def update(self):
        db.session.commit()
