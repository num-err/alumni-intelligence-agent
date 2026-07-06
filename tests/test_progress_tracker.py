import pytest

from app.workers.progress_tracker import create_run, get_run


def test_create_run_is_retrievable():
    progress = create_run(upload_id=1, total=10)
    assert get_run(1) is progress


def test_processed_and_remaining_computed_correctly():
    progress = create_run(upload_id=2, total=10)
    progress.record_success("Jane Doe", 95)
    progress.record_failure("John Smith", "boom")

    assert progress.processed == 2
    assert progress.remaining == 8


def test_average_confidence_is_none_when_nothing_completed():
    progress = create_run(upload_id=3, total=5)
    assert progress.average_confidence is None


def test_average_confidence_computed_across_successes():
    progress = create_run(upload_id=4, total=5)
    progress.record_success("A", 100)
    progress.record_success("B", 80)

    assert progress.average_confidence == 90


def test_is_running_until_finished():
    progress = create_run(upload_id=5, total=1)
    assert progress.is_running is True

    progress.finish()

    assert progress.is_running is False


def test_worker_status_tracking():
    progress = create_run(upload_id=6, total=1)
    progress.set_worker_status(0, status="searching", student="Jane Doe")

    assert progress.workers[0].status == "searching"
    assert progress.workers[0].current_student == "Jane Doe"


def test_api_requests_counter():
    progress = create_run(upload_id=7, total=1)
    progress.record_api_request()
    progress.record_api_request()

    assert progress.api_requests == 2


def test_estimated_seconds_remaining_is_none_before_any_progress():
    progress = create_run(upload_id=8, total=10)
    assert progress.estimated_seconds_remaining is None


def test_estimated_seconds_remaining_is_none_when_nothing_left():
    progress = create_run(upload_id=9, total=1)
    progress.record_success("A", 90)

    assert progress.estimated_seconds_remaining is None


def test_estimated_seconds_remaining_extrapolates_from_elapsed_rate():
    import datetime

    progress = create_run(upload_id=10, total=4)
    # simulate 10 seconds having elapsed with 2 of 4 rows done
    progress.started_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10)
    progress.record_success("A", 90)
    progress.record_success("B", 90)

    # rate = 2 rows / 10s = 0.2 rows/s; 2 remaining -> ~10s
    assert progress.estimated_seconds_remaining == pytest.approx(10, rel=0.2)


def test_elapsed_seconds_freezes_after_finish():
    import datetime
    import time

    progress = create_run(upload_id=11, total=1)
    progress.finish()
    frozen = progress.elapsed_seconds

    time.sleep(0.05)
    assert progress.elapsed_seconds == frozen
