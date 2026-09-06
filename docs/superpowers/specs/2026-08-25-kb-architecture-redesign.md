# 知识库架构重设计方案

> ⚠️ **状态声明（2026-08-30 更新）：** 本文档涉及的学习 tab 已并入 Know-How 内容流，knowledge_base 范围调整为 Know-How 统一承载。当前主线见 `docs/superpowers/specs/2026-08-29-knowhow-system-design.md` 与 `docs/superpowers/plans/2026-08-30-knowhow-consolidation-migration.md`。**请勿据此文档进行新开发。**

> 日期：2026-08-25
> 状态：Draft
> 范围：agent-learning/knowledge_base + workbench 学习 tab + Agent 工具链

---

## 1. 现状问题

### 1.1 架构

```
数据源:
  topics/*/README.md  ─┐
  docs/*.md           ─┤→ gather_documents() → chunk_documents() → VectorStore (纯内存)
  docs/web/*.md       ─┘                                              ↓
                                                              query() → cosine → 结果
```

- **162 chunks**，TF-IDF 向量，每次 query 全量重建索引
- 无持久化：重启丢失索引，每次 `kb.query()` 都触发 `build()`
- 无增量：新文件加入后必须全量重建

### 1.2 元数据

- Web 笔记的 `topic`/`source`/`date` 埋在 Markdown 正文里，不可结构化查询
- 无 `.meta.json`，无法按 topic 筛选、按 URL 去重、按时间排序

### 1.3 展示

- "问答 KB" 只有：输入框 + 文本片段 + score 数字
- 无来源类型标签（笔记 vs 网页 vs 文档）
- 无 topic 分组
- 无 Web 内容浏览器（看不到抓了什么）

### 1.4 Agent 集成

- Agent 可写入（`fetch_url_text` → `enrich_kb_from_url`）
- Agent 可查询（`query_knowledge_base`）
- 但无去重、无元数据、无浏览界面

---

## 2. 目标架构

### 2.1 数据层

```
┌─────────────────────────────────────────────────────────┐
│                    KnowledgeBase                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ topics/  │  │  docs/   │  │ docs/web/│              │
│  │ 20 README│  │ *.md     │  │ *.md     │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │              │              │                    │
│       ▼              ▼              ▼                    │
│  ┌──────────────────────────────────────────┐           │
│  │         gather_documents()               │           │
│  │  (scan → Doc(topic, source, text, meta)) │           │
│  └──────────────────┬───────────────────────┘           │
│                     │                                    │
│                     ▼                                    │
│  ┌──────────────────────────────────────────┐           │
│  │       chunk_documents()                  │           │
│  │  (split by heading → Chunk with meta)    │           │
│  └──────────────────┬───────────────────────┘           │
│                     │                                    │
│                     ▼                                    │
│  ┌──────────────────────────────────────────┐           │
│  │         VectorStore                      │           │
│  │  (TF-IDF matrix + chunks)               │           │
│  │  persist to: .cache/store.pkl           │           │
│  └──────────────────────────────────────────┘           │
│                                                          │
│  ┌──────────────────────────────────────────┐           │
│  │         MetadataIndex                    │           │
│  │  (per-file .meta.json lookup)            │           │
│  │  - url → note_path (去重)               │           │
│  │  - topic → [chunks] (按 topic 筛选)     │           │
│  │  - date → [chunks] (时间排序)           │           │
│  └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

### 2.2 元数据结构

每个 web 笔记对应一个 `.meta.json`（与 `.md` 同目录）：

```json
{
  "url": "https://example.com",
  "title": "Example Domain",
  "topic_id": "09_knowledge_base",
  "topic_confidence": 0.72,
  "topic_method": "embedding",
  "fetched_at": "2026-08-25T22:10:19",
  "source_type": "web",
  "file_path": "docs/web/20260825_221019_c984d06aafbe_Example_Domain.md",
  "tags": ["rag", "vector-search"],
  "word_count": 850
}
```

### 2.3 索引策略

| 阶段 | 操作 | 触发 |
|------|------|------|
| 首次/全量 | `kb ingest` — 扫描所有目录，构建向量矩阵，保存到 `.cache/` | 手动 |
| 增量 | `kb ingest --incremental` — 只处理新增/修改的文件 | 可自动（agent 抓取后） |
| 查询 | 加载 `.cache/store.pkl`，不重建 | 每次 `query()` |
| 缓存失效 | 文件 mtime 变化 → 重新索引该文件 | 自动检测 |

---

## 3. 功能设计

### 3.1 Web 内容浏览器（学习 tab 新 pane）

**位置**：学习 tab → "网页笔记" 子 tab（与"笔记"、"Demo"、"问答 KB" 并列）

**界面**：

```
┌─────────────────────────────────────────────────────┐
│ 网页笔记                                    [筛选 ▾] │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐ │
│ │ 📄 Example Domain                    [网页]      │ │
│ │ 来源: example.com · 分类: 09 知识库 · 8/25 22:10│ │
│ │ [查看] [重分类] [删除]                           │ │
│ └─────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 📄 Pi Sandbox · Packages · Pi         [网页]      │ │
│ │ 来源: pypi.org · 分类: unknown · 8/25 22:28     │ │
│ │ [查看] [重分类] [删除]                           │ │
│ └─────────────────────────────────────────────────┘ │
│                                                      │
│ 共 3 篇网页笔记 · 索引 162 chunks                    │
└─────────────────────────────────────────────────────┘
```

**交互**：
- 「查看」→ 展开 Markdown 渲染（复用 `renderMd()`）
- 「重分类」→ 下拉选择 topic → 调 `/api/learn/web/reclassify`
- 「删除」→ 确认后调 `/api/learn/web/delete` → 删除 `.md` + `.meta.json`
- 「筛选」→ 按 topic / 时间 / 关键词筛选

**API**：

```
GET  /api/learn/web/list          → { notes: [{title, url, topic, fetched_at, path}] }
POST /api/learn/web/reclassify    → { path, topic_id } → 重新分类
POST /api/learn/web/delete        → { path } → 删除笔记
GET  /api/learn/web/stats         → { total, by_topic: {topic: count} }
```

### 3.2 搜索结果增强

**当前**：
```
[0.72] topics/09_knowledge_base/README.md
LangGraph 是一个...
```

**改进后**：
```
┌─────────────────────────────────────────────────────┐
│ 📝 笔记 · 09_knowledge_base              score 0.72 │
│ "LangGraph 是一个基于图的 Agent 编排框架..."          │
│ → 查看完整笔记                                       │
├─────────────────────────────────────────────────────┤
│ 🌐 网页 · example.com                       score 0.45│
│ "Example Domain — 用于文档示例的域名..."              │
│ → 查看网页笔记                                       │
└─────────────────────────────────────────────────────┘
```

**分组逻辑**：
- 按 `source_type` 分组：笔记 / 网页 / 文档
- 每组内按 score 降序
- 来源类型用 badge 区分：📝 笔记 / 🌐 网页 / 📄 文档

### 3.3 URL 去重

**流程**：
```
Agent 调用 fetch_url_text(url)
  ↓
