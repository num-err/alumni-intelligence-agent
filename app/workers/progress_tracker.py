"""In-memory tracking of a running enrichment job.

This is intentionally not persisted -- the durable checkpoint is each
record's `processing_status` in the database (see `enrichment_worker.py`).
This module only tracks the transient, human-facing state a live
dashboard (Milestone 7) needs: current worker activity, running totals,
and recent errors. If the process restarts, this state is simply rebuilt
from scratch the next time a run starts; nothing about resumability
depends on it.
"""

import datetime
from dataclasses import dataclass, field


@dataclass
class WorkerStatus:
    worker_id: int
    status: str = "idle"  # idle | searching | reasoning | verifying email | writing
    current_student: str | None = None


@dataclass
class RunProgress:
    upload_id: int
    total: int
    completed: int = 0
    failed: int = 0
    confidence_sum: int = 0
    api_requests: int = 0
    last_completed_student: str | None = None
    errors: list[str] = field(default_factory=list)
    started_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    finished_at: datetime.datetime | None = None
    workers: dict[int, WorkerStatus] = field(default_factory=dict)

    @property
    def processed(self) -> int:
        return self.completed + self.failed

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.processed)

    @property
    def average_confidence(self) -> float | None:
        return (self.confidence_sum / self.completed) if self.completed else None

    @property
    def is_running(self) -> bool:
        return self.finished_at is None

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at or datetime.datetime.now(datetime.timezone.utc)
        return (end - self.started_at).total_seconds()

    @property
    def estimated_seconds_remaining(self) -> float | None:
        """Rough ETA: (elapsed / processed) * remaining, once we have a rate to extrapolate from."""
        if self.processed == 0 or self.remaining == 0 or self.elapsed_seconds <= 0:
            return None
        rate_per_second = self.processed / self.elapsed_seconds
        return self.remaining / rate_per_second

    def set_worker_status(self, worker_id: int, *, status: str, student: str | None) -> None:
        self.workers[worker_id] = WorkerStatus(worker_id=worker_id, status=status, current_student=student)

    def record_success(self, student_name: str, confidence: int) -> None:
        self.completed += 1
        self.confidence_sum += confidence
        self.last_completed_student = student_name

    def record_failure(self, student_name: str, error: str) -> None:
        self.failed += 1
        self.errors.append(f"{student_name}: {error}")

    def record_api_request(self) -> None:
        self.api_requests += 1

    def finish(self) -> None:
        self.finished_at = datetime.datetime.now(datetime.timezone.utc)


_active_runs: dict[int, RunProgress] = {}


def create_run(upload_id: int, total: int) -> RunProgress:
    progress = RunProgress(upload_id=upload_id, total=total)
    _active_runs[upload_id] = progress
    return progress


def get_run(upload_id: int) -> RunProgress | None:
    return _active_runs.get(upload_id)
