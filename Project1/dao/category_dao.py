from models.expense_category import ExpenseCategory


class CategoryDAO:
    def get_all(self):
        return ExpenseCategory.query.all()

    def get_active(self):
        return (
            ExpenseCategory.query.filter_by(is_active=True)
            .order_by(ExpenseCategory.name)
            .all()
        )

    def get_by_id(self, category_id):
        return ExpenseCategory.query.get(category_id)