enrich_kb_from_url(url, ...)
  ↓
检查 docs/web/ 下所有 .meta.json
  if url 已存在:
    return { ok: true, kb_note: existing_path, duplicate: true }
  else:
    写入 .md + .meta.json
    return { ok: true, kb_note: new_path, duplicate: false }
```

**实现**：
- `kb_enrich.py` 增加 `_find_existing_note(url)` 函数
- 扫描 `docs/web/*.meta.json` 匹配 url
- 命中则返回已有路径，不重复写入

### 3.4 Agent 工具增强

`query_knowledge_base` 返回值增加元数据：

```python
{
    "ok": True,
    "results": [
        {
            "score": 0.72,
            "source": "topics/09_knowledge_base/README.md",
            "topic": "09_knowledge_base",
            "source_type": "note",     # 新增
            "text": "LangGraph 是...",
            "url": "",                  # 新增（web 笔记有值）
            "fetched_at": "",           # 新增
        }
    ]
}
```

---

## 4. 实现计划

### Phase 1: 元数据 + 去重（P0）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 为现有 web 笔记生成 `.meta.json` | `kb_enrich.py` (新函数) | S |
| `enrich_kb_from_url` 增加去重逻辑 | `kb_enrich.py` | S |
| `ingest.py` 读取 `.meta.json` 填充 Chunk.meta | `ingest.py` | M |
| `query_knowledge_base` 返回 source_type + url | `builtin.py` | S |

### Phase 2: Web 浏览器 UI（P0）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| 后端 API：list / reclassify / delete / stats | `learn_routes.py` | M |
| 前端："网页笔记" pane + 列表/查看/操作 | `index.html` + `learn.js` | L |
| 搜索结果分组展示 | `learn.js` (runKb) | M |

### Phase 3: 增量索引（P1）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| `VectorStore` 序列化/反序列化 | `store.py` | M |
| `kb.py` 增量 build（检测 mtime） | `kb.py` | M |
| `.cache/` 目录管理 | `kb.py` | S |

### Phase 4: 智能关联（P2）

| 任务 | 文件 | 工作量 |
|------|------|--------|
| Topic 页面显示相关网页笔记 | `learn.js` | M |
| 知识图谱加入 web 节点 | `learn.js` | L |

---

## 5. 非目标

- 不换向量库（TF-IDF 够用，保持离线可跑）
- 不加 LLM 总结（离线模式不可用，保持现状）
- 不做全文搜索（向量检索足够）
- 不做用户权限（单用户场景）

---

## 6. 验收标准

- [ ] `docs/web/` 下每个 `.md` 有对应 `.meta.json`
- [ ] 同一 URL 不会重复写入
- [ ] 学习 tab 有"网页笔记" pane，可浏览/查看/删除/重分类
- [ ] 问答 KB 搜索结果按来源类型分组
- [ ] Agent `query_knowledge_base` 返回 source_type + url
- [ ] `kb ingest` 支持增量模式（仅处理新文件）
- [ ] 全部 lsp_diagnostics 通过
