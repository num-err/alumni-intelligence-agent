from app.services.claude_types import ClaudeEnrichment
from app.services.evidence_service import build_evidence
from app.services.validation_service import ValidatedEnrichment


def _enrichment() -> ClaudeEnrichment:
    return ClaudeEnrichment(
        linkedin="https://linkedin.com/in/janedoe",
        email=None,
        graduation_year="2020",
        country_origin=None,
        current_location=None,
        current_employer=None,
        confidence=90,
        evidence=["LinkedIn profile matches name and State University"],
        review_required=False,
        reason="confident",
    )


def _validated(rejections=None) -> ValidatedEnrichment:
    return ValidatedEnrichment(
        linkedin="https://linkedin.com/in/janedoe",
        email=None,
        graduation_year="2020",
        country_origin=None,
        current_location=None,
        current_employer=None,
        confidence=90,
        rejections=rejections or [],
    )


def test_includes_claude_evidence_bullets():
    evidence = build_evidence(_enrichment(), _validated(), tier="medium", should_write=True)
    assert "LinkedIn profile matches name and State University" in evidence


def test_includes_validation_rejections():
    evidence = build_evidence(
        _enrichment(), _validated(rejections=["email value 'bad' is not valid"]), tier="medium", should_write=True
    )
    assert any("Validation rejected" in line for line in evidence)


def test_includes_confidence_tier():
    evidence = build_evidence(_enrichment(), _validated(), tier="auto", should_write=True)
    assert any("'auto' tier" in line for line in evidence)


def test_notes_when_existing_data_is_kept():
    evidence = build_evidence(_enrichment(), _validated(), tier="medium", should_write=False)
    assert any("Existing data kept" in line for line in evidence)
