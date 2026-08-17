# 知识卡片 · 多平台贴图发布（公众号 / 今日头条）

> Date: 2026-08-09  
> Status: Draft for review  
> Approach: **方案 2** — 统一发布层 + 分阶段接入（公众号先真发，头条同接口后接）

## 背景与目标

知识卡片在工作台「扫描并生成」后，用户需要把成片贴图发到：

- **微信公众号**：贴图方式；**标题 = 卡片 tags**（多个用 ` · ` 拼接）
- **今日头条**：同样多图贴图；标题规则同公众号（封面 title / tags）

同时需要：

- 发布前 **扫码 / OAuth 授权** 账号
- 扫描成功后出现 **「发布」按钮**，勾选平台再确认（非全自动）
- 默认进 **草稿**；可选勾选 **直接发布**

## 非目标（本期）

- 图文长文排版（富文本群发文章）作为主路径（可贴图为主）
- 企业微信 / 钉钉 / 飞书
- 定时发布日历、多账号矩阵运营后台
- 用非官方 Cookie 爬虫发头条（仅官方开放能力；不足时显式降级）

## 用户流程

```text
扫描并生成成功
  → 预览区 / 操作条出现「发布到平台」
  → 打开发布面板
       · 勾选：微信公众号、今日头条
       · 勾选：直接发布（默认关）
       · 展示标题预览（来自 tags）与将上传的图片张数
  → 某平台未授权 →「扫码授权」→ 回调写入 token → 状态变已授权
  → 确认发布
       · 服务端导出/使用已有 PNG（封面 + 各知识点）
       · 按平台 Adapter：上传图片 → 创建草稿 或 直接发布
  → 面板展示每平台结果（成功链接 / 草稿提示 / 失败原因）
  → 写入卡片历史 publish 字段，可回看
```

## 架构

```text
cards_workshop.js (Publish modal)
        │
        ▼
POST /api/cards/publish
        │
        ▼
cards/publish/service.py
  · resolve title from tags
  · ensure images (export or cached)
  · for each selected platform → Publisher.publish(...)
        │
        ├── platforms/weixin/publisher.py   (v1 真接)
        └── platforms/toutiao/publisher.py  (v1 接口齐，能力不足则 NotConfigured)

POST /api/oauth/{platform}/authorize  → 跳转 / 返回扫码 URL
GET  /api/oauth/{platform}/callback   → 换 token，按 user 持久化
GET  /api/oauth/{platform}/status     → 是否已授权、账号名
DELETE /api/oauth/{platform}          → 解除绑定
```

### Publisher 接口（统一）

```python
class PublishResult(TypedDict):
    platform: str          # weixin | toutiao
    status: str            # draft | published | failed | skipped
    external_id: str       # 草稿/内容 id
    url: str               # 可打开链接（可空）
    message: str           # 人类可读说明

class PlatformPublisher(Protocol):
    def auth_url(self, *, user_id: str, redirect_uri: str) -> str: ...
    async def handle_callback(self, *, user_id: str, query: dict) -> None: ...
    async def status(self, *, user_id: str) -> dict: ...
    async def publish(
        self,
        *,
        user_id: str,
        title: str,
        image_paths: list[Path],
        direct: bool,
        meta: dict,
    ) -> PublishResult: ...
```

## 标题与素材规则

| 项 | 规则 |
|----|------|
| 标题 | 优先 `cover.tags` 用 ` · ` 拼接；若无 tags 则用 `cover.title`；超长按平台限制截断（公众号建议 ≤64 字） |
| 图片 | 顺序：封面 → 知识点 1..N；来源优先本次导出 PNG（与现有 html-to-image 一致），缓存于 `data/cards/exports/{history_id}/` |
| 直接发布 | `direct=false` → 草稿；`direct=true` → 尝试正式发布，账号无权限则 **回退草稿** 并在 `message` 说明 |

## 微信公众号（v1）

- 凭证：`WEIXIN_APP_ID` / `WEIXIN_APP_SECRET`（已有 env 占位）；可选用户级覆盖存 secrets
- 能力：
  1. `access_token` 缓存
  2. 上传图文/图片素材（临时或永久，按贴图场景选临时 + 草稿引用）
  3. 草稿箱创建（多图贴图结构以微信当前「草稿 / 发表」API 为准实现）
  4. 若勾选直接发布：调用发表接口；失败则保留草稿
- 授权：优先公众号服务端凭证（同一主体配置）；若需用户扫码授权第三方平台，走微信开放平台授权页，callback 存 authorizer refresh_token
- **说明**：订阅号/服务号能力差异大，UI 需展示当前账号类型与能力探测结果

## 今日头条（v1 接口 + 分阶段实现）

- 凭证：`TOUTIAO_APP_ID` / `TOUTIAO_APP_SECRET` / 回调 URL（新增 `.env.example`）
- Adapter **先实现完整接口**；若开放平台无「多图发帖」权限：
  - `status().ready == false`
  - `publish` 返回 `skipped` + 明确文案（不阻断公众号）
- 授权：OAuth 扫码 / 跳转，callback 存 token
- v1.1：权限开通后填充真实 `upload_images` / `create_draft` / `publish`

## 数据与安全

- Token：按 `user_id`（及 email）存 `data/oauth/{platform}/{owner}.json` 或 InsForge secrets；**禁止**下发到前端明文
- 发布记录：挂在卡片 history 项上：

```json
"publish": [
  {
    "platform": "weixin",
    "status": "draft",
    "at": "2026-08-09T08:00:00Z",
    "title": "Agent 编排 · RAG 工程",
    "external_id": "...",
    "url": "",
    "message": "已写入公众号草稿箱"
  }
]
```

- 所有 publish / oauth 路由 `@require_user`

## UI（工作台卡片模式）

- 扫描成功 note 旁 / sticky 操作区：`发布到平台`
- 历史条目：已发布平台小标签（草稿/已发/失败）
- 发布面板：
  - 平台勾选 + 授权状态灯
  - 标题预览（可编辑一次，仅本次）
  - 「直接发布」开关（默认关）
  - 进度：导出图 → 上传 → 提交
- 设置页或卡片顶栏：平台授权入口（与发布面板共用 status API）

## 分阶段交付

| 阶段 | 内容 |
|------|------|
| **P0** | Publisher 协议、OAuth status 骨架、发布面板 UI、导出图缓存、标题规则、`POST /api/cards/publish` mock 成功路径（本地无密钥可测） |
| **P1** | 微信：token、上传、草稿；授权配置文档；直接发布 + 回退草稿 |
| **P2** | 头条：OAuth + 真实发帖（视开放能力）；两端结果并写入 history |

## 测试

- 单元：标题拼接/截断、未授权拒绝、direct 回退草稿
- API：未登录 401；mock publisher 双平台勾选返回两条结果
- 手工：配置微信测试号 / 正式号走通草稿

## 风险

- 微信「贴图」具体 API 形态随账号类型变化 → 实现时以当前微信文档为准，必要时降级为「多图素材 + 草稿图文」
- 头条开放能力不确定 → 必须允许单平台成功
- 导出图耗时 → 发布前复用已有导出或异步任务（P1 可先同步，超时提示重试）

## 与现有文档关系

- 更新 `2026-08-09-knowledge-cards-design.md`：原「公众号草稿后续可加」改为指向本文
- 不恢复已删除的旧 `social.publisher` 包名；新模块放 `cn_social_agent/platforms/`
