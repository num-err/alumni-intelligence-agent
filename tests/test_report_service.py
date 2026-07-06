import openpyxl
import pytest

from app.services.ingestion_service import ingest_upload
from app.services.report_service import build_report


@pytest.fixture(autouse=True)
def _isolated_progress_registry(monkeypatch):
    """Progress tracking is a process-lifetime global registry keyed by
    upload_id; other test files create runs with small ids too, so give
    each test here its own empty registry to avoid cross-test collisions.
    """
    import app.workers.progress_tracker as progress_tracker

    monkeypatch.setattr(progress_tracker, "_active_runs", {})


def _make_workbook(tmp_path, headers, rows, name="roster.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    path = tmp_path / name
    wb.save(path)
    return path


def test_report_counts_processed_skipped_and_reviewed(tmp_path, db_session):
    path = _make_workbook(
        tmp_path,
        ["First Name", "Processing Status"],
        [["Jane", "completed"], ["John", "pending"], ["Sam", "failed"]],
    )
    upload = ingest_upload(db_session, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)
    upload.records[0].review_required = True  # Jane needs review
    db_session.commit()

    report = build_report(upload)

    assert report.total_rows == 3
    assert report.rows_processed == 2  # completed + failed
    assert report.rows_skipped == 1  # still pending
    assert report.rows_reviewed == 1


def test_report_counts_missing_email_and_linkedin(tmp_path, db_session):
    path = _make_workbook(tmp_path, ["First Name", "Email", "LinkedIn"], [["Jane", "", ""], ["John", "j@x.com", ""]])
    upload = ingest_upload(db_session, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)

    report = build_report(upload)

    assert report.missing_email_count == 1
    assert report.missing_linkedin_count == 2


def test_report_average_confidence_ignores_null_confidence(tmp_path, db_session):
    path = _make_workbook(tmp_path, ["First Name"], [["Jane"], ["John"]])
    upload = ingest_upload(db_session, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)
    upload.records[0].confidence = 80
    upload.records[1].confidence = None
    db_session.commit()

    report = build_report(upload)

    assert report.average_confidence == 80


def test_report_handles_no_confidence_values(tmp_path, db_session):
    path = _make_workbook(tmp_path, ["First Name"], [["Jane"]])
    upload = ingest_upload(db_session, original_filename="roster.xlsx", stored_filename="roster.xlsx", stored_path=path)

    report = build_report(upload)

    assert report.average_confidence is None
    assert report.api_requests is None  # no run in progress_tracker for this upload
    assert report.elapsed_seconds is None
