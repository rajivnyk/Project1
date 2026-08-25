import hashlib
from datetime import datetime
from decimal import Decimal
from config.database import db


def generate_sequence(prefix, model, column):
    year = datetime.now().year
    like = f"{prefix}-{year}-%"
    count = (
        db.session.query(db.func.count(getattr(model, column)))
        .filter(getattr(model, column).like(like))
        .scalar()
        or 0
    )
    return f"{prefix}-{year}-{count + 1:06d}"


def file_checksum(stream):
    sha = hashlib.sha256()
    stream.seek(0)
    for chunk in iter(lambda: stream.read(8192), b""):
        sha.update(chunk)
    stream.seek(0)
    return sha.hexdigest()


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def apply_item_reviews(form, claim, default_to_claimed):
    """Read per-item approved_amount_<id> / comment_<id> fields off a submitted form.

    A blank or missing amount either falls back to the claimed amount (the
    manager's first review) or leaves the current value alone (finance's
    re-check). A non-numeric amount raises ValueError so the caller can flash
    it, rather than letting float() blow up into a 500.
    """
    from util.validators import to_decimal

    for item in claim.items:
        raw = form.get(f"approved_amount_{item.id}")
        comment = form.get(f"comment_{item.id}")
        if raw is not None and str(raw).strip() != "":
            item.approved_amount = to_decimal(
                raw, f"Approved amount for item {item.id}", min_value=0
            )
        elif default_to_claimed and item.approved_amount is None:
            item.approved_amount = item.amount_in_base
        if comment:
            item.reviewer_comments = comment
