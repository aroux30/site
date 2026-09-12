"""Bulk import service for digital cards from Excel and CSV (Karta Phase 1/2).

Implements:
- Deduplication via deterministic SHA-256 hash (Karta card_hash)
- AES-256-GCM encryption for stored PINs
- Support for .xlsx, .xls, and .csv formats
- Persian / Arabic digit normalisation
- Detailed batch import report with duplicate and error counts
"""

from __future__ import annotations

import csv
import io
import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy.exc import IntegrityError

from app.modules.inventory.application.crypto_service import compute_card_hash, encrypt_pin
from app.modules.inventory.domain.digital_models import (
    DigitalCard,
    DigitalCardStatus,
    DigitalDeliveryType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def normalise_digits(text: str) -> str:
    """Convert Persian/Arabic numerals to standard ASCII digits."""
    if not text:
        return ""
    persian = "۰۱۲۳۴۵۶۷۸۹"
    arabic = "٠١٢٣٤٥٦٧٨٩"
    trans = str.maketrans(
        {
            **{p: str(i) for i, p in enumerate(persian)},
            **{a: str(i) for i, a in enumerate(arabic)},
        }
    )
    return text.translate(trans)


async def bulk_import_cards(
    db: AsyncSession,
    product_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    delivery_type: DigitalDeliveryType = DigitalDeliveryType.UNIQUE,
    max_uses: int = 1,
) -> dict[str, Any]:
    """Parse Excel or CSV file, deduplicate via SHA-256 hash, and encrypt PINs."""
    is_excel = filename.lower().endswith((".xlsx", ".xls"))
    raw_entries: list[tuple[str, str | None]] = []

    if is_excel:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheet = wb.active
        for row in sheet.iter_rows(values_only=True):
            if not row or all(v is None for v in row):
                continue
            col0 = str(row[0]).strip() if row[0] is not None else ""
            col1 = str(row[1]).strip() if len(row) > 1 and row[1] is not None else None
            if col0.lower() in ("pin", "code", "card_pin", "کد", "پین"):
                continue
            if col0:
                raw_entries.append((col0, col1))
    else:
        text_content = file_bytes.decode("utf-8-sig", errors="replace")
        reader = csv.reader(io.StringIO(text_content))
        for row in reader:
            if not row or not any(row):
                continue
            col0 = row[0].strip()
            col1 = row[1].strip() if len(row) > 1 and row[1].strip() else None
            if col0.lower() in ("pin", "code", "card_pin", "کد", "پین"):
                continue
            if col0:
                raw_entries.append((col0, col1))

    total_rows = len(raw_entries)
    imported = 0
    duplicates = 0
    errors = 0
    details = []
    seen_in_batch: set[str] = set()

    for idx, (raw_pin, raw_serial) in enumerate(raw_entries, start=1):
        pin = normalise_digits(raw_pin)
        serial = normalise_digits(raw_serial) if raw_serial else None

        if not pin:
            errors += 1
            details.append(
                {
                    "row_number": idx,
                    "serial_number": serial,
                    "status": "error",
                    "detail": "Empty PIN",
                }
            )
            continue

        c_hash = compute_card_hash(pin, serial)

        if c_hash in seen_in_batch:
            duplicates += 1
            details.append(
                {
                    "row_number": idx,
                    "serial_number": serial,
                    "status": "duplicate_skipped",
                    "detail": "Duplicate in batch",
                }
            )
            continue

        seen_in_batch.add(c_hash)

        try:
            ciphertext = encrypt_pin(pin)
            card = DigitalCard(
                product_id=product_id,
                delivery_type=delivery_type,
                serial_number=serial,
                pin_ciphertext=ciphertext,
                card_hash=c_hash,
                status=DigitalCardStatus.AVAILABLE,
                max_uses=max_uses,
                used_count=0,
            )

            async with db.begin_nested():
                db.add(card)
                await db.flush()

            imported += 1
            details.append(
                {
                    "row_number": idx,
                    "serial_number": serial,
                    "status": "success",
                    "detail": None,
                }
            )
        except IntegrityError:
            duplicates += 1
            details.append(
                {
                    "row_number": idx,
                    "serial_number": serial,
                    "status": "duplicate_skipped",
                    "detail": "Duplicate card in database",
                }
            )
        except Exception as exc:
            errors += 1
            details.append(
                {
                    "row_number": idx,
                    "serial_number": serial,
                    "status": "error",
                    "detail": str(exc),
                }
            )

    await logger.ainfo(
        "bulk_cards_imported",
        product_id=str(product_id),
        total_rows=total_rows,
        imported=imported,
        duplicates=duplicates,
        errors=errors,
    )

    return {
        "total_rows": total_rows,
        "imported_count": imported,
        "duplicate_count": duplicates,
        "error_count": errors,
        "details": details,
    }
