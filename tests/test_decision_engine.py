import pytest

from app.models.alumni import AlumniRecord
from app.services.claude_types import ClaudeEnrichment
from app.services.decision_engine import apply_decision, decide
from app.services.hunter_email_service import EmailResolution
from config import get_settings


@pytest.fixture(autouse=True)
def _stale_email_domain(monkeypatch):
    """Pin the stale-email domain so these tests don't depend on the local
    .env file's real-world configuration."""
    get_settings.cache_clear()
    monkeypatch.setenv("STALE_EMAIL_DOMAIN", "test.edu")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _enrichment(**overrides) -> ClaudeEnrichment:
    defaults = dict(
        linkedin="https://linkedin.com/in/janedoe",
        email="jane@example.com",
        graduation_year="2020",
        country_origin="Kenya",
        current_location="New York, NY",
        current_employer="Example Corp",
        confidence=90,
        evidence=["matched LinkedIn"],
        review_required=False,
        reason="confident match",
    )
    defaults.update(overrides)
    return ClaudeEnrichment(**defaults)


def test_confidence_95_and_above_is_auto_tier_and_not_review():
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    decision = decide(record, _enrichment(confidence=97))

    assert decision.confidence_tier == "auto"
    assert decision.review_required is False


def test_confidence_80_to_94_is_medium_tier_and_not_review():
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    decision = decide(record, _enrichment(confidence=85))

    assert decision.confidence_tier == "medium"
    assert decision.review_required is False


def test_confidence_below_80_is_review_tier():
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    decision = decide(record, _enrichment(confidence=60))

    assert decision.confidence_tier == "review"
    assert decision.review_required is True


def test_claudes_own_review_flag_forces_review_even_at_high_confidence():
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    decision = decide(record, _enrichment(confidence=97, review_required=True))

    assert decision.review_required is True


def test_first_pass_always_writes_when_no_existing_confidence():
    record = AlumniRecord(first_name="Jane", last_name="Doe", confidence=None)
    decision = decide(record, _enrichment(confidence=50))

    assert decision.should_write is True
    assert decision.fields["linkedin"] == "https://linkedin.com/in/janedoe"


def _fully_filled_record(**overrides) -> AlumniRecord:
    defaults = dict(
        first_name="Jane",
        last_name="Doe",
        confidence=90,
        linkedin="https://linkedin.com/in/existing",
        email="jane@company.com",
        graduation_year="2019",
        country_origin="Ghana",
        current_location="Boston, MA",
        current_employer="Existing Corp",
    )
    defaults.update(overrides)
    return AlumniRecord(**defaults)


def test_does_not_overwrite_already_filled_fields_below_auto_write_confidence():
    record = _fully_filled_record()
    decision = decide(record, _enrichment(confidence=90))

    assert decision.should_write is False
    assert decision.fields == {}


def test_overwrites_already_filled_fields_when_confidence_reaches_auto_write():
    record = _fully_filled_record()
    decision = decide(record, _enrichment(confidence=97))

    assert decision.should_write is True
    assert decision.fields["linkedin"] == "https://linkedin.com/in/janedoe"
    assert decision.fields["graduation_year"] == "2020"
    assert decision.fields["country_origin"] == "Kenya"
    assert decision.fields["current_location"] == "New York, NY"


def test_empty_fields_are_written_even_when_other_fields_are_protected():
    # linkedin is already filled and confidence is below the auto-write bar,
    # so it should be protected -- but graduation_year is still blank on
    # this record and should be filled in regardless of confidence.
    record = AlumniRecord(first_name="Jane", last_name="Doe", linkedin="https://linkedin.com/in/existing")
    decision = decide(record, _enrichment(confidence=60))

    assert decision.should_write is True
    assert "linkedin" not in decision.fields
    assert decision.fields["graduation_year"] == "2020"


def test_email_left_alone_when_already_non_stale():
    record = AlumniRecord(first_name="Jane", last_name="Doe", email="jane@company.com")
    decision = decide(record, _enrichment(confidence=97, email="jane@newcompany.com"))

    assert "public_email" not in decision.fields
    # other empty fields still get filled in
    assert decision.fields["graduation_year"] == "2020"


def test_email_enriched_when_known_email_is_stale_domain():
    record = AlumniRecord(first_name="Jane", last_name="Doe", email="jdoe1@test.edu")
    decision = decide(record, _enrichment(confidence=60, email="jane@company.com"))

    assert decision.fields["public_email"] == "jane@company.com"


def test_email_enriched_when_known_email_is_missing():
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    decision = decide(record, _enrichment(confidence=60, email="jane@company.com"))

    assert decision.fields["public_email"] == "jane@company.com"


def test_invalid_fields_are_excluded_from_write_but_valid_fields_still_written():
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    decision = decide(record, _enrichment(linkedin="https://facebook.com/janedoe"))

    assert "linkedin" not in decision.fields
    assert decision.fields["public_email"] == "jane@example.com"
    assert any("Validation rejected" in line for line in decision.evidence)


def test_apply_decision_writes_fields_and_metadata_when_should_write():
    record = AlumniRecord(first_name="Jane", last_name="Doe")
    decision = decide(record, _enrichment(confidence=97))

    apply_decision(record, decision)

    assert record.linkedin == "https://linkedin.com/in/janedoe"
    assert record.public_email == "jane@example.com"
    assert record.confidence == 97
    assert record.processing_status == "completed"
    assert record.review_required is False
    assert record.last_updated is not None


def test_apply_decision_leaves_fields_untouched_when_not_should_write():
    record = _fully_filled_record()
    decision = decide(record, _enrichment(confidence=90))

    apply_decision(record, decision)

    assert record.linkedin == "https://linkedin.com/in/existing"
    assert record.confidence == 90  # unchanged
    assert record.processing_status == "completed"  # status still updates


def test_hunter_verified_email_bypasses_auto_write_gate():
    # Claude's overall confidence (60) is well below the auto-write bar, but
    # a Hunter-verified email is an independent signal about the email
    # specifically and should still replace an existing stale-domain address.
    record = AlumniRecord(first_name="Jane", last_name="Doe", email="jdoe1@test.edu", public_email="old@x.com")
    resolution = EmailResolution(email="jane@newco.com", hunter_verified=True)

    decision = decide(record, _enrichment(confidence=60), resolution)

    assert decision.fields["public_email"] == "jane@newco.com"


def test_hunter_unverified_email_is_dropped_not_written():
    record = AlumniRecord(first_name="Jane", last_name="Doe", email="jdoe1@test.edu")
    resolution = EmailResolution(email=None, hunter_verified=False)

    decision = decide(record, _enrichment(confidence=97), resolution)

    assert "public_email" not in decision.fields


def test_hunter_not_consulted_when_email_does_not_need_enrichment():
    # Hunter is only ever consulted when the known email needs replacing --
    # if it's already a good non-stale address, any email_resolution
    # passed in should be ignored entirely.
    record = AlumniRecord(first_name="Jane", last_name="Doe", email="jane@company.com")
    resolution = EmailResolution(email="jane@newco.com", hunter_verified=True)

    decision = decide(record, _enrichment(confidence=97), resolution)

    assert "public_email" not in decision.fields


def test_review_threshold_is_configurable(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "50")
    get_settings.cache_clear()

    try:
        record = AlumniRecord(first_name="Jane", last_name="Doe")
        decision = decide(record, _enrichment(confidence=60))

        # would be "review" under the default threshold of 80, but the
        # configured threshold of 50 makes 60 a "medium" write
        assert decision.confidence_tier == "medium"
        assert decision.review_required is False
    finally:
        get_settings.cache_clear()
