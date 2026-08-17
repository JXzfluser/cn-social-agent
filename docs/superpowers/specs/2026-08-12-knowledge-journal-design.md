# 知识期刊 · 采编 → 成刊 设计

> Date: 2026-08-12  
> Status: Approved (conversation)  
> Extends: [2026-08-09-knowledge-cards-design.md](./2026-08-09-knowledge-cards-design.md)

## 目标

把知识卡片从「浅扫 + 硬模板填空」升级为**可实用的知识期刊**：

1. **深采（A）**：大量扫描、过滤、打分，形成可追溯证据池  
2. **灵活成刊（B）**：打破固定 3 卡 +【机制】【易错】【检验】硬模板；3–6 张混排，论点挂证据  

用户感知：一期 = 刊号 + 素材台账 + 成刊稿；可「只重成刊、不重扫」。

## 非目标（本轮）

- 长文杂志正文再抽卡（方案 3）
- 付费搜索 API、无头浏览器整页抓取、站点登录
- 改动微信/头条发布协议
- 强制所有用户必须深采（快扫路径保留）

## 问题诊断（现状）

- 扫描浅：每主题 ≤3 query，有用片段约 6 条即停；AI 路径只喂 LLM ≤8 条  
- 市场信号曾被词典/导航站污染（已部分过滤，但仍浅）  
- LLM 被锁在「3 卡 + 机制/易错/检验 + 字数框」→ 材料不足时只能写空话  
- UI 把默认 AI 路径标成「深度生成」，名不副实  

## 形态总览

```
主题/分类
  ├─ 深采 research ──► Evidence Pack（可勾选）
  │                      │
  │                      └─ 成刊 compose ──► Journal Issue（cover + 3–6 cards + evidenceIds）
  │
  └─ 快扫 scan（兼容）──► 浅 research + compose（卡数偏少，一次完成）
```

| 用户动作 | API | 产出 |
|----------|-----|------|
| 深采 | `POST /api/cards/research` | `evidencePack` |
| 成刊 | `POST /api/cards/compose` | 现有 cover/knowledge + 证据摘要 |
| 快扫 | `POST /api/cards/scan` | 浅采 + 成刊一体（兼容旧客户端） |

刊号「第 N 期」逻辑不变（空则 `len(history)+1`）。

## 采编 · Evidence Pack

### 扫描深度

- 最多 **3** 个主题并行  
- 每主题 **6–8** 条 query：分类 `scrape_suffixes` + 维度词（如编排/RAG/交付）+ 面试/实践向；多字主题继续整词加引号  
- Bing 为主；有用片段不足再 Baidu / DDG  
- **早期停止**：有用片段 ≥ **18**/主题 或全局合并后 ≥ **30** 再停（替换今天的 ~6）  
- HTTP timeout 仍约 9s/请求；失败跳过，不拖垮整包  

### 证据条目 schema

```json
{
  "id": "e1",
  "text": "…",
  "query": "…",
  "engine": "bing|baidu|ddg",
  "role": "主题名",
  "score": 0.0,
  "signals": ["招聘", "LangGraph"],
  "url": "",
  "title": ""
}
```

- `id`：包内稳定短 ID（`e1`…），成刊引用只用这些 ID  
- `score`：信号命中 + 主题命中 + 长度；词典/百科/工具导航站直接丢弃（沿用并扩展 `is_useful_snippet`）  
- 合并去重后目标 **20–40** 条；写入 pack 时按 score 降序  

### Pack 持久化

- 本地历史记录增加 `evidencePack`（或并列 `data/cards/packs/`，以 history 内嵌优先，减少碎片）  
- InsForge `wb_card_history`：增加 JSON 字段存 pack（若列不存在则仅本地；不阻塞成刊）  
- `mode` 扩展：`research`（仅采编未成刊）| `journal`（成刊完成）| 保留 `ai`/`live`/`cached` 给快扫  

### 可编辑

- 工坊「本期素材」列表：勾选/剔除；成刊只使用 `selected !== false` 的证据  
- 允许在已有 pack 上再次「深采追加」（同主题 merge 去重），不强制清空  

## 成刊 · Journal Issue

### 版式灵活性

- **取消**「永远 3 卡 + 必须三行【机制】【易错】【检验】」硬约束  
- 规范化后：**3–6** 张卡；`card_kind` 混排：`concept | keypoints | steps | compare | data | quote`  
- 字段按 kind 弹性：
  - `keypoints`：条目列表（2–5 条），不强制机制模板  
  - `steps`：强调 `flow`  
  - `data`：强调 `metric` / `metric_note`  
  - `quote`：强调 `quote` + `source`  
  - `compare`：`compare.left` / `right`  
