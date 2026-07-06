import pytest

from app.services.settings_service import get_settings_view, update_settings
from config import get_settings


@pytest.fixture(autouse=True)
def _temp_env(tmp_path, monkeypatch):
    """Point the settings service at a scratch .env file (so tests never
    touch the real project .env), and mirror the same starting values as
    real process env vars -- pydantic-settings prioritizes actual env vars
    over the env_file, so `get_settings()` (which always reads the real
    .env's *path*, unaffected by the ENV_PATH patch below) still reflects
    this fixture's intended starting state.
    """
    import app.services.settings_service as settings_service

    env_path = tmp_path / ".env"
    env_path.write_text(
        "CLAUDE_API_KEY=sk-original-key\n"
        "TAVILY_API_KEY=tvly-original-key\n"
        "HUNTER_API_KEY=hunter-original-key\n"
        "WORKER_COUNT=5\n"
        "CONFIDENCE_THRESHOLD=80\n"
        "RETRY_COUNT=3\n"
        "CACHE_EXPIRATION_DAYS=30\n"
        "OUTPUT_DIR=output\n"
    )
    monkeypatch.setattr(settings_service, "ENV_PATH", env_path)

    monkeypatch.setenv("CLAUDE_API_KEY", "sk-original-key")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-original-key")
    monkeypatch.setenv("HUNTER_API_KEY", "hunter-original-key")
    monkeypatch.setenv("WORKER_COUNT", "5")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "80")
    monkeypatch.setenv("RETRY_COUNT", "3")
    monkeypatch.setenv("CACHE_EXPIRATION_DAYS", "30")
    monkeypatch.setenv("OUTPUT_DIR", "output")

    get_settings.cache_clear()
    yield env_path
    get_settings.cache_clear()


def test_get_settings_view_masks_api_keys():
    view = get_settings_view()

    assert view.claude_api_key_hint.endswith("-key")
    assert "*" in view.claude_api_key_hint
    assert view.worker_count == 5


def test_update_settings_writes_valid_values(_temp_env):
    errors = update_settings(
        claude_api_key="",
        tavily_api_key="",
        hunter_api_key="",
        institution_name="Test University",
        stale_email_domain="",
        worker_count="10",
        confidence_threshold="70",
        retry_count="5",
        cache_expiration_days="60",
        output_dir="my_output",
    )

    assert errors == []
    contents = _temp_env.read_text()
    assert "WORKER_COUNT=10" in contents
    assert "CONFIDENCE_THRESHOLD=70" in contents
    assert "OUTPUT_DIR=my_output" in contents
    # untouched keys preserved
    assert "CLAUDE_API_KEY=sk-original-key" in contents


def test_blank_api_key_leaves_existing_key_unchanged(_temp_env):
    update_settings(
        claude_api_key="",
        tavily_api_key="",
        hunter_api_key="",
        institution_name="Test University",
        stale_email_domain="",
        worker_count="5",
        confidence_threshold="80",
        retry_count="3",
        cache_expiration_days="30",
        output_dir="output",
    )

    contents = _temp_env.read_text()
    assert "CLAUDE_API_KEY=sk-original-key" in contents


def test_non_blank_api_key_overwrites_existing_key(_temp_env):
    update_settings(
        claude_api_key="sk-new-key",
        tavily_api_key="",
        hunter_api_key="",
        institution_name="Test University",
        stale_email_domain="",
        worker_count="5",
        confidence_threshold="80",
        retry_count="3",
        cache_expiration_days="30",
        output_dir="output",
    )

    contents = _temp_env.read_text()
    assert "CLAUDE_API_KEY=sk-new-key" in contents


def test_invalid_worker_count_rejected_and_env_untouched(_temp_env):
    errors = update_settings(
        claude_api_key="",
        tavily_api_key="",
        hunter_api_key="",
        institution_name="Test University",
        stale_email_domain="",
        worker_count="not-a-number",
        confidence_threshold="80",
        retry_count="3",
        cache_expiration_days="30",
        output_dir="output",
    )

    assert len(errors) == 1
    contents = _temp_env.read_text()
    assert "WORKER_COUNT=5" in contents  # unchanged


def test_confidence_threshold_out_of_range_rejected(_temp_env):
    errors = update_settings(
        claude_api_key="",
        tavily_api_key="",
        hunter_api_key="",
        institution_name="Test University",
        stale_email_domain="",
        worker_count="5",
        confidence_threshold="150",
        retry_count="3",
        cache_expiration_days="30",
        output_dir="output",
    )

    assert len(errors) == 1
    assert "Confidence threshold" in errors[0]


def test_blank_output_dir_rejected(_temp_env):
    errors = update_settings(
        claude_api_key="",
        tavily_api_key="",
        hunter_api_key="",
        institution_name="Test University",
        stale_email_domain="",
        worker_count="5",
        confidence_threshold="80",
        retry_count="3",
        cache_expiration_days="30",
        output_dir="   ",
    )

    assert len(errors) == 1
    assert "Output directory" in errors[0]
