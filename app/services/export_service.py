"""Exports an upload's enriched records back into a completed Excel workbook.

Preserves every canonical spreadsheet column (existing + new, per the
project spec) plus any unrecognized columns from the original upload,
which were kept verbatim in each record's `extra_data`.
"""

import datetime
from pathlib import Path
from typing import Any

import openpyxl

from app.models.alumni import AlumniRecord, Upload
from config import get_settings

# (AlumniRecord field, output header) in the order the finished roster
# should read in. `email`/`current_location`/`country_origin` are computed
# fields (see `_cell_value`) that fall back to the original spreadsheet
# value whenever enrichment didn't need to (or wasn't allowed to) replace it.
CANONICAL_HEADERS: list[tuple[str, str]] = [
    ("first_name", "First Name"),
    ("last_name", "Last Name"),
    ("graduation_year", "Graduation Year"),
    ("email", "Email"),
    ("linkedin", "LinkedIn"),
    ("current_location", "Current City/State"),
    ("country_origin", "Country of Origin"),
    ("current_employer", "Current Employer"),
    ("confidence", "Confidence"),
    ("evidence", "Evidence"),
    ("processing_status", "Processing Status"),
    ("review_required", "Review Required"),
    ("last_updated", "Last Updated"),
]

# computed field -> (enriched attr, original-spreadsheet fallback attr)
_FALLBACK_FIELDS: dict[str, tuple[str, str]] = {
    "email": ("public_email", "email"),
    "current_location": ("current_location", "city"),
    "country_origin": ("country_origin", "country"),
}


def _cell_value(record: AlumniRecord, field: str) -> Any:
    if field in _FALLBACK_FIELDS:
        enriched_attr, original_attr = _FALLBACK_FIELDS[field]
        return getattr(record, enriched_attr) or getattr(record, original_attr)

    value = getattr(record, field)
    if field == "evidence":
        return "; ".join(value) if value else ""
    if field == "review_required":
        return "Yes" if value else "No"
    if field == "last_updated" and value is not None:
        return value.replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
    return value


def export_upload(upload: Upload) -> Path:
    """Write a completed workbook for `upload` to the output directory.

    Returns the path of the written file.
    """
    settings = get_settings()
    settings.output_path.mkdir(parents=True, exist_ok=True)

    extra_headers = list(upload.extra_columns)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Alumni"

    sheet.append([label for _, label in CANONICAL_HEADERS] + extra_headers)

    for record in sorted(upload.records, key=lambda r: r.row_index):
        row = [_cell_value(record, field) for field, _ in CANONICAL_HEADERS]
        row += [record.extra_data.get(header) for header in extra_headers]
        sheet.append(row)

    stem = Path(upload.original_filename).stem
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    output_path = settings.output_path / f"{stem}_completed_{timestamp}.xlsx"
    workbook.save(output_path)
    return output_path
