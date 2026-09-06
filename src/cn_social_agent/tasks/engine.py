"""Task engine: orchestration, persistence and the enforcement point.

The engine is the only component allowed to move a task between statuses, and
it does so through :func:`~cn_social_agent.tasks.models.assert_transition`.
That keeps the "approved means done" invariant in exactly one place.

Every read and write goes through :class:`~cn_social_agent.core.db.TenantDB`,
so the engine never even sees another tenant's rows — Postgres filters them
before they reach Python.

Tables (all RLS-protected, see ``scripts/ensure_nexus_schema.py``)::

    wb_nexus_tasks      one row per task, owned by user_id
    wb_nexus_steps      execution trace
    wb_nexus_artifacts  deliverables
    wb_nexus_reviews    acceptance outcomes (immutable audit record)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from cn_social_agent.core.ai import TenantAI, tenant_ai
from cn_social_agent.core.db import TenantDB, tenant_db
from cn_social_agent.core.events import emit
from cn_social_agent.core.tenant import require
from cn_social_agent.experts.models import Expert
from cn_social_agent.experts.registry import ExpertRegistry

from .models import (
    Artifact,
    ReviewOutcome,
    Task,
    TaskStatus,
    TaskStep,
    assert_transition,
    utcnow,
)
from .review import ReviewEngine
from .runners import get_runner

logger = logging.getLogger(__name__)

TASKS_TABLE = "wb_nexus_tasks"
STEPS_TABLE = "wb_nexus_steps"
ARTIFACTS_TABLE = "wb_nexus_artifacts"
REVIEWS_TABLE = "wb_nexus_reviews"


class TaskError(RuntimeError):
    pass


class TaskEngine:
    """Owns the task lifecycle for the bound tenant."""

    def __init__(
        self,
        client: Any,
        registry: ExpertRegistry,
        *,
        db: Optional[TenantDB] = None,
        ai: Optional[TenantAI] = None,
        reviewer: Optional[ReviewEngine] = None,
    ) -> None:
        self._client = client
        self.registry = registry
        self._db = db or tenant_db(client)
        self._ai = ai
        self.reviewer = reviewer or ReviewEngine()

    # ── helpers ──────────────────────────────────────────────────

    @property
    def db(self) -> TenantDB:
        return self._db

    @property
    def ai(self) -> Optional[TenantAI]:
        if self._ai is None and self._client is not None:
            try:
                self._ai = tenant_ai(self._client)
            except Exception:  # noqa: BLE001
                self._ai = None
        return self._ai

    @staticmethod
    def _tenant_id() -> str:
        return require().user_id

    async def _trace(self, task_id: str, kind: str, message: str, **data: Any) -> None:
        """Persist a step and broadcast it to the tenant's event stream."""
        row = {
            "task_id": task_id,
            "kind": kind,
            "message": message,
            "data": data or {},
        }
        try:
            await self._db.create(STEPS_TABLE, row)
        except Exception as exc:  # noqa: BLE001
            logger.warning("step persist failed: %s", exc)
        await emit(self._tenant_id(), task_id, kind, message, **data)

    async def _set_status(self, task: Task, target: TaskStatus, **evidence: Any) -> None:
        assert_transition(
            task.status,
            target,
            evidence=evidence.get("evidence"),
            human_approved=bool(evidence.get("human_approved")),
        )
        task.status = target
        await self._db.update_by_id(
            TASKS_TABLE, task.id, {"status": target.value, "updated_at": utcnow()}
        )
        await self._trace(task.id, "status", target.value)

    # ── reads ────────────────────────────────────────────────────

    async def list_tasks(
        self, *, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> list[Task]:
        filters: dict[str, str] = {}
        if status:
            filters["status"] = f"eq.{status}"
        rows = await self._db.query(
            TASKS_TABLE,
            filters=filters or None,
            order="updated_at.desc",
            limit=limit,
            offset=offset,
        )
        tasks = [Task.from_row(row) for row in rows]
        for task in tasks:
            task.review = await self.latest_review(task.id)
        return tasks

    async def get_task(self, task_id: str, *, with_detail: bool = True) -> Task:
        row = await self._db.get_by_id(TASKS_TABLE, task_id)
        if row is None:
            raise TaskError("task not found")
        task = Task.from_row(row)
        if with_detail:
            task.artifacts = await self.artifacts(task_id)
            task.steps = await self.steps(task_id)
            task.review = await self.latest_review(task_id)
        return task

    async def steps(self, task_id: str, limit: int = 200) -> list[TaskStep]:
        rows = await self._db.query(
            STEPS_TABLE,
            filters={"task_id": f"eq.{task_id}"},
            order="created_at.asc",
            limit=limit,
        )
        return [
            TaskStep(
                id=str(r.get("id") or ""),
                task_id=str(r.get("task_id") or ""),
                kind=str(r.get("kind") or "info"),
                message=str(r.get("message") or ""),
                data=r.get("data") if isinstance(r.get("data"), dict) else {},
                created_at=r.get("created_at"),
            )
            for r in rows
        ]

    async def artifacts(self, task_id: str) -> list[Artifact]:
        rows = await self._db.query(
            ARTIFACTS_TABLE,
            filters={"task_id": f"eq.{task_id}"},
            order="created_at.asc",
            limit=100,
        )
        return [
            Artifact(
                id=str(r.get("id") or ""),
                task_id=str(r.get("task_id") or ""),
                kind=str(r.get("kind") or "markdown"),
                name=str(r.get("name") or ""),
                content=str(r.get("content") or ""),
                storage_key=str(r.get("storage_key") or ""),
                meta=r.get("meta") if isinstance(r.get("meta"), dict) else {},
                created_at=r.get("created_at"),
            )
            for r in rows
        ]

    async def latest_review(self, task_id: str) -> Optional[ReviewOutcome]:
        rows = await self._db.query(
            REVIEWS_TABLE,
            filters={"task_id": f"eq.{task_id}"},
            order="created_at.desc",
            limit=1,
        )
        if not rows:
            return None
        return _review_from_row(rows[0])

    # ── lifecycle ────────────────────────────────────────────────

    async def create_task(
        self,
        expert_id: str,
        title: str,
        brief: str,
        *,
        locale: str = "zh-CN",
        meta: Optional[dict[str, Any]] = None,
    ) -> Task:
        expert = self.registry.require(expert_id)
        title = (title or "").strip()
        if not title:
            raise TaskError("title is required")
        if not (brief or "").strip():
            raise TaskError("brief is required")

        row = {
            "expert_id": expert.id,
            "title": title[:300],
            "brief": brief.strip(),
            "status": TaskStatus.DRAFT.value,
            "locale": locale,
            "attempt": 0,
            "meta": dict(meta or {}),
            "updated_at": utcnow(),
        }
        rows = await self._db.create(TASKS_TABLE, row)
        task = Task.from_row(rows[0] if rows else {**row})
        await self._trace(task.id, "created", "task created", expert=expert.id)
        return task

    # Routes from any resumable state onto RUNNING, one legal hop at a time.
    _RUN_LADDER: dict[TaskStatus, tuple[TaskStatus, ...]] = {
        TaskStatus.DRAFT: (TaskStatus.QUEUED, TaskStatus.RUNNING),
        TaskStatus.QUEUED: (TaskStatus.RUNNING,),
        TaskStatus.REJECTED: (TaskStatus.RUNNING,),
        TaskStatus.SUBMITTED: (TaskStatus.RUNNING,),
        TaskStatus.FAILED: (TaskStatus.QUEUED, TaskStatus.RUNNING),
        # Reviewing must pass through rejected — you cannot silently abandon
        # an in-flight review by re-running the task.
        TaskStatus.REVIEWING: (TaskStatus.REJECTED, TaskStatus.RUNNING),
    }

    async def _ensure_running(self, task: Task) -> None:
        if task.status is TaskStatus.APPROVED:
            raise TaskError("task is already approved; archive it instead of re-running")
        if task.status is TaskStatus.ARCHIVED:
            raise TaskError("task is archived")
        for target in self._RUN_LADDER.get(task.status, ()):  # type: ignore[arg-type]
            await self._set_status(task, target)

    async def run_task(self, task_id: str) -> Task:
        """Execute the expert work and immediately run acceptance."""
        task = await self.get_task(task_id, with_detail=False)
        expert = self.registry.require(task.expert_id)

        await self._ensure_running(task)
        await self._trace(
            task.id, "start", "expert started",
            expert=expert.id, runner=expert.runner, attempt=task.attempt + 1,
        )

        # Clear artifacts from the previous attempt so review judges fresh work.
        await self._db.delete(ARTIFACTS_TABLE, {"task_id": f"eq.{task_id}"})

        runner = get_runner(expert.runner)

        async def _emit(kind: str, message: str, **data: Any) -> None:
            await self._trace(task_id, kind, message, **data)

        try:
            artifacts = await runner(expert, task, self.ai, _emit)
        except Exception as exc:  # noqa: BLE001
            await self._trace(task_id, "error", f"execution failed: {exc}")
            await self._set_status(task, TaskStatus.FAILED)
            raise TaskError(f"execution failed: {exc}") from exc

        for artifact in artifacts:
            await self._db.create(
                ARTIFACTS_TABLE,
                {
                    "task_id": task.id,
                    "kind": artifact.kind,
                    "name": artifact.name,
                    "content": artifact.content,
                    "storage_key": artifact.storage_key,
                    "meta": artifact.meta,
                },
            )
        await self._trace(task.id, "result", "artifacts stored", count=len(artifacts))

        await self._db.update_by_id(
            TASKS_TABLE, task.id, {"attempt": task.attempt + 1, "updated_at": utcnow()}
        )
        await self._set_status(task, TaskStatus.SUBMITTED)
        return await self.review_task(task.id)

    async def _ensure_reviewable(self, task: Task) -> None:
        """Walk a task up to SUBMITTED so the rubric can be evaluated.

        Used when a user manually requests acceptance on a task that has not
        been through the automatic run path (or was edited after a run).
        """
        if task.status in (TaskStatus.SUBMITTED, TaskStatus.REVIEWING):
            return
        if task.status in (TaskStatus.APPROVED, TaskStatus.ARCHIVED):
            return
        ladder = {
            TaskStatus.DRAFT: (TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.SUBMITTED),
            TaskStatus.QUEUED: (TaskStatus.RUNNING, TaskStatus.SUBMITTED),
            TaskStatus.RUNNING: (TaskStatus.SUBMITTED,),
            TaskStatus.REJECTED: (TaskStatus.RUNNING, TaskStatus.SUBMITTED),
        }
        for target in ladder.get(task.status, ()):  # type: ignore[arg-type]
            await self._set_status(task, target)

    async def review_task(self, task_id: str) -> Task:
        """Run the rubric and record the outcome (does not approve by itself)."""
        task = await self.get_task(task_id, with_detail=True)
        if task.status is TaskStatus.APPROVED:
            return await self.get_task(task_id)
        expert = self.registry.require(task.expert_id)

        await self._ensure_reviewable(task)

        previous = await self.latest_review(task_id)
        human_decision = previous.human_decision if previous else None
        human_note = previous.human_note if previous else ""

        await self._set_status(task, TaskStatus.REVIEWING)
        outcome = self.reviewer.evaluate(
            task, task.artifacts, expert,
            human_decision=human_decision, human_note=human_note,
        )

        await self._db.create(
            REVIEWS_TABLE,
            {
                "task_id": task_id,
                "verdict": outcome.verdict,
                "passed": outcome.passed,
                "score": outcome.score,
                "requires_human": outcome.requires_human,
                "human_decision": outcome.human_decision,
                "human_note": outcome.human_note,
                "findings": [f.to_dict() for f in outcome.findings],
            },
        )
        await self._trace(
            task.id, "gate", "acceptance evaluated",
            verdict=outcome.verdict, score=outcome.score,
            blockers=len(outcome.unresolved_blockers),
        )
        task.review = outcome

        if outcome.passed:
            # Auto-gates and any prior human sign-off are all green.
            await self._set_status(
                task, TaskStatus.APPROVED,
                evidence=outcome, human_approved=True,
            )
        elif not [b for b in outcome.unresolved_blockers if not b.pending]:
            # Only human items remain — stay in review, wait for a decision.
            pass
        else:
            await self._set_status(task, TaskStatus.REJECTED)
        return await self.get_task(task_id)

    async def decide(self, task_id: str, decision: str, note: str = "") -> Task:
        """Human verdict: approve (task completes) or reject (send back)."""
        decision = (decision or "").strip().lower()
        if decision not in ("approve", "reject"):
            raise TaskError("decision must be 'approve' or 'reject'")

        task = await self.get_task(task_id, with_detail=True)
        if task.status not in (TaskStatus.SUBMITTED, TaskStatus.REVIEWING):
            raise TaskError(
                f"task is {task.status.value}; only submitted or in-review tasks "
                "can be accepted or rejected"
            )
        expert = self.registry.require(task.expert_id)

        outcome = self.reviewer.evaluate(
            task, task.artifacts, expert, human_decision=decision, human_note=note,
        )
        await self._db.create(
            REVIEWS_TABLE,
            {
                "task_id": task_id,
                "verdict": outcome.verdict,
                "passed": outcome.passed,
                "score": outcome.score,
                "requires_human": outcome.requires_human,
                "human_decision": decision,
                "human_note": note,
                "findings": [f.to_dict() for f in outcome.findings],
            },
        )
        await self._trace(
            task.id, "human", f"reviewer {decision}d",
            verdict=outcome.verdict, score=outcome.score,
        )

        if task.status is TaskStatus.SUBMITTED:
            await self._set_status(task, TaskStatus.REVIEWING)

        if decision == "approve":
            await self._set_status(
                task, TaskStatus.APPROVED,
                evidence=outcome, human_approved=True,
            )
        else:
            await self._set_status(task, TaskStatus.REJECTED)
        return await self.get_task(task_id)

    async def add_user_message(self, task_id: str, content: str) -> None:
        """Append a follow-up message from the user to the task trace.

        WorkBuddy-style tasks are conversational: the user keeps adding
        requirements while the task lives. Messages are persisted as steps
        (kind="user") so they survive reloads and appear in the workspace.
        """
        task = await self.get_task(task_id, with_detail=False)
        text = (content or "").strip()
        if not text:
            raise TaskError("message content is required")
        await self._trace(task.id, "user", text[:4000])

    async def archive(self, task_id: str) -> Task:
        task = await self.get_task(task_id, with_detail=False)
        await self._set_status(task, TaskStatus.ARCHIVED)
        return await self.get_task(task_id)

    async def delete_task(self, task_id: str) -> None:
        """Cascade delete within the tenant's own rows."""
        await self._db.delete(STEPS_TABLE, {"task_id": f"eq.{task_id}"})
        await self._db.delete(ARTIFACTS_TABLE, {"task_id": f"eq.{task_id}"})
        await self._db.delete(REVIEWS_TABLE, {"task_id": f"eq.{task_id}"})
        await self._db.delete_by_id(TASKS_TABLE, task_id)


def _review_from_row(row: dict[str, Any]) -> ReviewOutcome:
    from .models import Finding

    findings_raw = row.get("findings")
    findings: list[Finding] = []
    if isinstance(findings_raw, list):
        for item in findings_raw:
            if isinstance(item, dict):
                findings.append(
                    Finding(
                        item_id=str(item.get("item_id") or ""),
                        title=str(item.get("title") or ""),
                        passed=bool(item.get("passed")),
                        severity=str(item.get("severity") or "major"),
                        kind=str(item.get("kind") or "auto"),
                        message=str(item.get("message") or ""),
                        pending=bool(item.get("pending")),
                    )
                )
    return ReviewOutcome(
        verdict=str(row.get("verdict") or "fail"),
        findings=findings,
        requires_human=bool(row.get("requires_human")),
        human_decision=row.get("human_decision"),
        human_note=str(row.get("human_note") or ""),
        score=int(row.get("score") or 0),
        created_at=row.get("created_at"),
    )
