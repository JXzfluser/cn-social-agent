# 知识卡片多平台贴图发布 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扫描生成成功后，用户可勾选微信公众号 / 今日头条，经扫码授权后以贴图方式发布（标题=tags，默认草稿、可选直发）；统一 Publisher 层，公众号 P1 真接，头条同接口可跳过。

**Architecture:** `platforms/` 下各平台实现同一 Protocol；`cards/publish/` 负责标题规则、导出图缓存、编排多平台发布并写回 history；`/api/oauth/*` 与 `/api/cards/publish` 挂到现有 aiohttp workbench；前端在 `cards_workshop.js` 增加发布面板。

**Tech Stack:** aiohttp、httpx、现有 `cards/history.py`、html-to-image（前端导出后上传）、env 凭证。

**Spec:** [`docs/superpowers/specs/2026-08-09-card-platform-publish-design.md`](../specs/2026-08-09-card-platform-publish-design.md)

---

## File map

| File | Responsibility |
|------|----------------|
| `src/cn_social_agent/platforms/__init__.py` | 注册表 `get_publisher(name)` |
| `src/cn_social_agent/platforms/base.py` | `PublishResult` TypedDict + `PlatformPublisher` Protocol |
| `src/cn_social_agent/platforms/tokens.py` | 按 owner 读写 `data/oauth/{platform}/{owner}.json` |
| `src/cn_social_agent/platforms/weixin/publisher.py` | 微信：token / 上传 / 草稿 / 发表（P1） |
| `src/cn_social_agent/platforms/toutiao/publisher.py` | 头条：接口齐全，未配置则 skipped |
| `src/cn_social_agent/platforms/mock.py` | 无密钥时本地可测的 MockPublisher |
| `src/cn_social_agent/cards/publish/title.py` | tags → 标题拼接与截断 |
| `src/cn_social_agent/cards/publish/images.py` | 导出目录、接收上传 PNG、路径校验 |
| `src/cn_social_agent/cards/publish/service.py` | `publish_card(...)` 编排 |
| `src/cn_social_agent/cards/history.py` | `append_publish_record(...)` |
| `src/cn_social_agent/api/oauth_routes.py` | authorize / callback / status / unbind |
| `src/cn_social_agent/api/card_routes.py` | `POST /api/cards/publish`、`POST /api/cards/export-images` |
| `src/cn_social_agent/api/app.py` | `setup_oauth_routes` |
| `.env.example` | `TOUTIAO_*`、`OAUTH_PUBLIC_BASE` |
| `src/cn_social_agent/workbench/index.html` | 发布按钮 + modal DOM/CSS |
| `src/cn_social_agent/workbench/cards_workshop.js` | 发布面板逻辑 |
| `tests/workbench/test_card_publish.py` | 标题、编排、API |
| `tests/workbench/test_platform_tokens.py` | token 存取 |

---

## Phase P0 — 协议 + Mock 发布 + UI 面板

### Task 1: Publisher 协议与注册表

**Files:**
- Create: `src/cn_social_agent/platforms/base.py`
- Create: `src/cn_social_agent/platforms/__init__.py`
- Create: `src/cn_social_agent/platforms/mock.py`
- Create: `tests/workbench/test_card_publish.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/workbench/test_card_publish.py
import pytest
from pathlib import Path

def test_get_publisher_mock():
    from cn_social_agent.platforms import get_publisher
    p = get_publisher("mock")
    assert p is not None

@pytest.mark.asyncio
async def test_mock_publish_draft(tmp_path):
    from cn_social_agent.platforms import get_publisher
    img = tmp_path / "c.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    pub = get_publisher("mock")
    r = await pub.publish(
        user_id="u1",
        title="A · B",
        image_paths=[img],
        direct=False,
        meta={},
    )
    assert r["platform"] == "mock"
    assert r["status"] == "draft"
    assert r["external_id"]
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=src .venv/bin/pytest tests/workbench/test_card_publish.py::test_get_publisher_mock -v`  
Expected: FAIL import / not found

- [ ] **Step 3: 实现 base + mock + registry**

