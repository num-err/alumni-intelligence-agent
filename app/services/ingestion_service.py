"""Persists a parsed spreadsheet as an `Upload` plus its `AlumniRecord` rows.

Rows whose "Processing Status" column already reads "completed" (e.g. the
user re-uploaded a partially-enriched export to keep working on it) are
loaded as completed and excluded from the processing queue -- the app never
reprocesses a student it already finished.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.alumni import AlumniRecord, Upload
from app.services.spreadsheet_reader import ParsedWorkbook, read_workbook

VALID_STATUSES = {"pending", "processing", "completed", "failed", "skipped"}
COMPLETED_STATUSES = {"completed", "done"}


def _parse_bool(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in {"true", "yes", "1", "y"}


def _parse_confidence(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return None


def _parse_evidence(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def _normalize_status(value: str | None) -> str:
    status = (value or "pending").strip().lower()
    if status in COMPLETED_STATUSES:
        return "completed"
    return status if status in VALID_STATUSES else "pending"


def ingest_upload(
    db: Session,
    *,
    original_filename: str,
    stored_filename: str,
    stored_path: Path,
) -> Upload:
    """Parse the workbook at `stored_path` and persist it as a new Upload."""
    parsed: ParsedWorkbook = read_workbook(stored_path)

    upload = Upload(
        original_filename=original_filename,
        stored_filename=stored_filename,
        stored_path=str(stored_path),
        total_rows=parsed.total_rows,
        column_mapping=parsed.column_map,
        extra_columns=parsed.extra_columns,
    )
    db.add(upload)
    db.flush()  # assigns upload.id for the records below

    for index, row in enumerate(parsed.rows):
        db.add(
            AlumniRecord(
                upload_id=upload.id,
                row_index=index,
                first_name=row.get("first_name"),
                last_name=row.get("last_name"),
                email=row.get("email"),
                linkedin=row.get("linkedin"),
                graduation_year=row.get("graduation_year"),
                country=row.get("country"),
                city=row.get("city"),
                public_email=row.get("public_email"),
                country_origin=row.get("country_origin"),
                current_location=row.get("current_location"),
                confidence=_parse_confidence(row.get("confidence")),
                evidence=_parse_evidence(row.get("evidence")),
                processing_status=_normalize_status(row.get("processing_status")),
                review_required=_parse_bool(row.get("review_required")),
                extra_data=row.get("_extra") or {},
            )
        )

    db.commit()
    db.refresh(upload)
    return upload


def rows_needing_processing(upload: Upload) -> list[AlumniRecord]:
    """Records not already completed -- these are what the queue must process."""
    return [record for record in upload.records if record.processing_status != "completed"]
