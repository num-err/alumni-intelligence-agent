from app.models.alumni import AlumniRecord
from app.services.review_service import approve, edit, reject


def _record(**overrides) -> AlumniRecord:
    defaults = dict(
        first_name="Jane",
        last_name="Doe",
        linkedin="https://linkedin.com/in/janedoe",
        public_email=None,
        graduation_year="2020",
        country_origin="Kenya",
        current_location=None,
        confidence=60,
        evidence=["Claude's original evidence"],
        review_required=True,
    )
    defaults.update(overrides)
    return AlumniRecord(**defaults)


def test_approve_sets_full_confidence_and_clears_review_flag():
    record = _record()

    approve(record)

    assert record.confidence == 100
    assert record.review_required is False
    assert record.linkedin == "https://linkedin.com/in/janedoe"  # unchanged
    assert any("approved" in line.lower() for line in record.evidence)
    assert record.last_updated is not None


def test_reject_clears_all_candidate_fields():
    record = _record()

    reject(record)

    assert record.linkedin is None
    assert record.public_email is None
    assert record.graduation_year is None
    assert record.country_origin is None
    assert record.current_location is None
    assert record.confidence is None
    assert record.review_required is False
    assert any("rejected" in line.lower() for line in record.evidence)


def test_reject_preserves_prior_evidence_for_audit_trail():
    record = _record()

    reject(record)

    assert "Claude's original evidence" in record.evidence


def test_edit_applies_valid_field_updates():
    record = _record()

    errors = edit(
        record,
        {
            "linkedin": "https://linkedin.com/in/newprofile",
            "public_email": "jane@example.com",
            "graduation_year": "2019",
            "country_origin": "Nigeria",
            "current_location": "Boston, MA",
        },
    )

    assert errors == []
    assert record.linkedin == "https://linkedin.com/in/newprofile"
    assert record.public_email == "jane@example.com"
    assert record.graduation_year == "2019"
    assert record.country_origin == "Nigeria"
    assert record.current_location == "Boston, MA"
    assert record.confidence == 100
    assert record.review_required is False


def test_edit_rejects_invalid_values_and_leaves_record_untouched():
    record = _record()

    errors = edit(
        record,
        {
            "linkedin": "https://facebook.com/janedoe",  # invalid
            "public_email": "not-an-email",  # invalid
            "graduation_year": "2020",
            "country_origin": "Kenya",
            "current_location": "",
        },
    )

    assert len(errors) == 2
    # record must be untouched since validation failed
    assert record.linkedin == "https://linkedin.com/in/janedoe"
    assert record.review_required is True
    assert record.confidence == 60


def test_edit_allows_clearing_a_field_by_blanking_it():
    record = _record()

    errors = edit(
        record,
        {
            "linkedin": "",
            "public_email": "",
            "graduation_year": "2020",
            "country_origin": "Kenya",
            "current_location": "",
        },
    )

    assert errors == []
    assert record.linkedin is None
