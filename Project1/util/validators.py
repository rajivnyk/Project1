import os
from datetime import datetime
from decimal import Decimal, InvalidOperation


def require(value, field):
    if value is None or str(value).strip() == "":
        raise ValueError(f"{field} is required")
    return str(value).strip()


def to_decimal(value, field, min_value=Decimal("0.01")):
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"{field} must be a number")
    if amount < min_value:
        raise ValueError(f"{field} must be at least {min_value}")
    return amount.quantize(Decimal("0.01"))


def to_date(value, field):
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{field} must be a valid date (YYYY-MM-DD)")


def validate_date_range(start, end, field="Date range"):
    if end < start:
        raise ValueError(f"{field}: end date cannot be before start date")
    return True


def validate_upload(file_storage, allowed_ext, max_bytes):
    if file_storage is None or file_storage.filename == "":
        raise ValueError("No file selected")
    ext = os.path.splitext(file_storage.filename)[1].lower().lstrip(".")
    if ext not in allowed_ext:
        raise ValueError(
            f"'{ext}' files are not allowed. Allowed: {', '.join(sorted(allowed_ext))}"
        )
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        raise ValueError("The selected file is empty")
    if size > max_bytes:
        raise ValueError(
            f"File is {size // 1024} KB; the limit is {max_bytes // 1024} KB"
        )
    head = file_storage.stream.read(8)
    file_storage.stream.seek(0)
    signatures = {b"%PDF": "pdf", b"\x89PNG": "png", b"\xff\xd8\xff": "jpg"}
    if not any(head.startswith(sig) for sig in signatures):
        raise ValueError("File content does not match a PDF or image file")
    return ext, size
