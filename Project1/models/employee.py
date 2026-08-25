from datetime import datetime
from config.database import db


class Employee(db.Model):
    __tablename__ = "employees"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False
    )
    emp_code = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(60), nullable=False)
    designation = db.Column(db.String(60))
    grade = db.Column(db.String(10), nullable=False, default="G3")
    manager_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    date_of_joining = db.Column(db.Date)
    contact_number = db.Column(db.String(15))
    bank_account_no = db.Column(db.String(30))
    ifsc_code = db.Column(db.String(15))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="employee")
    manager = db.relationship("Employee", remote_side=[id], backref="reportees")

    def to_dict(self):
        return {
            "id": self.id,
            "emp_code": self.emp_code,
            "full_name": self.full_name,
            "department": self.department,
            "designation": self.designation,
            "grade": self.grade,
            "manager": self.manager.full_name if self.manager else None,
        }
