"""Expert pack loading, validation and localisation."""

from __future__ import annotations

import pytest

from cn_social_agent.experts import ExpertRegistry
from cn_social_agent.experts.models import Expert, RubricItem, pick
from cn_social_agent.experts.registry import default_search_dirs


@pytest.fixture(scope="module")
def registry() -> ExpertRegistry:
    return ExpertRegistry().scan()


def test_builtin_packs_load_without_errors(registry):
    assert registry.errors == []
    assert len(registry) >= 5


def test_every_expert_has_a_rubric_with_a_human_signoff(registry):
    for expert in registry.all():
        assert expert.rubric, f"{expert.id} has no rubric"
        assert any(item.needs_human for item in expert.rubric), (
            f"{expert.id} has no human sign-off item — nothing would require acceptance"
        )
        assert any(item.is_blocker for item in expert.rubric)


def test_every_expert_has_a_registered_runner(registry):
    from cn_social_agent.tasks.runners import RUNNERS

    for expert in registry.all():
        assert expert.runner in RUNNERS, f"{expert.id} references unknown runner"


def test_auto_gates_all_resolve(registry):
    from cn_social_agent.tasks.gates import GATES

    for expert in registry.all():
        for item in expert.rubric:
            if item.kind == "auto":
                assert item.rule in GATES, f"{expert.id}.{item.id} -> unknown gate {item.rule}"


def test_experts_are_bilingual(registry):
    for expert in registry.all():
        zh = expert.to_dict("zh-CN")
        en = expert.to_dict("en-US")
        assert zh["name"] and en["name"]
        assert zh["name"] != en["name"], f"{expert.id} name not localised"
        assert len(zh["rubric"]) == len(en["rubric"])


def test_ids_are_unique_and_stable(registry):
    ids = [e.id for e in registry.all()]
    assert len(ids) == len(set(ids))
    for expert in registry.all():
        assert registry.get(expert.id) is expert


def test_unknown_expert_raises(registry):
    with pytest.raises(KeyError):
        registry.require("nope")


def test_bad_pack_is_reported_not_fatal(tmp_path):
    (tmp_path / "broken.yaml").write_text("id: broken\nrubric:\n  - id: x\n", encoding="utf-8")
    reg = ExpertRegistry([tmp_path]).scan()
    # A rubric item without a rule for an auto kind must be rejected loudly.
    assert reg.errors
    assert "broken" not in reg.ids()


def test_pick_handles_missing_and_plain_strings():
    assert pick({"zh-CN": "中文", "en-US": "English"}, "en-US") == "English"
    assert pick({"zh-CN": "中文"}, "en-US") == "中文"
    assert pick(None, "zh-CN") == ""
    assert pick("纯文本", "en-US") == "纯文本"


def test_rubric_item_validates_kind_and_severity():
    with pytest.raises(ValueError):
        RubricItem(id="x", title="t", kind="magic")
    with pytest.raises(ValueError):
        RubricItem(id="x", title="t", severity="critical")
    with pytest.raises(ValueError, match="require a rule"):
        RubricItem(id="x", title="t", kind="auto")


def test_search_dirs_include_project_overrides():
    dirs = default_search_dirs()
    assert any(d.name == "experts" for d in dirs)
