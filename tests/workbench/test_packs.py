"""Content pack loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cn_social_agent.packs.loader import (
    activate_pack,
    apply_pack_skills,
    effective_templates,
    get_active_pack,
    load_pack,
    load_pack_file,
    pack_video_defaults,
    resolve_pack_yaml,
    set_active_pack,
)
from cn_social_agent.skills.loader import Skill
from cn_social_agent.video.pipeline import VIDEO_TEMPLATES, list_video_styles


@pytest.fixture(autouse=True)
def _clear_pack():
    set_active_pack(None)
    yield
    set_active_pack(None)


def test_resolve_tech_saas_pack():
    path = resolve_pack_yaml("tech-saas")
    assert path is not None
    assert path.name == "pack.yaml"
    assert "tech-saas" in str(path)


def test_load_tech_saas_pack():
    pack = load_pack("tech-saas")
    assert pack is not None
    assert pack.id == "tech-saas"
    assert "short-video-director" in pack.skills_enabled
    assert pack.defaults["video"]["target_seconds"] == 15
    ids = {t["id"] for t in pack.templates}
    assert {"product_update", "tech_rant", "tutorial"} <= ids


def test_activate_and_list_styles():
    pack = activate_pack("tech-saas")
    assert get_active_pack() is pack
    styles = list_video_styles()
    assert styles["pack"]["id"] == "tech-saas"
    assert styles["default_seconds"] == 15
    assert styles["default_template_id"] == "product_update"
    tids = {t["id"] for t in styles["templates"]}
    assert "product_update" in tids


def test_effective_templates_override(tmp_path: Path):
    yaml_path = tmp_path / "pack.yaml"
    yaml_path.write_text(
        """
id: custom
templates:
  - id: product_update
    target_seconds: 30
    label: 自定义产品更新
defaults:
  video:
    target_seconds: 30
    default_template_id: product_update
""",
        encoding="utf-8",
    )
    pack = load_pack_file(yaml_path, pack_id="custom")
    set_active_pack(pack)
    catalog = effective_templates(VIDEO_TEMPLATES)
    assert catalog["product_update"]["target_seconds"] == 30
    assert catalog["product_update"]["label"] == "自定义产品更新"
    assert pack_video_defaults()["target_seconds"] == 30


def test_apply_pack_skills():
    class FakeLoader:
        def __init__(self):
            self._skills = {
                "short-video-director": Skill(
                    id="short-video-director",
                    name="d",
                    description="",
                    body="",
                    path="",
                    enabled=True,
                ),
                "tech-saas-content": Skill(
                    id="tech-saas-content",
                    name="t",
                    description="",
                    body="",
                    path="",
                    enabled=True,
                ),
                "demo-echo": Skill(
                    id="demo-echo",
                    name="e",
                    description="",
                    body="",
                    path="",
                    enabled=True,
                ),
            }

        def scan(self):
            return list(self._skills.values())

    pack = load_pack("tech-saas")
    assert pack is not None
    loader = FakeLoader()
    apply_pack_skills(loader, pack)
    assert loader._skills["short-video-director"].enabled is True
    assert loader._skills["tech-saas-content"].enabled is True
    # demo-echo is optional → left enabled
    assert loader._skills["demo-echo"].enabled is True


def test_pack_none(monkeypatch):
    monkeypatch.setenv("WORKBENCH_PACK", "none")
    assert load_pack() is None
