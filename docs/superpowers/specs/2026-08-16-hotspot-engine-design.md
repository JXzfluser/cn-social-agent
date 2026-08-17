# 热点选题引擎 v1（方案 2）

> Date: 2026-08-16  
> Status: Approved — 2026-08-16  
> Plan: `docs/superpowers/plans/2026-08-16-hotspot-engine.md`  
> Approach: **方案 2** — 选题引擎 v1（A 质量 + B 源覆盖 + C 闭环交接）  
> Related: `src/cn_social_agent/tools/hotspots.py`、`api/hotspots_routes.py`、Workbench Agent 热点抽屉

## 1. Goal

把 Agent 热点从「多源榜单 + 开聊 starter」升级为 **可打分、可过滤、可交接** 的选题引擎：

**扫榜 → 统一打分/去重/资产碰撞 → 领域过滤 → 研究并交接（口播 / 讲解 / 期刊）**

成功标准：

1. 每条热点有 `why`（为何值得做）+ `topic_key`；已做过的主题可见「本地已有资产」
2. 可按源 / 领域过滤；至少 **1 个稳定中文源**
3. 一点「研究并交接」能进入对应工坊，并带上 `research_notes`

## 2. Locked decisions

| Item | Choice |
|------|--------|
| Scope | A + B + C（不做 D 日报主动推送） |
| Scoring | 规则归一化热度 + 轻量启发式 why（v1 不强制 LLM 打分） |
| 中文源 | 公开 RSS / 稳定 JSON API（先 1～2 个）；**不做**微博/抖音非官方爬虫 |
| 闭环 | UI 主按钮 + 可选 Agent tool `handoff_hotspot`；复用现有 `propose_*` / draft |
| 资产碰撞 | 复用 `lookup_topic_assets` / `topic_key` |
| InsForge LLM | 本规格不切换 Agent LLM |

## 3. Non-goals (v1)

- Agent 定时扫榜 / 每日推送（D）
- 微博、抖音、小红书非官方抓取
- 完整舆情图谱 / 向量检索
- 跨用户热点订阅 feed
- 改 InsForge vendor 本体

## 4. Current baseline

| Layer | Today |
|-------|--------|
| 源 | GitHub / HN / Lobsters / V2EX / Dev.to |
| API | `GET /api/hotspots` → `tool_scan_hotspot_board` |
| UI | Agent 抽屉 chips：洞察 / 短视频 / 知识卡 starter 文案 |
| 缺口 | 无跨源统一分；无 why；无资产碰撞；无领域过滤；中文源仅 V2EX；闭环靠用户再聊一轮 |

## 5. Architecture

```text
Workbench UI (热点抽屉)
    │  GET /api/hotspots?source=&domain=&per_page=
    ▼
hotspots.scan (增强)
    ├─ fetch sources (existing + new CN RSS)
    ├─ normalize → HotItem
    ├─ score + dedupe(topic_key)
    ├─ enrich why + local_assets (lookup)
    └─ filter by domain
    ▼
board[] + handoff actions

「研究并交接」
    │  POST /api/hotspots/handoff  或  chat starter 触发 Agent
    ▼
research_notes 短摘 → propose_short_video | propose_presentation | propose_knowledge_cards
```

## 6. Data model

### 6.1 HotItem（board 元素扩展）

| Field | Type | Notes |
|-------|------|--------|
| `rank` | int | 展示序（按 score 降序） |
| `source` / `source_label` | str | 来源 |
| `title` / `full_name` | str | 标题（兼容现字段 `full_name`） |
| `url` | str | 原文链接 |
| `description` | str | ≤160 字 |
| `raw_score` | number | 源原始热度（stars/points/replies…） |
| `score` | float | **0–100** 归一化综合分 |
| `topic_key` | str | `knowledge.topic_key.topic_key(title)` |
| `domains` | string[] | 如 `ai` / `devtools` / `product` / `hiring` / `general` |
| `why` | str | ≤48 字：为何值得做成内容 |
| `freshness` | str | `hot` \| `rising` \| `steady`（启发式） |
| `local_assets` | object\|null | `{ journal_count, video_count, hint }` 碰撞结果 |
| `starters` | array | 保留现有 insight/intro/cards |
| `handoff` | object | `{ default_track, research_seed }` |

兼容：保留 `headline`、`stars`（可等于 raw_score）、`default_message`，避免旧 UI 断裂。

### 6.2 打分（v1 规则）

对每个源把 `raw_score` 映射到 0–100（对数或分位截断），再：

```text
score = 0.55 * heat_norm
      + 0.25 * freshness_bonus   # 近 7 天 / front_page 等
      + 0.20 * fit_bonus         # 命中领域词典；无则 50 中性
```

同 `topic_key`：**保留 score 最高的一条**，`sources_merged` 可选列出其它源。

`why` 模板（无 LLM）：

- GitHub：`近创高星 · {lang} · 适合讲「是什么+谁该用」`
- HN/Lobsters：`社区热议 · 适合观点/对比角`
- V2EX/中文 RSS：`中文讨论热 · 适合本地受众口播`
- 若 `local_assets` 有期刊/视频：`why` 后缀 `· 本地已有资产，可续做或换角`

