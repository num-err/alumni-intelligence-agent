import openpyxl

from app.services.ingestion_service import ingest_upload, rows_needing_processing


def _make_workbook(tmp_path, headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    path = tmp_path / "roster.xlsx"
    wb.save(path)
    return path


def test_ingest_creates_upload_and_records(tmp_path, db_session):
    path = _make_workbook(
        tmp_path,
        ["First Name", "Last Name", "Email", "Processing Status"],
        [
            ["Jane", "Doe", "jane@example.com", "completed"],
            ["John", "Smith", "", "pending"],
        ],
    )

    upload = ingest_upload(
        db_session,
        original_filename="roster.xlsx",
        stored_filename="stored.xlsx",
        stored_path=path,
    )

    assert upload.id is not None
    assert upload.total_rows == 2
    assert len(upload.records) == 2


def test_completed_rows_are_skipped_from_the_queue(tmp_path, db_session):
    path = _make_workbook(
        tmp_path,
        ["First Name", "Processing Status"],
        [["Jane", "completed"], ["John", "pending"], ["Sam", ""]],
    )

    upload = ingest_upload(
        db_session,
        original_filename="roster.xlsx",
        stored_filename="stored.xlsx",
        stored_path=path,
    )

    queued = rows_needing_processing(upload)
    queued_names = {record.first_name for record in queued}

    assert queued_names == {"John", "Sam"}


def test_extra_columns_preserved_on_record(tmp_path, db_session):
    path = _make_workbook(
        tmp_path,
        ["First Name", "Major", "Dorm"],
        [["Jane", "Computer Science", "Willets"]],
    )

    upload = ingest_upload(
        db_session,
        original_filename="roster.xlsx",
        stored_filename="stored.xlsx",
        stored_path=path,
    )

    record = upload.records[0]
    assert record.extra_data == {"Major": "Computer Science", "Dorm": "Willets"}


def test_confidence_and_review_required_are_parsed(tmp_path, db_session):
    path = _make_workbook(
        tmp_path,
        ["First Name", "Confidence", "Review Required"],
        [["Jane", "150", "yes"], ["John", "not-a-number", "no"]],
    )

    upload = ingest_upload(
        db_session,
        original_filename="roster.xlsx",
        stored_filename="stored.xlsx",
        stored_path=path,
    )

    jane, john = upload.records
    assert jane.confidence == 100  # clamped to the valid 0-100 range
    assert jane.review_required is True
    assert john.confidence is None
    assert john.review_required is False
