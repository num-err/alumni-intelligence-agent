"""Database models for uploaded spreadsheets and the alumni rows within them.

Each uploaded workbook becomes one `Upload` row plus one `AlumniRecord` per
spreadsheet row. Any spreadsheet column that isn't one of the known/new
canonical fields is preserved verbatim in `AlumniRecord.extra_data` so it
survives round-tripping back to Excel.
"""

import datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.engine import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(1024))
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    total_rows: Mapped[int] = mapped_column(default=0)

    # original header -> canonical field name, e.g. {"First Name": "first_name"}
    column_mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    # headers present in the source file with no canonical mapping, preserved as-is
    extra_columns: Mapped[list] = mapped_column(JSON, default=list)

    records: Mapped[list["AlumniRecord"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )


class AlumniRecord(Base):
    __tablename__ = "alumni_records"
    __table_args__ = (UniqueConstraint("upload_id", "row_index", name="uq_upload_row"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id"))
    row_index: Mapped[int]

    # --- existing spreadsheet columns -----------------------------------
    first_name: Mapped[str | None] = mapped_column(String(255), default=None)
    last_name: Mapped[str | None] = mapped_column(String(255), default=None)
    email: Mapped[str | None] = mapped_column(String(255), default=None)
    linkedin: Mapped[str | None] = mapped_column(String(512), default=None)
    graduation_year: Mapped[str | None] = mapped_column(String(16), default=None)
    country: Mapped[str | None] = mapped_column(String(255), default=None)
    city: Mapped[str | None] = mapped_column(String(255), default=None)

    # --- new enrichment columns ------------------------------------------
    public_email: Mapped[str | None] = mapped_column(String(255), default=None)
    country_origin: Mapped[str | None] = mapped_column(String(255), default=None)
    current_location: Mapped[str | None] = mapped_column(String(255), default=None)
    current_employer: Mapped[str | None] = mapped_column(String(255), default=None)
    confidence: Mapped[int | None] = mapped_column(default=None)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    processing_status: Mapped[str] = mapped_column(String(32), default="pending")
    review_required: Mapped[bool] = mapped_column(default=False)
    last_updated: Mapped[datetime.datetime | None] = mapped_column(default=None)

    # any source columns with no canonical mapping, keyed by original header
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)

    upload: Mapped["Upload"] = relationship(back_populates="records")
