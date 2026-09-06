"""Acceptance gates behave deterministically, and fail closed.

The second half of this file pins the most important product rule: a human
cannot approve work that failed a machine blocker. Sign-off is required, but
it is not sufficient.
"""

from __future__ import annotations

import json

import pytest

from cn_social_agent.tasks import Artifact, Task, TaskStatus, utcnow
from cn_social_agent.tasks.gates import GateContext, run_gate
from cn_social_agent.tasks.review import ReviewEngine
from cn_social_agent.experts.models import RubricItem


def _ctx(content: str = "", *, kind: str = "markdown", meta=None, title="选题") -> GateContext:
    task = Task(id="t1", title=title, brief="要求", meta=meta or {})
    artifacts = [Artifact(kind=kind, content=content)] if content else []
    return GateContext(task=task, artifacts=artifacts, brief="要求")


def _item(rule: str, **params) -> RubricItem:
    return RubricItem(id="x", title={"zh-CN": "检查", "en-US": "check"},
                      rule=rule, params=params)


# ── individual gates ─────────────────────────────────────────────


def test_artifact_exists_detects_missing_and_wrong_kind():
    assert run_gate(_item("artifact_exists"), _ctx()).passed is False
    assert run_gate(_item("artifact_exists"), _ctx("hi")).passed is True
    assert run_gate(_item("artifact_exists", kind="json"), _ctx("hi")).passed is False
    assert (
        run_gate(_item("artifact_exists", kind="json"), _ctx("{}", kind="json")).passed
        is True
    )


def test_text_length_bounds():
    assert run_gate(_item("text_length", min=5, max=10), _ctx("1234567")).passed is True
    assert run_gate(_item("text_length", min=5, max=10), _ctx("12")).passed is False
    assert run_gate(_item("text_length", min=5, max=10), _ctx("1" * 50)).passed is False


def test_required_sections_min_matches():
    item = _item("required_sections", any_of=["## A", "## B"], min_matches=2)
    assert run_gate(item, _ctx("## A\n## B")).passed is True
    assert run_gate(item, _ctx("## A")).passed is False


def test_forbidden_patterns_flags_ai_filler():
    item = _item("forbidden_patterns", patterns=["在当今", "Let's dive in"])
    assert run_gate(item, _ctx("在当今时代")).passed is False
    assert run_gate(item, _ctx("直接给结论")).passed is True


def test_forbidden_patterns_scope_first_scene():
    body = json.dumps(
        {"scenes": [{"narration": "大家好我是小明"}, {"narration": "开始吧"}]}
    )
    item = _item("forbidden_patterns", patterns=["大家好我是"], scope="first_scene")
    assert run_gate(item, _ctx(body, kind="json")).passed is False
    ok = json.dumps({"scenes": [{"narration": "先看结论"}, {"narration": "大家好我是小明"}]})
    assert run_gate(item, _ctx(ok, kind="json")).passed is True


def test_keyword_present_uses_cjk_ngrams():
    item = _item("keyword_present", min_hits=1)
    ctx = _ctx("这篇讲的是小团队自建消息队列的代价", title="小团队要不要自建 MQ")
    assert run_gate(item, ctx).passed is True
    assert run_gate(item, _ctx("完全无关的另一些内容", title="小团队要不要自建 MQ")).passed is False


def test_json_fields_and_counts():
    body = json.dumps({"title": "t", "scenes": [{"id": 1}, {"id": 2}, {"id": 3}],
                       "total_duration": 9})
    assert run_gate(_item("json_fields", fields=["title", "scenes"]),
                    _ctx(body, kind="json")).passed is True
    assert run_gate(_item("json_fields", fields=["missing"]),
                    _ctx(body, kind="json")).passed is False
    assert run_gate(_item("scene_count", min=3, max=10), _ctx(body, kind="json")).passed is True
    assert run_gate(_item("scene_count", min=5), _ctx(body, kind="json")).passed is False
    assert run_gate(_item("scene_count", min=1), _ctx("not json", kind="json")).passed is False


def test_storyboard_duration_respects_budget():
    body = json.dumps({
        "title": "t",
        "scenes": [{"narration": "短" * 10, "duration": 5},
                   {"narration": "短" * 10, "duration": 5}],
        "total_duration": 10,
    })
    ctx = _ctx(body, kind="json", meta={"duration": 15})
    assert run_gate(_item("storyboard_duration"), ctx).passed is True

    tight = _ctx(body, kind="json", meta={"duration": 5})
    assert run_gate(_item("storyboard_duration"), tight).passed is False


