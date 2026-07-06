"""Reads and writes the `.env` file backing runtime settings.

API keys are never echoed back in full -- the settings form only shows a
masked hint, and a blank submission leaves the existing key unchanged.
"""

from dataclasses import dataclass

from config.settings import PROJECT_ROOT, get_settings

ENV_PATH = PROJECT_ROOT / ".env"


@dataclass
class SettingsView:
    claude_api_key_hint: str
    tavily_api_key_hint: str
    hunter_api_key_hint: str
    institution_name: str
    stale_email_domain: str
    worker_count: int
    confidence_threshold: int
    retry_count: int
    cache_expiration_days: int
    output_dir: str


def _mask_secret(value: str) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def get_settings_view() -> SettingsView:
    settings = get_settings()
    return SettingsView(
        claude_api_key_hint=_mask_secret(settings.claude_api_key),
        tavily_api_key_hint=_mask_secret(settings.tavily_api_key),
        hunter_api_key_hint=_mask_secret(settings.hunter_api_key),
        institution_name=settings.institution_name,
        stale_email_domain=settings.stale_email_domain,
        worker_count=settings.worker_count,
        confidence_threshold=settings.confidence_threshold,
        retry_count=settings.retry_count,
        cache_expiration_days=settings.cache_expiration_days,
        output_dir=settings.output_dir,
    )


def _validate_int(name: str, raw: str, *, minimum: int, maximum: int | None = None) -> tuple[int | None, str | None]:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, f"{name} must be a whole number"
    if value < minimum or (maximum is not None and value > maximum):
        bound = f"{minimum}-{maximum}" if maximum is not None else f">= {minimum}"
        return None, f"{name} must be {bound}"
    return value, None


def update_settings(
    *,
    claude_api_key: str,
    tavily_api_key: str,
    hunter_api_key: str,
    institution_name: str,
    stale_email_domain: str,
    worker_count: str,
    confidence_threshold: str,
    retry_count: str,
    cache_expiration_days: str,
    output_dir: str,
) -> list[str]:
    """Validate and persist the form submission to `.env`.

    Returns a list of validation errors; if empty, `.env` was updated and
    the settings cache cleared so the new values take effect immediately.
    """
    errors: list[str] = []
    updates: dict[str, str] = {}

    if claude_api_key.strip():
        updates["CLAUDE_API_KEY"] = claude_api_key.strip()
    if tavily_api_key.strip():
        updates["TAVILY_API_KEY"] = tavily_api_key.strip()
    if hunter_api_key.strip():
        updates["HUNTER_API_KEY"] = hunter_api_key.strip()

    if not institution_name.strip():
        errors.append("Institution name cannot be blank")
    else:
        updates["INSTITUTION_NAME"] = institution_name.strip()

    updates["STALE_EMAIL_DOMAIN"] = stale_email_domain.strip()

    worker_count_value, error = _validate_int("Worker count", worker_count, minimum=1, maximum=50)
    if error:
        errors.append(error)
    else:
        updates["WORKER_COUNT"] = str(worker_count_value)

    confidence_value, error = _validate_int("Confidence threshold", confidence_threshold, minimum=0, maximum=100)
    if error:
        errors.append(error)
    else:
        updates["CONFIDENCE_THRESHOLD"] = str(confidence_value)

    retry_value, error = _validate_int("Retry count", retry_count, minimum=0, maximum=20)
    if error:
        errors.append(error)
    else:
        updates["RETRY_COUNT"] = str(retry_value)

    cache_days_value, error = _validate_int("Cache expiration", cache_expiration_days, minimum=1, maximum=365)
    if error:
        errors.append(error)
    else:
        updates["CACHE_EXPIRATION_DAYS"] = str(cache_days_value)

    if not output_dir.strip():
        errors.append("Output directory cannot be blank")
    else:
        updates["OUTPUT_DIR"] = output_dir.strip()

    if errors:
        return errors

    _write_env(updates)
    get_settings.cache_clear()
    return []


def _write_env(updates: dict[str, str]) -> None:
    """Update `.env` in place, preserving comments/ordering/unrelated keys."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    remaining = dict(updates)

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            new_lines.append(f"{key}={remaining.pop(key)}")
        else:
            new_lines.append(line)

    for key, value in remaining.items():
        new_lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n")