```python
# platforms/base.py
from pathlib import Path
from typing import Any, Protocol, TypedDict

class PublishResult(TypedDict):
    platform: str
    status: str  # draft | published | failed | skipped
    external_id: str
    url: str
    message: str

class PlatformPublisher(Protocol):
    name: str
    def auth_url(self, *, user_id: str, redirect_uri: str, state: str = "") -> str: ...
    async def handle_callback(self, *, user_id: str, query: dict[str, str]) -> dict[str, Any]: ...
    async def status(self, *, user_id: str) -> dict[str, Any]: ...
    async def publish(
        self,
        *,
        user_id: str,
        title: str,
        image_paths: list[Path],
        direct: bool,
        meta: dict[str, Any],
    ) -> PublishResult: ...
```

```python
# platforms/mock.py
import time
import uuid
from pathlib import Path
from typing import Any
from cn_social_agent.platforms.base import PublishResult

class MockPublisher:
    name = "mock"
    def auth_url(self, *, user_id: str, redirect_uri: str, state: str = "") -> str:
        return f"{redirect_uri}?code=mock&state={state}&user_id={user_id}"
    async def handle_callback(self, *, user_id: str, query: dict[str, str]) -> dict[str, Any]:
        return {"ok": True, "account": "mock-account"}
    async def status(self, *, user_id: str) -> dict[str, Any]:
        return {"platform": "mock", "ready": True, "authorized": True, "account": "mock-account"}
    async def publish(self, *, user_id: str, title: str, image_paths: list[Path], direct: bool, meta: dict[str, Any]) -> PublishResult:
        eid = f"mock_{uuid.uuid4().hex[:8]}"
        return {
            "platform": "mock",
            "status": "published" if direct else "draft",
            "external_id": eid,
            "url": "",
            "message": f"mock {'published' if direct else 'draft'} · {len(image_paths)} images · {title}",
        }
```

```python
# platforms/__init__.py
from cn_social_agent.platforms.mock import MockPublisher

_REGISTRY = {"mock": MockPublisher}

def get_publisher(name: str):
    key = (name or "").strip().lower()
    cls = _REGISTRY.get(key)
    if not cls:
        raise KeyError(f"unknown platform: {name}")
    return cls()

def list_platforms() -> list[str]:
    return sorted(_REGISTRY.keys())

def register_publisher(name: str, cls: type) -> None:
    _REGISTRY[name] = cls
```

- [ ] **Step 4: 跑测通过**

Run: `PYTHONPATH=src .venv/bin/pytest tests/workbench/test_card_publish.py -v`  
Expected: PASS

- [ ] **Step 5: Commit（若用户要求再提交）**

```bash
git add src/cn_social_agent/platforms tests/workbench/test_card_publish.py
git commit -m "feat(platforms): add publisher protocol and mock adapter"
```

---

### Task 2: 标题规则

**Files:**
- Create: `src/cn_social_agent/cards/publish/__init__.py`
- Create: `src/cn_social_agent/cards/publish/title.py`
- Modify: `tests/workbench/test_card_publish.py`

- [ ] **Step 1: 写失败测试**

```python
def test_resolve_publish_title_from_tags():
    from cn_social_agent.cards.publish.title import resolve_publish_title
    assert resolve_publish_title({"tags": ["Agent", "RAG"], "title": "X"}) == "Agent · RAG"

def test_resolve_publish_title_fallback_and_clip():
    from cn_social_agent.cards.publish.title import resolve_publish_title
    assert resolve_publish_title({"tags": [], "title": "仅标题"}) == "仅标题"
    long_tags = ["很长标签名"] * 20
    t = resolve_publish_title({"tags": long_tags, "title": "X"}, max_len=20)
    assert len(t) <= 20
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONPATH=src .venv/bin/pytest tests/workbench/test_card_publish.py::test_resolve_publish_title_from_tags -v`

- [ ] **Step 3: 实现**

```python
# cards/publish/title.py
from __future__ import annotations
from typing import Any

def resolve_publish_title(cover: dict[str, Any] | None, *, max_len: int = 64) -> str:
    cover = cover or {}
    tags = cover.get("tags") if isinstance(cover.get("tags"), list) else []
    parts = [str(t).strip() for t in tags if str(t).strip()]
    title = " · ".join(parts) if parts else str(cover.get("title") or "").strip()
    title = title or "知识卡片"
    if len(title) <= max_len:
        return title
    return title[: max(0, max_len - 1)].rstrip(" ·") + "…"
```

- [ ] **Step 4: 跑测通过**

---

### Task 3: Token 存储 + OAuth owner key

**Files:**
- Create: `src/cn_social_agent/platforms/tokens.py`
- Create: `tests/workbench/test_platform_tokens.py`

