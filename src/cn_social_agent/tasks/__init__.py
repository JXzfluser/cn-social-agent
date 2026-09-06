"""Expert task lifecycle — dispatch, execute, and accept.

Public surface::

    TaskEngine   orchestrates tasks (the only thing that changes status)
    ReviewEngine evaluates a deliverable against its expert's rubric
    TaskStatus   the state machine, where only ``approved`` means done
"""

from __future__ import annotations

from .models import (
    ACTIVE_STATUSES,
    DONE_STATUSES,
    Artifact,
    Finding,
    ReviewOutcome,
    Task,
    TaskStatus,
    TaskStep,
    TransitionError,
    assert_transition,
    can_transition,
    utcnow,
)
from .gates import GATES, GateContext, run_gate
from .review import ReviewEngine
from .runners import RUNNERS, get_runner
from .engine import (
    ARTIFACTS_TABLE,
    REVIEWS_TABLE,
    STEPS_TABLE,
    TASKS_TABLE,
    TaskEngine,
    TaskError,
)

__all__ = [
    "ACTIVE_STATUSES",
    "DONE_STATUSES",
    "Artifact",
    "Finding",
    "ReviewOutcome",
    "Task",
    "TaskStatus",
    "TaskStep",
    "TransitionError",
    "assert_transition",
    "can_transition",
    "utcnow",
    "GATES",
    "GateContext",
    "run_gate",
    "ReviewEngine",
    "RUNNERS",
    "get_runner",
    "ARTIFACTS_TABLE",
    "REVIEWS_TABLE",
    "STEPS_TABLE",
    "TASKS_TABLE",
    "TaskEngine",
    "TaskError",
]
