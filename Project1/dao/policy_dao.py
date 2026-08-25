from datetime import date
from config.database import db
from models.expense_policy import ExpensePolicy


class PolicyDAO:
    def get_all(self):
        return ExpensePolicy.query.all()

    def get_active_policy(self, category_id, grade, on_date=None):
        on_date = on_date or date.today()
        return (
            ExpensePolicy.query.filter(
                ExpensePolicy.category_id == category_id,
                ExpensePolicy.grade == grade,
                ExpensePolicy.is_active.is_(True),
                ExpensePolicy.effective_from <= on_date,
                (
                    (ExpensePolicy.effective_to.is_(None))
                    | (ExpensePolicy.effective_to >= on_date)
                ),
            )
            .order_by(ExpensePolicy.effective_from.desc())
            .first()
        )

    def save(self, policy):
        db.session.add(policy)
        db.session.commit()
        return policy
