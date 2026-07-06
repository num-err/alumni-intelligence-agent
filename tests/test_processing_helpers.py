from app.api.processing import _format_duration, _progress_context
from app.workers.progress_tracker import create_run

# Use a high upload_id range to avoid colliding with other tests that
# create runs in the shared, process-lifetime `_active_runs` registry.
UPLOAD_ID_BASE = 900_000


def test_format_duration_none_is_calculating():
    assert _format_duration(None) == "calculating..."


def test_format_duration_seconds_only():
    assert _format_duration(45) == "45s"


def test_format_duration_minutes_and_seconds():
    assert _format_duration(125) == "2m 5s"


def test_format_duration_hours_and_minutes():
    assert _format_duration(3725) == "1h 2m"


def test_progress_context_when_no_run_started():
    context = _progress_context(UPLOAD_ID_BASE + 1)

    assert context["progress"] is None
    assert context["is_running"] is False


def test_progress_context_computes_percent_and_displays():
    upload_id = UPLOAD_ID_BASE + 2
    progress = create_run(upload_id, total=4)
    progress.record_success("A", 90)

    context = _progress_context(upload_id)

    assert context["progress"] is progress
    assert context["percent"] == 25
    assert context["is_running"] is True
    assert "elapsed_display" in context
    assert "eta_display" in context


def test_progress_context_shows_100_percent_when_nothing_to_process():
    upload_id = UPLOAD_ID_BASE + 3
    create_run(upload_id, total=0)

    context = _progress_context(upload_id)

    assert context["percent"] == 100
