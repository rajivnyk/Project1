import os
import uuid
from flask import current_app, send_file
from models.expense_receipt import ExpenseReceipt
from util.validators import validate_upload
from util.helpers import file_checksum


class FileService:
    def __init__(self, receipt_dao):
        self.receipt_dao = receipt_dao

    def save_receipt(self, file_storage, claim, item_id, user):
        cfg = current_app.config
        ext, size = validate_upload(
            file_storage, cfg["ALLOWED_EXTENSIONS"], cfg["MAX_CONTENT_LENGTH"]
        )
        checksum = file_checksum(file_storage.stream)
        duplicate = self.receipt_dao.get_by_checksum(checksum)
        if duplicate:
            raise ValueError(
                f"This exact file was already uploaded on claim {duplicate.claim.claim_no}"
            )
        os.makedirs(cfg["UPLOAD_FOLDER"], exist_ok=True)
        stored = f"{claim.claim_no}_{uuid.uuid4().hex}.{ext}"
        abs_path = os.path.join(cfg["UPLOAD_FOLDER"], stored)
        file_storage.save(abs_path)
        receipt = ExpenseReceipt(
            claim_id=claim.id,
            item_id=item_id or None,
            original_filename=file_storage.filename,
            stored_filename=stored,
            file_path=stored,
            file_type=ext,
            file_size=size,
            checksum_sha256=checksum,
            uploaded_by=user.id,
        )
        try:
            return self.receipt_dao.save(receipt)
        except Exception:
            if os.path.exists(abs_path):
                os.remove(abs_path)
            raise

    def download(self, receipt_id, viewer_user, viewer_employee):
        receipt = self.receipt_dao.get_by_id(receipt_id)
        if receipt is None:
            raise ValueError("Receipt not found")
        claim = receipt.claim
        allowed = (
            viewer_user.role in ("FINANCE", "ADMIN")
            or (viewer_employee and claim.employee_id == viewer_employee.id)
            or (
                viewer_user.role == "MANAGER"
                and viewer_employee
                and claim.employee.manager_id == viewer_employee.id
            )
        )
        if not allowed:
            raise ValueError("You are not allowed to download this document")
        abs_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], receipt.stored_filename
        )
        if not os.path.exists(abs_path):
            raise ValueError("The stored file is missing from the server")
        return send_file(
            abs_path, as_attachment=True, download_name=receipt.original_filename
        )
