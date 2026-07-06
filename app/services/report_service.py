"""Computes the end-of-run report stats for one upload.

Combines durable per-record state (the source of truth for counts) with
the in-memory `RunProgress` for a run's API usage/elapsed time, which is
only available while (or immediately after) that run's process is alive.
"""

from dataclasses import dataclass

from app.models.alumni import Upload
from app.workers.progress_tracker import get_run

TERMINAL_STATUSES = {"completed", "failed"}


@dataclass
class UploadReport:
    upload_id: int
    filename: str
    total_rows: int
    rows_processed: int
    rows_skipped: int
    rows_reviewed: int
    missing_email_count: int
    missing_linkedin_count: int
    average_confidence: float | None
    api_requests: int | None
    elapsed_seconds: float | None


def build_report(upload: Upload) -> UploadReport:
    records = upload.records

    processed = [r for r in records if r.processing_status in TERMINAL_STATUSES]
    reviewed = [r for r in records if r.review_required]
    missing_email = [r for r in records if not r.email and not r.public_email]
    missing_linkedin = [r for r in records if not r.linkedin]

    confidences = [r.confidence for r in records if r.confidence is not None]
    average_confidence = sum(confidences) / len(confidences) if confidences else None

    progress = get_run(upload.id)

    return UploadReport(
        upload_id=upload.id,
        filename=upload.original_filename,
        total_rows=upload.total_rows,
        rows_processed=len(processed),
        rows_skipped=len(records) - len(processed),
        rows_reviewed=len(reviewed),
        missing_email_count=len(missing_email),
        missing_linkedin_count=len(missing_linkedin),
        average_confidence=average_confidence,
        api_requests=progress.api_requests if progress else None,
        elapsed_seconds=progress.elapsed_seconds if progress else None,
    )