- [ ] **Step 1: 写失败测试**

```python
def test_token_roundtrip(tmp_path, monkeypatch):
    import cn_social_agent.platforms.tokens as tok
    monkeypatch.setattr(tok, "oauth_dir", lambda: tmp_path)
    tok.save_token("weixin", "e_demo", {"access_token": "a", "account": "acc"})
    data = tok.load_token("weixin", "e_demo")
    assert data["access_token"] == "a"
    tok.clear_token("weixin", "e_demo")
    assert tok.load_token("weixin", "e_demo") is None
```

- [ ] **Step 2: 实现**

```python
# platforms/tokens.py
import json
import re
from pathlib import Path
from typing import Any, Optional

def oauth_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "data" / "oauth"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _safe(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_@.+-]+", "_", (s or "").strip())[:96] or "anon"

def token_path(platform: str, owner: str) -> Path:
    p = oauth_dir() / _safe(platform)
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{_safe(owner)}.json"

def save_token(platform: str, owner: str, data: dict[str, Any]) -> None:
    token_path(platform, owner).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_token(platform: str, owner: str) -> Optional[dict[str, Any]]:
    path = token_path(platform, owner)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None

def clear_token(platform: str, owner: str) -> bool:
    path = token_path(platform, owner)
    if path.is_file():
        path.unlink()
        return True
    return False
```

复用 `cards.history.history_owner_key` 作为 owner（email 优先）。

- [ ] **Step 3: 跑测通过**

---

### Task 4: 导出图目录 + publish service（Mock）

**Files:**
- Create: `src/cn_social_agent/cards/publish/images.py`
- Create: `src/cn_social_agent/cards/publish/service.py`
- Modify: `src/cn_social_agent/cards/history.py` — 增加 `append_publish_record`
- Modify: `tests/workbench/test_card_publish.py`

- [ ] **Step 1: 写失败测试**

```python
def test_publish_card_with_mock(tmp_path, monkeypatch):
    import cn_social_agent.cards.history as hist
    import cn_social_agent.cards.publish.images as imgs
    monkeypatch.setattr(hist, "history_dir", lambda: tmp_path)
    monkeypatch.setattr(imgs, "exports_dir", lambda: tmp_path / "exports")
    from cn_social_agent.cards.history import save_history_record
    rec = save_history_record(
        {
            "cover": {"title": "T", "tags": ["A", "B"]},
            "knowledge": [{"topicTitle": "k1"}],
            "mode": "ai",
        },
        email="demo@local.test",
        user_id="u_demo_local",
    )
    exp = tmp_path / "exports" / rec["id"]
    exp.mkdir(parents=True)
    (exp / "00_cover.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (exp / "01_k0.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    import asyncio
    from cn_social_agent.cards.publish.service import publish_card
    out = asyncio.get_event_loop().run_until_complete(
        publish_card(
            history_id=rec["id"],
            platforms=["mock"],
            direct=False,
            title_override="",
            user_id="u_demo_local",
            email="demo@local.test",
        )
    )
    assert out["results"][0]["status"] == "draft"
    assert out["title"] == "A · B"
```

- [ ] **Step 2: 实现 images + append_publish_record + service**

`exports_dir()` → `data/cards/exports`  
`list_export_images(history_id)` → 按文件名排序的 `*.png`  
`save_uploaded_images(history_id, files: list[tuple[str, bytes]])`

`append_publish_record(history_id, entry, *, user_id, email)`：load → 找到 id → `publish` list append → save

`publish_card`：
1. `get_history_item`
2. `resolve_publish_title(cover)` 或 override
3. `list_export_images`；若空 raise `RuntimeError("请先导出或上传卡片图片")`
4. 对每个 platform `get_publisher` → `publish`
5. 每条 `append_publish_record`
6. 返回 `{title, results: [...]}`

注册：`register_publisher("weixin", ...)` 暂不在本任务；P0 仅 mock。生产路由默认 platforms 映射：无密钥时 weixin/toutiao 也可指向可 skipped 实现。

- [ ] **Step 3: 跑测通过**

---

### Task 5: API 路由 OAuth + publish

**Files:**
- Create: `src/cn_social_agent/api/oauth_routes.py`
- Modify: `src/cn_social_agent/api/card_routes.py`
- Modify: `src/cn_social_agent/api/app.py`
- Modify: `tests/workbench/test_knowledge_cards.py` 或 `test_card_publish.py`（aiohttp TestClient）