def test_line_length_gates():
    body = json.dumps({"cards": [{"title": "一句话结论", "body": "短" * 10},
                                 {"title": "翻车标题", "body": "长" * 200}]})
    ctx = _ctx(body, kind="json")
    assert run_gate(_item("max_line_length", field="body", max=80), ctx).passed is False
    assert run_gate(_item("min_line_length", field="title", min=4), ctx).passed is True


def test_unknown_gate_fails_closed():
    finding = run_gate(_item("no_such_gate"), _ctx("content"))
    assert finding.passed is False
    assert "unknown gate" in finding.message


def test_crashing_gate_fails_closed():
    gate_ctx = _ctx("content")
    item = _item("text_length", min="not-a-number")
    finding = run_gate(item, gate_ctx)
    assert finding.passed is False


# ── verdict composition ──────────────────────────────────────────


def _expert_with(items, options=None):
    from cn_social_agent.experts.models import Expert

    return Expert(id="test", name={"zh-CN": "测试专家", "en-US": "Test"},
                  rubric=items, options=options or {})


def test_major_failures_do_not_block():
    engine = ReviewEngine()
    expert = _expert_with([
        RubricItem(id="minor", title="提醒", severity="major",
                   rule="text_length", params={"min": 9999}),
    ])
    outcome = engine.evaluate(Task(id="t", title="x"), [Artifact(content="short")], expert)
    assert outcome.verdict == "pass"
    assert outcome.passed is True
    assert outcome.warnings


def test_blocker_failure_fails_the_verdict():
    engine = ReviewEngine()
    expert = _expert_with([
        RubricItem(id="b", title="阻塞", severity="blocker",
                   rule="text_length", params={"min": 9999}),
    ])
    outcome = engine.evaluate(Task(id="t", title="x"), [Artifact(content="s")], expert)
    assert outcome.verdict == "fail"
    assert len(outcome.unresolved_blockers) == 1


def test_human_signoff_is_required_and_sufficient_when_gates_pass():
    engine = ReviewEngine()
    expert = _expert_with([
        RubricItem(id="g", title="门禁", severity="blocker",
                   rule="artifact_exists", params={}),
        RubricItem(id="h", title="人工", kind="human", severity="blocker"),
    ])
    task = Task(id="t", title="x")
    artifact = [Artifact(content="ok")]

    pending = engine.evaluate(task, artifact, expert)
    assert pending.passed is False
    assert pending.pending_human

    approved = engine.evaluate(task, artifact, expert, human_decision="approve")
    assert approved.passed is True
    assert approved.requires_human is True


def test_human_cannot_override_a_failed_machine_gate():
    engine = ReviewEngine()
    expert = _expert_with([
        RubricItem(id="g", title="门禁", severity="blocker",
                   rule="text_length", params={"min": 9999}),
        RubricItem(id="h", title="人工", kind="human", severity="blocker"),
    ])
    outcome = engine.evaluate(
        Task(id="t", title="x"), [Artifact(content="s")], expert, human_decision="approve"
    )
    assert outcome.passed is False, "human sign-off must not override a failed blocker"


def test_score_reflects_pass_ratio():
    engine = ReviewEngine()
    expert = _expert_with([
        RubricItem(id="a", title="A", severity="blocker", rule="artifact_exists", params={}),
        RubricItem(id="b", title="B", severity="blocker",
                   rule="text_length", params={"min": 9999}),
    ])
    outcome = engine.evaluate(Task(id="t", title="x"), [Artifact(content="s")], expert)
    assert outcome.score == 50


# ── engine-level enforcement ─────────────────────────────────────


@pytest.mark.asyncio
async def test_approving_a_failing_task_keeps_it_rejected(
    fake, registry, as_user, engine_factory
):
    as_user("u-alice")
    engine = engine_factory()
    task = await engine.create_task("copywriter", "主题", "要求")
    task = await engine.run_task(task.id)

    # Sabotage the deliverable so a machine blocker fails.
    await engine.db.delete("wb_nexus_artifacts", {"task_id": f"eq.{task.id}"})
    await engine.db.create(
        "wb_nexus_artifacts",
        {"task_id": task.id, "kind": "markdown", "name": "empty.md", "content": "", "meta": {}},
    )

    outcome_task = await engine.review_task(task.id)
    assert outcome_task.status is TaskStatus.REJECTED

    with pytest.raises(Exception):
        await engine.decide(task.id, "approve")

    final = await engine.get_task(task.id)
    assert final.status is not TaskStatus.APPROVED
    assert final.is_done is False
