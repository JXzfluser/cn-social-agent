"""The invariant that defines the product: only APPROVED is done.

These tests pin the rule from every angle — direct status assignment, legal
transitions, missing acceptance evidence, blockers that a human cannot
override — because this is the behaviour the whole workbench is built around.
"""

from __future__ import annotations

import pytest

from cn_social_agent.tasks import (
    Artifact,
    ReviewOutcome,
    Task,
    TaskStatus,
    TransitionError,
    assert_transition,
    can_transition,
)


# ── state machine ────────────────────────────────────────────────


def test_only_approved_counts_as_done():
    done = [s for s in TaskStatus if s in {TaskStatus.APPROVED}]
    assert done == [TaskStatus.APPROVED]
    for status in TaskStatus:
        assert Task(status=status).is_done is (status is TaskStatus.APPROVED)


def test_submitted_is_not_done_even_with_artifacts():
    task = Task(status=TaskStatus.SUBMITTED, artifacts=[Artifact(kind="markdown", content="x")])
    assert not task.is_done


def test_approved_is_terminal():
    assert can_transition(TaskStatus.APPROVED, TaskStatus.RUNNING) is False
    assert can_transition(TaskStatus.APPROVED, TaskStatus.REJECTED) is False
    assert can_transition(TaskStatus.APPROVED, TaskStatus.ARCHIVED) is True


def test_illegal_transitions_rejected():
    for src, dst in [
        (TaskStatus.DRAFT, TaskStatus.APPROVED),
        (TaskStatus.RUNNING, TaskStatus.APPROVED),
        (TaskStatus.SUBMITTED, TaskStatus.APPROVED),
        (TaskStatus.QUEUED, TaskStatus.REVIEWING),
        (TaskStatus.ARCHIVED, TaskStatus.RUNNING),
    ]:
        assert can_transition(src, dst) is False
        with pytest.raises(TransitionError):
            assert_transition(src, dst)


def test_rejected_loops_back_for_rework():
    assert can_transition(TaskStatus.REJECTED, TaskStatus.RUNNING)


# ── evidence required to approve ─────────────────────────────────


def _outcome(passed: bool, requires_human: bool = False, blocking: int = 0) -> ReviewOutcome:
    from cn_social_agent.tasks.models import Finding

    findings = []
    if blocking:
        findings += [
            Finding(item_id=f"b{i}", title="blocker", passed=False,
                    severity="blocker", kind="auto")
            for i in range(blocking)
        ]
    return ReviewOutcome(
        verdict="pass" if passed else "fail",
        findings=findings,
        requires_human=requires_human,
    )


def test_approve_requires_a_review_outcome():
    with pytest.raises(TransitionError, match="without a review outcome"):
        assert_transition(TaskStatus.REVIEWING, TaskStatus.APPROVED)


def test_approve_rejected_when_review_failed():
    with pytest.raises(TransitionError, match="did not pass"):
        assert_transition(
            TaskStatus.REVIEWING, TaskStatus.APPROVED,
            evidence=_outcome(passed=False, blocking=2),
        )


def test_approve_requires_human_signoff_when_rubric_demands_it():
    outcome = ReviewOutcome(
        verdict="pass",
        requires_human=True,
        findings=[
            __import__("cn_social_agent.tasks.models", fromlist=["Finding"]).Finding(
                item_id="human_signoff", title="sign-off", passed=True,
                severity="blocker", kind="human", pending=False,
            )
        ],
    )
    with pytest.raises(TransitionError, match="human sign-off"):
        assert_transition(
            TaskStatus.REVIEWING, TaskStatus.APPROVED,
            evidence=outcome, human_approved=False,
        )
    assert_transition(
        TaskStatus.REVIEWING, TaskStatus.APPROVED,
        evidence=outcome, human_approved=True,
    )


def test_pending_human_item_blocks_completion():
    from cn_social_agent.tasks.models import Finding

    outcome = ReviewOutcome(
        verdict="fail",
        findings=[
            Finding(item_id="human_signoff", title="sign-off", passed=False,
                    severity="blocker", kind="human", pending=True)
        ],
        requires_human=True,
    )
    assert outcome.passed is False
    assert len(outcome.unresolved_blockers) == 1


# ── end-to-end lifecycle on the engine ───────────────────────────


@pytest.mark.asyncio
async def test_full_lifecycle_draft_to_approved(fake, registry, as_user, engine_factory):
    as_user("u-alice")
    engine = engine_factory()

    task = await engine.create_task(
        "copywriter", "为什么小团队不要自建 MQ", "讲清成本、运维负担和替代方案"
    )
    assert task.status is TaskStatus.DRAFT
    assert task.is_done is False

    task = await engine.run_task(task.id)
    # Auto gates may pass, but the human rubric item is still pending.
    assert task.status is TaskStatus.REVIEWING
    assert task.is_done is False
    assert task.review is not None
    assert task.review.requires_human is True
    assert task.review.pending_human, "human sign-off must still be outstanding"

    with pytest.raises(Exception):
        # Not submittable for a decision before the task exists in review — but
        # more importantly, approving must still be gated on the verdict.
        await engine.decide("missing-task", "approve")

    task = await engine.decide(task.id, "approve", note="可以发")
    assert task.status is TaskStatus.APPROVED
    assert task.is_done is True

    persisted = await engine.get_task(task.id)
    assert persisted.status is TaskStatus.APPROVED
    assert persisted.is_done is True


@pytest.mark.asyncio
async def test_rejection_sends_task_back(fake, registry, as_user, engine_factory):
    as_user("u-alice")
    engine = engine_factory()
    task = await engine.create_task("copywriter", "主题", "要求")
    task = await engine.run_task(task.id)

    task = await engine.decide(task.id, "reject", note="太水，重写")
    assert task.status is TaskStatus.REJECTED
    assert task.is_done is False
    assert task.review.human_decision == "reject"


@pytest.mark.asyncio
async def test_artifacts_are_recorded_and_trace_is_persisted(
    fake, registry, as_user, engine_factory
):
    as_user("u-alice")
    engine = engine_factory()
    task = await engine.create_task("research-analyst", "是否该上 K8s", "团队 5 人，每天 10w 请求")
    task = await engine.run_task(task.id)

    assert task.artifacts, "expert must leave a deliverable behind"
    assert any(a.kind == "markdown" for a in task.artifacts)
    kinds = {s.kind for s in task.steps}
    assert {"created", "start", "status", "gate"} & kinds, kinds


@pytest.mark.asyncio
async def test_execution_records_an_attempt(fake, registry, as_user, engine_factory):
    as_user("u-alice")
    engine = engine_factory()
    task = await engine.create_task("copywriter", "标题", "正文要求")
    task = await engine.run_task(task.id)
    assert task.attempt == 1
    task = await engine.run_task(task.id)
    assert task.attempt == 2
