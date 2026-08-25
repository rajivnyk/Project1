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
from tests.base import BaseTestCase, PDF_BYTES


class UnauthorizedDocumentAccessTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._tmp_upload_dir = tempfile.mkdtemp(prefix="test_uploads_")
        self.app.config["UPLOAD_FOLDER"] = self._tmp_upload_dir
        self.claim_dao = ClaimDAO()
        self.receipt_dao = ReceiptDAO()
        self.service = FileService(self.receipt_dao)
        self.claim = self.claim_dao.save(
            ExpenseClaim(
                claim_no="CLM-SEC-001",
                employee_id=self.employee.id,
                title="Secure claim",
                claim_date=date.today(),
                period_from=date.today(),
                period_to=date.today(),
                status=ClaimStatus.DRAFT,
            )
        )
        from werkzeug.datastructures import FileStorage

        with self.app.test_request_context():
            self.receipt = self.service.save_receipt(
                FileStorage(
                    stream=io.BytesIO(PDF_BYTES), filename="secret_invoice.pdf"
                ),
                self.claim,
                None,
                self.employee_user,
            )

    def tearDown(self):
        shutil.rmtree(self._tmp_upload_dir, ignore_errors=True)
        self.app.config["UPLOAD_FOLDER"] = "uploads/receipts"
        super().tearDown()

    def test_owner_can_download_own_receipt(self):
        with self.app.test_request_context():
            resp = self.service.download(
                self.receipt.id, self.employee_user, self.employee
            )
        self.assertEqual(resp.status_code, 200)

    def test_reporting_manager_can_download_reportee_receipt(self):
        with self.app.test_request_context():
            resp = self.service.download(
                self.receipt.id, self.manager_user, self.manager
            )
        self.assertEqual(resp.status_code, 200)

    def test_finance_can_download_any_receipt(self):
        with self.app.test_request_context():
            resp = self.service.download(self.receipt.id, self.finance_user, None)
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_download_any_receipt(self):
        with self.app.test_request_context():
            resp = self.service.download(self.receipt.id, self.admin_user, None)
        self.assertEqual(resp.status_code, 200)

    def test_unrelated_employee_cannot_download(self):
        with self.app.test_request_context():
            with self.assertRaises(ValueError) as ctx:
                self.service.download(
                    self.receipt.id, self.other_employee_user, self.other_employee
                )
        self.assertIn("not allowed", str(ctx.exception))

    def test_unrelated_manager_cannot_download(self):
        with self.app.test_request_context():
            with self.assertRaises(ValueError) as ctx:
                self.service.download(
                    self.receipt.id, self.other_manager_user, self.other_manager
                )
        self.assertIn("not allowed", str(ctx.exception))

    def test_download_nonexistent_receipt_raises(self):
        with self.app.test_request_context():
            with self.assertRaises(ValueError) as ctx:
                self.service.download(999999, self.finance_user, None)
        self.assertIn("not found", str(ctx.exception))


class UnauthorizedDocumentAccessHttpTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self._tmp_upload_dir = tempfile.mkdtemp(prefix="test_uploads_")
        self.app.config["UPLOAD_FOLDER"] = self._tmp_upload_dir

    def tearDown(self):
        shutil.rmtree(self._tmp_upload_dir, ignore_errors=True)
        self.app.config["UPLOAD_FOLDER"] = "uploads/receipts"
        super().tearDown()

    def _create_claim_with_receipt(self):
        self.login_as_employee()
        self.client.post(
            "/expense/new",
            data={
                "title": "HTTP secure claim",
                "period_from": date.today().isoformat(),
                "period_to": date.today().isoformat(),
            },
        )
        claim = ExpenseClaim.query.filter_by(title="HTTP secure claim").first()
        self.client.post(
            f"/expense/{claim.id}/receipt",
            data={
                "receipt": (io.BytesIO(PDF_BYTES), "bill.pdf"),
            },
            content_type="multipart/form-data",
        )
        from models.expense_receipt import ExpenseReceipt

        return ExpenseReceipt.query.filter_by(claim_id=claim.id).first()

    def test_owner_downloads_via_route(self):
        receipt = self._create_claim_with_receipt()
        resp = self.client.get(f"/expense/receipt/{receipt.id}/download")
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_user_cannot_download(self):
        receipt = self._create_claim_with_receipt()
        anon = self.app.test_client()
        resp = anon.get(
            f"/expense/receipt/{receipt.id}/download",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_unrelated_employee_redirected_away_from_download(self):
        receipt = self._create_claim_with_receipt()
        intruder = self.app.test_client()
        intruder.post(
            "/auth/login?portal=user",
            data={"username": "emp2", "password": "Test@1234"},
        )
        resp = intruder.get(
            f"/expense/receipt/{receipt.id}/download", follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"not allowed", resp.data)


if __name__ == "__main__":
    unittest.main()
