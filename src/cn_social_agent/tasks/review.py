"""The acceptance engine: rubric in, verdict out.

This is the component that makes "expert tasks can be accepted, and only
passing counts as done" a guarantee rather than a slogan.

Evaluation is deliberately conservative:

* an unknown gate **fails** its item (never silently passes),
* a crashing gate **fails** its item,
* a human item with no decision yet is recorded as ``pending`` and counts as
  an unresolved blocker,
* ``verdict == pass`` requires *zero* unresolved blockers.

The resulting :class:`ReviewOutcome` is the only evidence the task state
machine accepts when moving a task to ``approved``.
"""

from __future__ import annotations

from typing import Optional

from cn_social_agent.experts.models import Expert, pick

from .gates import GateContext, run_gate
from .models import Artifact, Finding, ReviewOutcome, Task, utcnow


class ReviewEngine:
    """Evaluates an expert's deliverable against its rubric."""

    def evaluate(
        self,
        task: Task,
        artifacts: list[Artifact],
        expert: Expert,
        *,
        human_decision: Optional[str] = None,
        human_note: str = "",
        locale: Optional[str] = None,
    ) -> ReviewOutcome:
        effective_locale = locale or task.locale
        ctx = GateContext(
            task=task,
            artifacts=artifacts,
            brief=task.brief,
            locale=effective_locale,
            options=dict(expert.options or {}),
        )

        findings: list[Finding] = []
        for item in expert.rubric:
            if item.needs_human:
                findings.append(self._human_finding(item, ctx, human_decision))
            else:
                findings.append(run_gate(item, ctx))

        requires_human = any(f.kind == "human" for f in findings)
        unresolved = [
            f for f in findings if f.severity == "blocker" and (not f.passed or f.pending)
        ]
        verdict = "pass" if not unresolved else "fail"
        score = self._score(findings)

        return ReviewOutcome(
            verdict=verdict,
            findings=findings,
            requires_human=requires_human,
            human_decision=human_decision,
            human_note=human_note,
            score=score,
            created_at=utcnow(),
        )

    @staticmethod
    def _human_finding(item, ctx: GateContext, decision: Optional[str]) -> Finding:
        title = pick(item.title, ctx.locale)
        hint = pick(item.hint, ctx.locale)
        if decision == "approve":
            return Finding(
                item_id=item.id,
                title=title,
                passed=True,
                severity=item.severity,
                kind="human",
                message=hint or "approved by reviewer",
                pending=False,
            )
        if decision == "reject":
            return Finding(
                item_id=item.id,
                title=title,
                passed=False,
                severity=item.severity,
                kind="human",
                message="rejected by reviewer",
                pending=False,
            )
        return Finding(
            item_id=item.id,
            title=title,
            passed=False,
            severity=item.severity,
            kind="human",
            message=hint or "awaiting human decision",
            pending=True,
        )

    @staticmethod
    def _score(findings: list[Finding]) -> int:
        if not findings:
            return 0
        passed = sum(1 for f in findings if f.passed and not f.pending)
        return round(passed * 100 / len(findings))

    # ── helpers used by the API layer ────────────────────────────

    @staticmethod
    def summarise(outcome: ReviewOutcome, locale: str = "zh-CN") -> str:
        if outcome.passed:
            return "验收通过" if locale.startswith("zh") else "Review passed"
        blockers = outcome.unresolved_blockers
        pending = outcome.pending_human
        if locale.startswith("zh"):
            if pending and not [b for b in blockers if not b.pending]:
                return f"等待人工验收（{len(pending)} 项）"
            return f"验收未通过：{len(blockers)} 项阻塞"
        if pending and not [b for b in blockers if not b.pending]:
            return f"Awaiting human sign-off ({len(pending)} item(s))"
        return f"Review failed: {len(blockers)} blocker(s)"