### 6.3 领域（domain）

| id | 匹配启发（标题/描述/tag） |
|----|---------------------------|
| `ai` | AI, LLM, Agent, GPT, 模型, 智能体… |
| `devtools` | CLI, SDK, IDE, 框架, Git, Docker… |
| `product` | Product, SaaS, 增长, UX, 独立开发… |
| `hiring` | 招聘, JD, 面试, 岗位… |
| `general` | 未命中其它 |

过滤：`domain=ai` 时只返回 `domains` 含 ai 的项；`all` 不过滤。

## 7. Sources (B)

### 7.1 Keep

GitHub rising、HN front_page、Lobsters hottest、V2EX hot、Dev.to top=7。

### 7.2 Add (v1)

| id | 类型 | 说明 |
|----|------|------|
| `sspai` | RSS | 少数派（或同等稳定中文科技 RSS）— **首选中文源** |
| `ph` | API/RSS | Product Hunt 今日（若官方/稳定 feed 可用；否则延后，不阻塞 sspai） |

实现要求：超时短、失败进 `errors[]`、不拖垮整榜。  
配置：允许 env `HOTSPOT_CN_RSS_URL` 覆盖默认少数派 feed，便于换源。

## 8. API

### 8.1 `GET /api/hotspots`（扩展 query）

| Query | Default | Notes |
|-------|---------|--------|
| `source` | `all` | 含新源 id |
| `domain` | `all` | 新增 |
| `per_page` | `8` | 聚合后截断 |
| `days` / `min_stars` / `language` | 同现网 | 仅 GitHub |

Response 增加：`domains` 可用列表、每条 HotItem 扩展字段、`scored: true`。

### 8.2 `POST /api/hotspots/handoff`（新增）

Body：

```json
{
  "title": "...",
  "url": "...",
  "source": "hn",
  "why": "...",
  "topic_key": "...",
  "track": "koubo|presentation|journal",
  "research_notes": "可选；若空则服务端用 url 拉短摘"
}
```

行为：

1. 若无 `research_notes`：对 url 做短摘（复用 `fetch_url_text` / 现有抓取，截断 ≤2k）
2. 拼 `research_notes` = why + 短摘 + 来源感
3. 按 `track` 返回与现网交接卡同构的 payload：
   - `koubo` → 等同 `propose_short_video` 字段
   - `presentation` → 等同 `propose_presentation`（可 `auto_draft` 提示）
   - `journal` → 等同 `propose_knowledge_cards` / 打开卡片工坊所需字段
4. **不**在 handoff 内直接长跑 LLM 深度起草（讲解深度起草仍由工坊 `draft` 触发），以免 API 超时

### 8.3 Agent tool

- 增强 `scan_hotspot_board`：同 API 字段；参数加 `domain`
- 新增 `handoff_hotspot`（可选，与 POST 同逻辑）：方便对话内交接

## 9. UI（Workbench Agent 抽屉）

1. 源 tabs：保留 + 新源；增加 **领域** 下拉（全部 / AI / 开发工具 / 产品 / 招聘）
2. Chip 展示：`headline`、`why`（一行）、若有资产则小标签「已有期刊/视频」
3. 操作：
   - 主按钮：**研究并交接** → 弹出轨三选一 → 调 handoff → 打开对应模式（复用现有 `openPresentationFromAgent` / 短视频 / 卡片交接）
   - 次按钮：保留「洞察研究」纯开聊
4. 加载失败：单源错误只显示在 meta，不整页空白

## 10. Implementation slices

| Slice | Deliverable |
|-------|-------------|
| **S1** | HotItem 打分 / topic_key / why / 去重；API+UI 展示 why |
| **S2** | `local_assets` 碰撞；领域过滤 UI+API |
| **S3** | 中文 RSS 源（sspai 或可配置） |
| **S4** | `POST /api/hotspots/handoff` + 抽屉「研究并交接」三轨 |

建议顺序：S1 → S2 → S3 → S4。每刀可独立验收。

## 11. Testing

- 单元：score 归一化、topic_key 去重、domain 标签、RSS 解析（fixture）
- API：`/api/hotspots?domain=ai` 返回结构；handoff 缺 url 时 400
- 手工：抽屉看到 why + 资产标；交接进讲解/口播/期刊且带 notes

## 12. Risks

| Risk | Mitigation |
|------|------------|
| 中文源不稳定 | env 可换 RSS；失败不阻断其它源 |
| 抓取超时拖慢榜 | 源并行 + 单源 timeout≤8–15s |
| why 模板空洞 | 绑定源类型 + 资产碰撞后缀；S2 后可再加 LLM 润色（非本 v1） |
| handoff 与 Agent 双路径不一致 | 共用同一 Python handoff 函数 |

## 13. Out of scope follow-ups

- D：定时热点日报
- LLM 生成个性化 why
- Product Hunt 若无稳定源则单列下一期
- 热点结果写入 InsForge 表做历史榜
