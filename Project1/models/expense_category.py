from config.database import db


class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(255))
    requires_receipt = db.Column(db.Boolean, default=True)
    default_limit = db.Column(db.Numeric(10, 2), default=0)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "requires_receipt": self.requires_receipt,
            "default_limit": float(self.default_limit or 0),
        }