- [ ] **Step 1: 写 API 测试**

```python
@pytest.mark.asyncio
async def test_cards_publish_requires_auth(monkeypatch):
    from aiohttp.test_utils import TestClient, TestServer
    from cn_social_agent.api import create_app
    monkeypatch.setenv("WORKBENCH_STORE", "memory")
    monkeypatch.setenv("WORKBENCH_LLM", "mock")
    app = create_app()
    async with TestClient(TestServer(app)) as client:
        r = await client.post("/api/cards/publish", json={"history_id": "x", "platforms": ["mock"]})
        assert r.status == 401

@pytest.mark.asyncio
async def test_cards_publish_mock_ok(tmp_path, monkeypatch):
    # login demo → save history with export pngs → POST publish platforms=["mock"]
    ...
    assert body["results"][0]["platform"] == "mock"
```

- [ ] **Step 2: 实现路由**

`oauth_routes.py`：
- `GET /api/oauth/{platform}/status` → publisher.status
- `GET /api/oauth/{platform}/authorize?redirect=` → `{auth_url}`（mock 可直接给 callback URL）
- `GET /api/oauth/{platform}/callback` → handle_callback → 302 回 workbench `/?mode=card&oauth=ok`
- `DELETE /api/oauth/{platform}` → clear_token

`card_routes.py`：
- `POST /api/cards/publish` body: `{history_id, platforms: [], direct: bool, title?: str}`
- `POST /api/cards/export-images` multipart: `history_id` + `files[]`（前端导出后上传）

合法 platform 名：`weixin` | `toutiao` | `mock`（mock 仅 `WORKBENCH_LLM=mock` 或 `CARD_PUBLISH_ALLOW_MOCK=1` 时开放）

- [ ] **Step 3: `setup_oauth_routes(app)` 接入 `create_app`**

- [ ] **Step 4: 跑测通过**

---

### Task 6: 前端发布面板

**Files:**
- Modify: `src/cn_social_agent/workbench/index.html`（`#viewCard` sticky 区）
- Modify: `src/cn_social_agent/workbench/cards_workshop.js`

- [ ] **Step 1: HTML** — 在 `kcExportBtn` 旁加：

```html
<button class="ghost" id="kcPublishBtn" type="button" style="width:100%;margin-top:8px;" disabled>发布到平台</button>
```

Modal（可放在 `#viewCard` 末尾）：

```html
<dialog id="kcPublishDlg">
  <form method="dialog" id="kcPublishForm">
    <h3>发布到平台</h3>
    <label><input type="checkbox" name="plat" value="weixin" checked /> 微信公众号 <span id="kcAuthWx"></span></label>
    <label><input type="checkbox" name="plat" value="toutiao" /> 今日头条 <span id="kcAuthTt"></span></label>
    <label>标题 <input id="kcPublishTitle" class="field" /></label>
    <label><input type="checkbox" id="kcPublishDirect" /> 直接发布（默认草稿）</label>
    <p class="meta" id="kcPublishHint">将上传封面与知识点图片</p>
    <p class="status" id="kcPublishStatus"></p>
    <div class="actions">
      <button type="button" class="ghost" id="kcPublishAuthWx">授权公众号</button>
      <button type="button" class="ghost" id="kcPublishAuthTt">授权头条</button>
      <button value="cancel" class="ghost">取消</button>
      <button value="ok" class="primary" id="kcPublishConfirm">确认发布</button>
    </div>
  </form>
</dialog>
```

- [ ] **Step 2: JS 逻辑**

1. `scan` / `applyPayload` 成功且有 `state.activeHistoryId` → 启用 `kcPublishBtn`
2. 打开对话框：`resolve` 标题（tags join）、拉取 `/api/oauth/weixin/status` 与 toutiao
3. 授权按钮 → `GET /api/oauth/{p}/authorize` → `window.open(auth_url)` 或跳转
4. 确认发布：
   - 先若本地无导出缓存：调用现有 `exportAll` 逻辑但改为上传到 `/api/cards/export-images`（复用 html-to-image blob）
   - 再 `POST /api/cards/publish`
5. 展示 `results[].message`；刷新 history 列表上的 publish 小标签

- [ ] **Step 3: 手工** — 启动 workbench，mock 环境走通：生成 → 发布 mock → 历史出现草稿标记

---

## Phase P1 — 微信公众号真接

