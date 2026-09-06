"""Idea Engine persistence mirror + content project bridge tests."""

from __future__ import annotations

import pytest

from cn_social_agent.idea_engine.connectors.base import RawMaterial
from cn_social_agent.idea_engine.processor import IdeaCard


class FakeDB:
    """Minimal InsForge db stand-in (query/create/update)."""

    def __init__(self):
        self.tables: dict[str, dict[str, dict]] = {}

    async def create(self, table: str, row: dict) -> None:
        rows = self.tables.setdefault(table, {})
        rid = str(row.get("id") or "")
        if rid in rows:
            raise RuntimeError("duplicate id")
        rows[rid] = dict(row)

    async def query(self, table: str, filters: dict | None = None, limit: int = 100):
        rows = self.tables.get(table, {})
        out = []
        for row in rows.values():
            ok = True
            for k, v in (filters or {}).items():
                if not str(v).startswith("eq."):
                    continue
                if str(row.get(k)) != str(v)[3:]:
                    ok = False
                    break
            if ok:
                out.append(dict(row))
            if len(out) >= max(1, limit):
                break
        return out

    async def update(self, table: str, filters: dict, row: dict) -> None:
        rows = self.tables.setdefault(table, {})
        for k, v in filters.items():
            if k == "id" and str(v).startswith("eq."):
                rid = str(v)[3:]
                if rid in rows:
                    rows[rid].update(row)
                return


@pytest.fixture
def fake_db(monkeypatch):
    from cn_social_agent.idea_engine import cloud as idea_cloud

    db = FakeDB()
    idea_cloud.set_idea_db(db)
    yield db
    idea_cloud.set_idea_db(None)


def _material(mid: str = "gh:foo/bar", **kw) -> RawMaterial:
    defaults = dict(
        id=mid,
        connector_id="github_trending",
        source="github",
        title="Foo Bar 框架",
        url="https://github.com/foo/bar",
        summary="一个示例项目",
        tags=["python", "llm"],
        heat=1200,
    )
    defaults.update(kw)
    return RawMaterial(**defaults)


def _card(mid: str = "u1", **kw) -> IdeaCard:
    defaults = dict(
        id="card:gh:foo/bar:u1",
        material_id="gh:foo/bar",
        user_id=mid,
        title="Foo Bar 上手",
        hook="为什么值得试",
        angles=["入门", "对比"],
        heat_score=90,
        difficulty_score=40,
        content_type="technical",
    )
    defaults.update(kw)
    return IdeaCard(**defaults)


@pytest.mark.asyncio
async def test_material_and_card_mirror_roundtrip(fake_db):
    from cn_social_agent.idea_engine import cloud as idea_cloud

    m = _material()
    c = _card()
    assert await idea_cloud.upsert_material(m, "u1") is True
    assert await idea_cloud.upsert_card(c) is True

    materials = await idea_cloud.load_materials("u1")
    cards = await idea_cloud.load_cards("u1")
    assert len(materials) == 1 and materials[0].id == m.id
    assert materials[0].title == m.title
    assert materials[0].tags == ["python", "llm"]
    assert len(cards) == 1 and cards[0].id == c.id
    assert cards[0].status == "pending"


@pytest.mark.asyncio
async def test_upsert_card_updates_in_place(fake_db):
    from cn_social_agent.idea_engine import cloud as idea_cloud

    c = _card()
    await idea_cloud.upsert_card(c)
    c.status = "selected"
    c.feedback = "good"
    await idea_cloud.upsert_card(c)

    cards = await idea_cloud.load_cards("u1")
    assert len(cards) == 1
    assert cards[0].status == "selected"
    assert cards[0].feedback == "good"


@pytest.mark.asyncio
async def test_patch_card_updates_status(fake_db):
    from cn_social_agent.idea_engine import cloud as idea_cloud

    await idea_cloud.upsert_card(_card())
    assert await idea_cloud.patch_card("card:gh:foo/bar:u1", {"project_id": "cp_1"}) is True
    cards = await idea_cloud.load_cards("u1")
    assert cards[0].project_id == "cp_1"


@pytest.mark.asyncio
async def test_engine_hydrates_and_dedupes(fake_db):
    from cn_social_agent.idea_engine import cloud as idea_cloud
    from cn_social_agent.idea_engine.engine import IdeaEngine

    await idea_cloud.upsert_material(_material(), "u1")
    await idea_cloud.upsert_card(_card())

    engine = IdeaEngine()
    await engine.ensure_loaded("u1")
    assert len(engine.materials["u1"]) == 1
    assert len(engine.cards["u1"]) == 1

    # Hydration is once-per-process; a second call must not dupe
    await engine.ensure_loaded("u1")
    assert len(engine.materials["u1"]) == 1
    assert len(engine.cards["u1"]) == 1

    # A fresh engine hydrating the same mirror sees exactly one of each
    engine2 = IdeaEngine()
    await engine2.ensure_loaded("u1")
    assert len(engine2.materials["u1"]) == 1
    assert len(engine2.cards["u1"]) == 1


@pytest.mark.asyncio
async def test_engine_mirror_write_through(fake_db, monkeypatch):
    from cn_social_agent.idea_engine import cloud as idea_cloud
    from cn_social_agent.idea_engine.engine import IdeaEngine

    engine = IdeaEngine()

    class FakeConnector:
        id = "github_trending"

        async def fetch(self):
            return [_material()]

    monkeypatch.setattr(
        "cn_social_agent.idea_engine.connectors.manager.get_or_create",
        lambda *a, **k: FakeConnector(),
    )
    got = await engine.fetch_single_connector("u1", "github_trending")
    assert len(got) == 1
    assert len(fake_db.tables.get(idea_cloud.MATERIALS_TABLE, {})) == 1

    # Restart simulation: fresh engine hydrates the mirror
    engine2 = IdeaEngine()
    await engine2.ensure_loaded("u1")
    assert len(engine2.materials["u1"]) == 1


@pytest.mark.asyncio
async def test_select_and_project_writeback(fake_db):
    from cn_social_agent.idea_engine import cloud as idea_cloud
    from cn_social_agent.idea_engine.engine import IdeaEngine

    await idea_cloud.upsert_card(_card())
    engine = IdeaEngine()
    result = await engine.select_card("u1", "card:gh:foo/bar:u1")
    assert result and result["title"] == "Foo Bar 上手"
    await engine.set_card_project("u1", "card:gh:foo/bar:u1", "cp_idea_1")

    assert engine.cards["u1"][0].project_id == "cp_idea_1"
    cards = await idea_cloud.load_cards("u1")
    assert cards[0].project_id == "cp_idea_1"
    assert cards[0].status == "selected"


@pytest.mark.asyncio
async def test_project_bridge_empty_title_returns_none():
    from cn_social_agent.idea_engine.project_bridge import ContentProjectStore

    proj = await ContentProjectStore().create("u1", {"title": "  "})
    assert proj is None
