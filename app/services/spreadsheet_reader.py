"""Reads an uploaded .xlsx workbook into normalized row dictionaries.

This module only parses the file -- it does not touch the database. See
`app.services.ingestion_service` for turning a `ParsedWorkbook` into
persisted records.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.column_mapping import CANONICAL_FIELDS, detect_column


@dataclass
class ParsedWorkbook:
    """Result of parsing a workbook: normalized rows plus column detection info."""

    rows: list[dict[str, Any]]
    column_map: dict[str, str]  # original header -> canonical field
    extra_columns: list[str]  # headers with no canonical mapping, preserved verbatim

    @property
    def total_rows(self) -> int:
        return len(self.rows)


def _clean(value: Any) -> str | None:
    """Blank cells and NaN become None; everything else is stripped text."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def read_workbook(path: Path) -> ParsedWorkbook:
    """Parse a spreadsheet into normalized rows.

    Every column is read as text (no float-coercion of things like
    graduation years). Headers matching a known alias are mapped to their
    canonical field; anything else is kept under each row's "_extra" dict so
    it can be written back to the export unmodified.
    """
    df = pd.read_excel(path, dtype=str, keep_default_na=False, engine="openpyxl")

    column_map: dict[str, str] = {}
    seen_canonical: set[str] = set()
    extra_columns: list[str] = []

    for header in df.columns:
        header_str = str(header)
        canonical = detect_column(header_str)
        if canonical and canonical not in seen_canonical:
            column_map[header_str] = canonical
            seen_canonical.add(canonical)
        else:
            extra_columns.append(header_str)

    rows: list[dict[str, Any]] = []
    for _, series in df.iterrows():
        row: dict[str, Any] = dict.fromkeys(CANONICAL_FIELDS)
        extra_data: dict[str, str | None] = {}

        for header, value in series.items():
            header_str = str(header)
            cleaned = _clean(value)
            canonical = column_map.get(header_str)
            if canonical:
                row[canonical] = cleaned
            else:
                extra_data[header_str] = cleaned

        row["_extra"] = extra_data
        rows.append(row)

    return ParsedWorkbook(rows=rows, column_map=column_map, extra_columns=extra_columns)
