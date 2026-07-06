import datetime

from app.models.cache import ClaudeResponseCache
from app.services.claude_cache_service import get_cached_response, store_response
from app.services.claude_types import ClaudeEnrichment


def _enrichment(linkedin="https://linkedin.com/in/janedoe") -> ClaudeEnrichment:
    return ClaudeEnrichment(
        linkedin=linkedin,
        email=None,
        graduation_year="2020",
        country_origin=None,
        current_location=None,
        current_employer=None,
        confidence=90,
        evidence=["match"],
        review_required=False,
        reason="confident",
    )


def test_cache_miss_returns_none(db_session):
    assert get_cached_response(db_session, "claude-sonnet-5", "some prompt") is None


def test_store_then_retrieve(db_session):
    store_response(db_session, "claude-sonnet-5", "prompt text", _enrichment())

    cached = get_cached_response(db_session, "claude-sonnet-5", "prompt text")

    assert cached is not None
    assert cached.linkedin == "https://linkedin.com/in/janedoe"


def test_different_model_is_a_different_cache_key(db_session):
    store_response(db_session, "claude-sonnet-5", "prompt text", _enrichment())

    assert get_cached_response(db_session, "claude-opus-4-8", "prompt text") is None


def test_expired_entries_are_not_returned(db_session):
    from config import get_settings

    store_response(db_session, "claude-sonnet-5", "prompt text", _enrichment())

    entry = db_session.query(ClaudeResponseCache).first()
    entry.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=get_settings().cache_expiration_days + 1
    )
    db_session.commit()

    assert get_cached_response(db_session, "claude-sonnet-5", "prompt text") is None


def test_storing_again_overwrites_existing_entry(db_session):
    store_response(db_session, "claude-sonnet-5", "prompt text", _enrichment(linkedin="https://old.com"))
    store_response(db_session, "claude-sonnet-5", "prompt text", _enrichment(linkedin="https://new.com"))

    cached = get_cached_response(db_session, "claude-sonnet-5", "prompt text")

    assert cached.linkedin == "https://new.com"
