from config.database import db
from models.employee import Employee


class EmployeeDAO:
    def get_all(self):
        return Employee.query.all()

    def get_by_id(self, employee_id):
        return Employee.query.get(employee_id)

    def get_by_user(self, user_id):
        return Employee.query.filter_by(user_id=user_id).first()

    def get_reportees(self, manager_employee_id):
        return Employee.query.filter_by(
            manager_id=manager_employee_id, is_active=True
        ).all()

    def reportee_ids(self, manager_employee_id):
        rows = (
            Employee.query.with_entities(Employee.id)
            .filter_by(manager_id=manager_employee_id)
            .all()
        )
        return [r.id for r in rows]

    def save(self, employee):
        db.session.add(employee)
        db.session.commit()
        return employee

    def update(self):
        db.session.commit()
