from app.services.claude_types import ClaudeEnrichment
from app.services.validation_service import validate_enrichment


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


def test_all_valid_fields_pass_through_unchanged():
    result = validate_enrichment(_enrichment())

    assert result.linkedin == "https://linkedin.com/in/janedoe"
    assert result.email == "jane@example.com"
    assert result.graduation_year == "2020"
    assert result.country_origin == "Kenya"
    assert result.current_location == "New York, NY"
    assert result.current_employer == "Example Corp"
    assert result.confidence == 90
    assert result.rejections == []


def test_invalid_fields_are_dropped_and_recorded_as_rejections():
    result = validate_enrichment(_enrichment(linkedin="https://facebook.com/janedoe", email="not-an-email"))

    assert result.linkedin is None
    assert result.email is None
    assert len(result.rejections) == 2
    # other valid fields are unaffected by the rejected ones
    assert result.country_origin == "Kenya"


def test_confidence_is_clamped():
    result = validate_enrichment(_enrichment(confidence=150))
    assert result.confidence == 100