- 招聘类可在 `llm_teach` 中**建议**机制/易错/检验，但不再作为 JSON 解析失败条件  

### 证据硬约束

- 每张卡 `evidenceIds: string[]`，**至少 1 个**，且必须存在于当前 pack  
- `marketNote`：优先高分证据摘录/压缩改写；无合格证据则留空（禁止词典句）  
- 事实性陈述应能对应证据；纯方法建议标 `stance: "evidence" | "opinion"`（默认 evidence；无引用则 opinion，UI 弱化）  
- 禁止编造 `evidenceIds`；LLM 输出非法 ID 时在 normalize 阶段丢弃并尽量从卡内关键词回填最高分证据  

### LLM 流程（成刊）

1. **大纲**：输入主题 + 证据摘要（id + 前 120 字 + score）；输出 cover 草案 + 3–6 个选题（title/kind/angle/evidenceIds）  
2. **扩写**：按大纲写正文；回填 `evidenceIds`；注入 anti-hollow（具名技术、可验证动作、禁口号）  
3. **normalize**：clamp 卡数、补齐 kind 字段、校验 evidenceIds、edition、visual_style  

快扫路径：浅 pack（每主题约 3 query、全局 ≤12 有用）→ 同一 compose；卡数倾向 3。

## API

### `POST /api/cards/research`

Body: `{ roles|topics, category, appendPackId? }`  
Response: `{ packId, evidencePack, roles, category, snippetCount, persisted }`  
副作用：写入/更新 history（可先存 `mode: research` 草稿）。

### `POST /api/cards/compose`

Body: `{ packId?, evidences?, roles, category, edition?, evidenceIdsAllowed? }`  
- 有 `packId` 则加载 pack；否则用请求内 `evidences`  
- 应用用户勾选过滤后再 LLM  

Response: 现有 scan 成功体 + `evidencePack` 摘要 + `mode: "journal"`。

### `POST /api/cards/scan`（兼容）

内部：`research(depth=shallow)` + `compose`；`mode` 可为 `ai`（保持旧语义）或标注 `journal` 若证据足够。  
UI 文案改为「快扫」，不再叫「深度生成」。

## UI（cards workshop）

- 主按钮拆分：**深采**、**成刊**（成刊在无 pack / 选中证据 < 5 时禁用并提示先深采）  
- 次要：**快扫**（下拉或次按钮）  
- **素材台账**面板（预览区上方或左侧历史旁）：分数、摘录、query、勾选；角标「可用 N 条」  
- 单卡编辑：展示已挂证据芯片；点击展开原文  
- 状态：`采编中…` → `素材就绪（N 条）` → `成刊中…` → `第 N 期已生成`  
- 历史回载：若有 `evidencePack`，恢复台账并可再成刊  

## 错误与降级

| 情况 | 行为 |
|------|------|
| 深采 0 有用片段 | 返回空 pack + 明确错误；不自动用词典垃圾填 marketNote |
| 成刊 LLM 失败 | 保留 pack；可用 `build_cards` 主题模板成刊但标记 `mode: cached` 且 UI 提示「证据不足/模型失败」 |
| InsForge 缺列 | pack 仅本地；`persisted: local` |
| 快扫 | 与现网一致的超时/失败回退链 |

## 测试

- 单元：`is_useful_snippet` / 打分 / 去重 / evidenceId 校验 / 卡数 clamp 3–6  
- 单元：compose normalize 丢弃非法 evidenceIds 并回填  
- API：research → compose 串联（可 mock httpx / LLM）  
- 回归：旧 `POST /api/cards/scan` 仍返回 cover + knowledge  

## 实现顺序（供计划拆分）

1. 加深 scrape + Evidence Pack 模型与 research API  
2. compose LLM（灵活 schema + evidenceIds）+ normalize  
3. 工坊 UI：深采/成刊/台账/快扫文案  
4. history/InsForge 持久化 pack；历史回载  
5. 快扫改为浅 research+compose；测试与样例刊  

## 成功标准

- 同主题深采后，sources/台账中**不再出现**拼音词典类片段  
- 成刊每张卡可见至少一条可点开的证据  
- 一期可出现 **≥2 种** `card_kind`，且不必再是三行机制模板  
- 用户可剔除证据后重成刊，**不必重扫**
