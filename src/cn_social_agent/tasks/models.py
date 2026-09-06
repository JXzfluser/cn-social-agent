"""Task domain model and the state machine that enforces "approved means done".

The whole point of this module is one rule:

    A task is *complete* if and only if it is in ``APPROVED``.

Not "the agent finished speaking". Not "artifacts exist". Approved — after the
rubric ran and a human signed off. Every other terminal-looking state
(``submitted``, ``reviewing``, ``rejected``, ``failed``) is explicitly *not*
done, and the machine refuses transitions that would sneak past review.

Transition guards live with the states so that no caller — API route, runner,
or background job — can mark work complete without evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from cn_social_agent.core.tenant import DEFAULT_LOCALE


class TaskStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    ARCHIVED = "archived"


# The single source of truth for "is this finished".
DONE_STATUSES = frozenset({TaskStatus.APPROVED})

# States in which the task is still expected to move.
ACTIVE_STATUSES = frozenset(
    {TaskStatus.DRAFT, TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.SUBMITTED,
     TaskStatus.REVIEWING, TaskStatus.REJECTED}
)

_LEGAL_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.DRAFT: frozenset({TaskStatus.QUEUED, TaskStatus.ARCHIVED}),
    TaskStatus.QUEUED: frozenset({TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.ARCHIVED}),
    TaskStatus.RUNNING: frozenset(
        {TaskStatus.SUBMITTED, TaskStatus.FAILED, TaskStatus.ARCHIVED}
    ),
    TaskStatus.SUBMITTED: frozenset(
        {TaskStatus.REVIEWING, TaskStatus.RUNNING, TaskStatus.ARCHIVED}
    ),
    TaskStatus.REVIEWING: frozenset(
        {TaskStatus.APPROVED, TaskStatus.REJECTED, TaskStatus.ARCHIVED}
    ),
    TaskStatus.REJECTED: frozenset(
        {TaskStatus.RUNNING, TaskStatus.DRAFT, TaskStatus.ARCHIVED}
    ),
    # Approved is terminal by design: re-opening would erase the audit trail.
    TaskStatus.APPROVED: frozenset({TaskStatus.ARCHIVED}),
    TaskStatus.FAILED: frozenset({TaskStatus.QUEUED, TaskStatus.ARCHIVED}),
    TaskStatus.ARCHIVED: frozenset(),
}


class TransitionError(RuntimeError):
    """Raised when a status change is illegal or lacks required evidence."""


def can_transition(current: "TaskStatus | str", target: "TaskStatus | str") -> bool:
    try:
        src = TaskStatus(current)
        dst = TaskStatus(target)
    except ValueError:
        return False
    if src == dst:
        return True
    return dst in _LEGAL_TRANSITIONS[src]


def assert_transition(
    current: "TaskStatus | str",
    target: "TaskStatus | str",
    *,
    evidence: Optional["ReviewOutcome"] = None,
    human_approved: bool = False,
) -> None:
    """Validate a transition, with extra proof required to reach APPROVED."""
    try:
        src = TaskStatus(current)
        dst = TaskStatus(target)
    except ValueError as exc:
        raise TransitionError(f"unknown status: {exc}") from exc

    if src == dst:
        return
    if dst not in _LEGAL_TRANSITIONS[src]:
        raise TransitionError(
            f"illegal transition {src.value} -> {dst.value}"
        )

    if dst is TaskStatus.APPROVED:
        # The gate that makes "accepted" meaningful.
        if evidence is None:
            raise TransitionError(
                "cannot approve without a review outcome"
            )
        if not evidence.passed:
            raise TransitionError(
                "cannot approve: review did not pass "
                f"({len(evidence.unresolved_blockers)} unresolved blockers)"
            )
        if evidence.requires_human and not human_approved:
            raise TransitionError(
                "cannot approve: rubric requires explicit human sign-off"
            )


@dataclass
class Artifact:
    """A deliverable produced by an expert."""

    id: str = ""
    task_id: str = ""
    kind: str = "markdown"  # markdown | json | video | image
    name: str = ""
    content: str = ""
    storage_key: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None

    @property
    def text(self) -> str:
        return self.content or ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "kind": self.kind,
            "name": self.name,
            "content": self.content,
            "storage_key": self.storage_key,
            "meta": self.meta,
            "created_at": self.created_at,
            "size": len(self.content or ""),
        }


@dataclass
class TaskStep:
    """One entry in the execution trace."""

    id: str = ""
    task_id: str = ""
    kind: str = "info"  # info | tool | gate | error | result
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "kind": self.kind,
            "message": self.message,
            "data": self.data,
            "created_at": self.created_at,
        }


@dataclass
class Finding:
    """Result of evaluating one rubric item."""

    item_id: str
    title: str
    passed: bool
    severity: str  # blocker | major | minor
    kind: str  # auto | human
    message: str = ""
    pending: bool = False  # True for human items awaiting a decision

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "passed": self.passed,
            "severity": self.severity,
            "kind": self.kind,
            "message": self.message,
            "pending": self.pending,
        }


@dataclass
class ReviewOutcome:
    """The verdict produced by the review engine."""

    verdict: str = "fail"  # pass | fail
    findings: list[Finding] = field(default_factory=list)
    requires_human: bool = False
    human_decision: Optional[str] = None  # approve | reject | None
    human_note: str = ""
    score: int = 0
    created_at: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.verdict == "pass" and not self.unresolved_blockers

    @property
    def blockers(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "blocker"]

    @property
    def unresolved_blockers(self) -> list[Finding]:
        """Blockers that are failing **or** still waiting on a human."""
        return [
            f
            for f in self.findings
            if f.severity == "blocker" and (not f.passed or f.pending)
        ]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity != "blocker" and not f.passed]

    @property
    def pending_human(self) -> list[Finding]:
        return [f for f in self.findings if f.pending]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "passed": self.passed,
            "score": self.score,
            "requires_human": self.requires_human,
            "human_decision": self.human_decision,
            "human_note": self.human_note,
            "findings": [f.to_dict() for f in self.findings],
            "blockers": [f.to_dict() for f in self.unresolved_blockers],
            "warnings": [f.to_dict() for f in self.warnings],
            "pending_human": [f.to_dict() for f in self.pending_human],
            "created_at": self.created_at,
        }


@dataclass
class Task:
    """A unit of expert work owned by exactly one user."""

    id: str = ""
    user_id: str = ""
    expert_id: str = ""
    title: str = ""
    brief: str = ""
    status: TaskStatus = TaskStatus.DRAFT
    locale: str = DEFAULT_LOCALE
    attempt: int = 0
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Populated on read; not columns.
    artifacts: list[Artifact] = field(default_factory=list)
    steps: list[TaskStep] = field(default_factory=list)
    review: Optional[ReviewOutcome] = None

    @property
    def is_done(self) -> bool:
        return self.status in DONE_STATUSES

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def to_dict(self, *, with_detail: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "expert_id": self.expert_id,
            "title": self.title,
            "brief": self.brief,
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "is_done": self.is_done,
            "locale": self.locale,
            "attempt": self.attempt,
            "meta": self.meta,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if with_detail:
            data["artifacts"] = [a.to_dict() for a in self.artifacts]
            data["steps"] = [s.to_dict() for s in self.steps]
            data["review"] = self.review.to_dict() if self.review else None
        return data

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Task":
        status_raw = (row.get("status") or TaskStatus.DRAFT.value).strip().lower()
        try:
            status = TaskStatus(status_raw)
        except ValueError:
            status = TaskStatus.DRAFT
        meta = row.get("meta")
        return cls(
            id=str(row.get("id") or ""),
            user_id=str(row.get("user_id") or ""),
            expert_id=str(row.get("expert_id") or ""),
            title=str(row.get("title") or ""),
            brief=str(row.get("brief") or ""),
            status=status,
            locale=str(row.get("locale") or DEFAULT_LOCALE),
            attempt=int(row.get("attempt") or 0),
            meta=meta if isinstance(meta, dict) else {},
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
