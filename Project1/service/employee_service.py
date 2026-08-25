from util.validators import require


class EmployeeService:
    def __init__(self, employee_dao):
        self.employee_dao = employee_dao

    def update_profile(self, employee, data):
        employee.full_name = require(data.get("full_name"), "Full name")
        employee.designation = data.get("designation")
        employee.contact_number = data.get("contact_number")
        employee.bank_account_no = data.get("bank_account_no")
        employee.ifsc_code = (data.get("ifsc_code") or "").upper() or None
        self.employee_dao.update()
        return employee
