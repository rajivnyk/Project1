from datetime import datetime
from config.database import db
from models.approval_history import ApprovalHistory
from models.enums import ClaimStatus


class ApprovalService:
    LEVEL_OF = {
        ClaimStatus.SUBMITTED: 1,
        ClaimStatus.MANAGER_APPROVED: 2,
        ClaimStatus.FINANCE_VERIFIED: 3,
        ClaimStatus.REIMBURSED: 3,
        ClaimStatus.MANAGER_REJECTED: 1,
        ClaimStatus.FINANCE_REJECTED: 2,
        ClaimStatus.CANCELLED: 0,
        ClaimStatus.DRAFT: 0,
    }

    def __init__(self, approval_dao):
        self.approval_dao = approval_dao

    def transition(
        self, claim, target_status, actor, action, comments=None, commit=True
    ):
        old = claim.status
        if not ClaimStatus.can_move(old, target_status):
            raise ValueError(
                f"Claim {claim.claim_no} is {old}; it cannot move to {target_status}"
            )
        if action == "REJECTED" and not (comments or "").strip():
            raise ValueError("A reason is mandatory when rejecting")
        claim.status = target_status
        if target_status == ClaimStatus.SUBMITTED:
            claim.submitted_at = datetime.utcnow()
        self.approval_dao.save(
            ApprovalHistory(
                entity_type="CLAIM",
                claim_id=claim.id,
                level=self.LEVEL_OF.get(target_status, 0),
                action=action,
                old_status=old,
                new_status=target_status,
                actor_id=actor.id,
                comments=comments,
            )
        )
        if commit:
            db.session.commit()
        return claim

    def assert_is_manager_of(self, manager_employee, claim):
        if claim.employee.manager_id != manager_employee.id:
            raise ValueError("This claim does not belong to your team")
