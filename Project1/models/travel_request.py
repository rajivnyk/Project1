from datetime import datetime
from config.database import db
from models.enums import TravelStatus


class TravelRequest(db.Model):
    __tablename__ = "travel_requests"
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(20), unique=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)
    destination_city = db.Column(db.String(80), nullable=False)
    destination_country = db.Column(db.String(80), default="India")
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    mode_of_travel = db.Column(db.String(20))
    estimated_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    advance_required = db.Column(db.Numeric(12, 2), default=0)
    status = db.Column(
        db.String(20), nullable=False, default=TravelStatus.DRAFT, index=True
    )
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    remarks = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee = db.relationship("Employee")

    def to_dict(self):
        return {
            "id": self.id,
            "request_no": self.request_no,
            "purpose": self.purpose,
            "destination": f"{self.destination_city}, {self.destination_country}",
            "from_date": self.from_date.isoformat(),
            "to_date": self.to_date.isoformat(),
            "days": (self.to_date - self.from_date).days + 1,
            "estimated_cost": float(self.estimated_cost),
            "status": self.status,
        }
