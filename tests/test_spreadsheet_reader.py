import openpyxl

from app.services.spreadsheet_reader import read_workbook


def _make_workbook(tmp_path, headers, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    path = tmp_path / "test.xlsx"
    wb.save(path)
    return path


def test_detects_known_columns_and_preserves_extras(tmp_path):
    path = _make_workbook(
        tmp_path,
        ["First Name", "Last Name", "Email", "Major"],
        [["Jane", "Doe", "jane@example.com", "Computer Science"]],
    )

    parsed = read_workbook(path)

    assert parsed.column_map["First Name"] == "first_name"
    assert parsed.column_map["Last Name"] == "last_name"
    assert parsed.column_map["Email"] == "email"
    assert "Major" in parsed.extra_columns

    row = parsed.rows[0]
    assert row["first_name"] == "Jane"
    assert row["last_name"] == "Doe"
    assert row["email"] == "jane@example.com"
    assert row["_extra"]["Major"] == "Computer Science"


def test_blank_cells_become_none(tmp_path):
    path = _make_workbook(tmp_path, ["First Name", "LinkedIn"], [["Jane", ""]])

    parsed = read_workbook(path)

    assert parsed.rows[0]["linkedin"] is None


def test_header_alias_variants_map_to_same_field(tmp_path):
    path = _make_workbook(
        tmp_path,
        ["Given Name", "Class Year", "Home Country"],
        [["Sam", "2021", "Kenya"]],
    )

    parsed = read_workbook(path)

    assert parsed.column_map["Given Name"] == "first_name"
    assert parsed.column_map["Class Year"] == "graduation_year"
    assert parsed.column_map["Home Country"] == "country"
    assert parsed.extra_columns == []


def test_new_columns_already_present_are_loaded_not_treated_as_extra(tmp_path):
    path = _make_workbook(
        tmp_path,
        ["First Name", "Public Email", "Confidence", "Processing Status"],
        [["Jane", "jane@public.com", "97", "completed"]],
    )

    parsed = read_workbook(path)

    assert parsed.extra_columns == []
    row = parsed.rows[0]
    assert row["public_email"] == "jane@public.com"
    assert row["confidence"] == "97"
    assert row["processing_status"] == "completed"


def test_empty_workbook_has_zero_rows(tmp_path):
    path = _make_workbook(tmp_path, ["First Name", "Last Name"], [])

    parsed = read_workbook(path)

    assert parsed.total_rows == 0
    assert parsed.rows == []