### Task 7: WeixinPublisher（token + 上传 + 草稿）

**Files:**
- Create: `src/cn_social_agent/platforms/weixin/__init__.py`
- Create: `src/cn_social_agent/platforms/weixin/publisher.py`
- Create: `src/cn_social_agent/platforms/weixin/api.py`（httpx 封装）
- Modify: `platforms/__init__.py` register `weixin`
- Modify: `.env.example` 确认 `WEIXIN_APP_ID` / `WEIXIN_APP_SECRET` / 增加 `WEIXIN_DRAFT_AUTHOR`（可选）
- Test: `tests/workbench/test_weixin_publisher.py`（httpx mock）

- [ ] **Step 1: 测试 access_token 缓存与缺配置 status.ready=false**

```python
def test_weixin_status_not_configured(monkeypatch):
    monkeypatch.delenv("WEIXIN_APP_ID", raising=False)
    from cn_social_agent.platforms.weixin.publisher import WeixinPublisher
    import asyncio
    st = asyncio.get_event_loop().run_until_complete(WeixinPublisher().status(user_id="u"))
    assert st["ready"] is False
```

- [ ] **Step 2: 实现**

- `GET https://api.weixin.qq.com/cgi-bin/token`
- 上传：`/cgi-bin/media/upload` 或草稿所需图片上传接口（以实现时微信文档为准）
- 草稿：`/cgi-bin/draft/add`；结构至少包含 title=tags 标题、多图 content 或图片消息字段
- `direct=True`：`freepublish` / 发表接口；失败则 status=draft + message 说明回退
- 无 AppID：`publish` → `skipped`（与头条一致，不抛死）

- [ ] **Step 3: 授权**

P1 默认 **服务号/公众号服务器配置凭证**（同一主体）：`status.authorized=True` 当 env 有密钥。  
扫码第三方平台授权可作为 P1.1：`auth_url` 指向开放平台，callback 存 authorizer token。

- [ ] **Step 4: 文档** — 在 design 旁短文或 README 小节：`docs/superpowers/specs/2026-08-09-card-platform-publish-weixin-setup.md`（AppID、IP 白名单、草稿权限）

---

## Phase P2 — 今日头条 Adapter

### Task 8: ToutiaoPublisher 骨架 + 注册

**Files:**
- Create: `src/cn_social_agent/platforms/toutiao/publisher.py`
- Modify: `.env.example` — `TOUTIAO_APP_ID=` `TOUTIAO_APP_SECRET=` `TOUTIAO_REDIRECT_URI=`
- Modify: `platforms/__init__.py`

- [ ] **Step 1: status** — 无密钥 `ready=False`；有密钥但未实现发帖 → `ready=False`, message=`头条发帖 API 待开通`
- [ ] **Step 2: publish** → 恒返回 `skipped` + 明确文案（直到真实 API）
- [ ] **Step 3: auth_url / callback** — 预留 OAuth 换 token 写入 `tokens.py`；无文档细节时 callback 存 placeholder 并返回 ok=false

---

### Task 9: 历史 UI 展示 publish 标记 + 回归

**Files:**
- Modify: `cards_workshop.js` `refreshHistory` — 若 `h.publish` 有项，显示小 pill（微信草稿 / 头条跳过等）
- Modify: `tests/workbench/test_knowledge_cards.py` — 既有用例仍绿
- Run: `PYTHONPATH=src .venv/bin/pytest tests/workbench/ -q`

---

## Spec coverage check

| Spec 项 | Task |
|---------|------|
| 扫描后发布按钮 / 勾选平台 | Task 6 |
| 扫码/OAuth | Task 5, 7, 8 |
| 贴图 + tags 标题 | Task 2, 4, 7 |
| 默认草稿 / 可选直发 | Task 4, 6, 7 |
| 统一 Publisher | Task 1 |
| 微信真接 | Task 7 |
| 头条同接口可 skipped | Task 8 |
| history.publish | Task 4, 9 |
| 导出图缓存 | Task 4, 6 |

## Placeholder scan

无 TBD；微信草稿具体 JSON 字段以实现时官方文档为准，Task 7 已写明降级路径。

---

## Execution

Plan 已保存。两种执行方式：

1. **Subagent-Driven（推荐）** — 每任务新开子代理，任务间复查  
2. **Inline Execution** — 本会话按任务连续做，设检查点  

回复选 **1** 或 **2** 即可开工。
