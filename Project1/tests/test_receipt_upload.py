import io
import shutil
import tempfile
import unittest
from datetime import date
from dao.claim_dao import ClaimDAO
from dao.receipt_dao import ReceiptDAO
from service.file_service import FileService
from models.expense_claim import ExpenseClaim
from models.enums import ClaimStatus
from tests.base import (
    BaseTestCase,
    PDF_BYTES,
    PNG_BYTES,
    JPG_BYTES,
    BAD_MAGIC_BYTES_PDF_EXT,
)


class ReceiptUploadServiceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._tmp_upload_dir = tempfile.mkdtemp(prefix="test_uploads_")
        self.app.config["UPLOAD_FOLDER"] = self._tmp_upload_dir
        self.claim_dao = ClaimDAO()
        self.receipt_dao = ReceiptDAO()
        self.service = FileService(self.receipt_dao)
        self.claim = self.claim_dao.save(
            ExpenseClaim(
                claim_no="CLM-RCPT-001",
                employee_id=self.employee.id,
                title="Receipt test",
                claim_date=date.today(),
                period_from=date.today(),
                period_to=date.today(),
                status=ClaimStatus.DRAFT,
            )
        )

    def tearDown(self):
        shutil.rmtree(self._tmp_upload_dir, ignore_errors=True)
        self.app.config["UPLOAD_FOLDER"] = "uploads/receipts"
        super().tearDown()

    def _upload(self, content, filename):
        from werkzeug.datastructures import FileStorage

        return FileStorage(stream=io.BytesIO(content), filename=filename)

    def test_valid_pdf_upload_succeeds(self):
        with self.app.test_request_context():
            receipt = self.service.save_receipt(
                self._upload(PDF_BYTES, "invoice.pdf"),
                self.claim,
                None,
                self.employee_user,
            )
        self.assertEqual(receipt.file_type, "pdf")
        self.assertEqual(receipt.original_filename, "invoice.pdf")

    def test_valid_png_upload_succeeds(self):
        with self.app.test_request_context():
            receipt = self.service.save_receipt(
                self._upload(PNG_BYTES, "photo.png"),
                self.claim,
                None,
                self.employee_user,
            )
        self.assertEqual(receipt.file_type, "png")

    def test_valid_jpg_upload_succeeds(self):
        with self.app.test_request_context():
            receipt = self.service.save_receipt(
                self._upload(JPG_BYTES, "photo.jpg"),
                self.claim,
                None,
                self.employee_user,
            )
        self.assertEqual(receipt.file_type, "jpg")

    def test_disallowed_extension_rejected(self):
        with self.app.test_request_context():
            with self.assertRaises(ValueError) as ctx:
                self.service.save_receipt(
                    self._upload(b"malicious content", "script.exe"),
                    self.claim,
                    None,
                    self.employee_user,
                )
        self.assertIn("not allowed", str(ctx.exception))

    def test_spoofed_extension_with_wrong_magic_bytes_rejected(self):
        with self.app.test_request_context():
            with self.assertRaises(ValueError) as ctx:
                self.service.save_receipt(
                    self._upload(BAD_MAGIC_BYTES_PDF_EXT, "fake.pdf"),
                    self.claim,
                    None,
                    self.employee_user,
                )
        self.assertIn("does not match", str(ctx.exception))

    def test_empty_file_rejected(self):
        with self.app.test_request_context():
            with self.assertRaises(ValueError) as ctx:
                self.service.save_receipt(
                    self._upload(b"", "empty.pdf"), self.claim, None, self.employee_user
                )
        self.assertIn("empty", str(ctx.exception))

    def test_no_file_selected_rejected(self):
        with self.app.test_request_context():
            with self.assertRaises(ValueError):
                self.service.save_receipt(
                    self._upload(b"", ""), self.claim, None, self.employee_user
                )

    def test_oversized_file_rejected(self):
        self.app.config["MAX_CONTENT_LENGTH"] = 100
        try:
            with self.app.test_request_context():
                with self.assertRaises(ValueError) as ctx:
                    self.service.save_receipt(
                        self._upload(PDF_BYTES * 10, "big.pdf"),
                        self.claim,
                        None,
                        self.employee_user,
                    )
            self.assertIn("limit", str(ctx.exception))
        finally:
            self.app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    def test_duplicate_checksum_rejected(self):
        with self.app.test_request_context():
            self.service.save_receipt(
                self._upload(PDF_BYTES, "first.pdf"),
                self.claim,
                None,
                self.employee_user,
            )
            with self.assertRaises(ValueError) as ctx:
                self.service.save_receipt(
                    self._upload(PDF_BYTES, "duplicate.pdf"),
                    self.claim,
                    None,
                    self.employee_user,
                )
        self.assertIn("already uploaded", str(ctx.exception))

    def test_different_content_same_extension_both_allowed(self):
        with self.app.test_request_context():
            r1 = self.service.save_receipt(
                self._upload(PDF_BYTES, "a.pdf"), self.claim, None, self.employee_user
            )
            r2 = self.service.save_receipt(
                self._upload(PDF_BYTES + b"extra", "b.pdf"),
                self.claim,
                None,
                self.employee_user,
            )
        self.assertNotEqual(r1.checksum_sha256, r2.checksum_sha256)


class ReceiptUploadHttpRouteTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self._tmp_upload_dir = tempfile.mkdtemp(prefix="test_uploads_")
        self.app.config["UPLOAD_FOLDER"] = self._tmp_upload_dir

    def tearDown(self):
        shutil.rmtree(self._tmp_upload_dir, ignore_errors=True)
        self.app.config["UPLOAD_FOLDER"] = "uploads/receipts"
        super().tearDown()

    def test_upload_receipt_via_route(self):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": "Upload route test",
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        claim = ExpenseClaim.query.filter_by(title="Upload route test").first()
        resp = self.client.post(
            f"/expense/{claim.id}/receipt",
            data={
                "receipt": (io.BytesIO(PDF_BYTES), "bill.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Receipt uploaded", resp.data)

    def test_upload_bad_file_via_route_shows_error(self):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": "Bad upload test",
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        claim = ExpenseClaim.query.filter_by(title="Bad upload test").first()
        resp = self.client.post(
            f"/expense/{claim.id}/receipt",
            data={
                "receipt": (io.BytesIO(b"not a real file"), "virus.exe"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"not allowed", resp.data)


if __name__ == "__main__":
    unittest.main()
