# 可视化工作流编辑器设计

> Date: 2026-08-26  
> Status: Approved  
> Related: `src/cn_social_agent/content/automations.py`、`api/automation_routes.py`、Workbench 项目 Tab

## 1. Goal

在项目 Tab 中嵌入**可视化工作流编辑器**，让用户用拖拽节点的方式编排内容生产流水线：

**触发器 → 动作 → 条件 → 输出**

实现：
1. 可视化画布：节点 + 连线，所见即所得
2. 节点配置：点击节点可配置参数
3. 即时运行：支持手动触发、定时触发、Webhook 触发
4. 运行历史：查看每次执行的状态和输出

成功标准：
- 用户能在 5 分钟内搭建一个「热点扫描 → LLM 生成 → 保存项目」的流水线
- 运行时可视化看到每个节点的执行状态
- 支持保存/加载工作流模板

## 2. Scope

### 2.1 In Scope

| 功能 | 说明 |
|------|------|
| 节点编辑器 | SVG 画布、拖拽、连线、缩放、平移 |
| 节点类型 | 触发器（定时/Webhook/手动）、动作（热点/LLM/视频）、控制（条件/延时）、输出（通知/保存） |
| 节点配置 | 点击节点弹出配置面板 |
| 工作流管理 | CRUD、启用/禁用、模板 |
| 执行引擎 | 异步执行、状态追踪、错误处理 |
| 运行历史 | 执行记录、节点状态可视化 |
| 预设模板 | 3-5 个常用工作流 |

### 2.2 Out of Scope (v1)

- 嵌套子工作流
- 跨用户工作流共享
- 工作流市场
- 复杂循环/并行分支
- 实时日志流

## 3. Architecture

### 3.1 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Workbench UI                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Workflow Editor                         │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │  │
│  │  │ Node    │  │ Canvas  │  │ Config  │  │ Toolbar │    │  │
│  │  │ Palette │  │ (SVG)   │  │ Panel   │  │         │    │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  Workflow API                             │  │
│  │  GET/POST/PUT/DELETE /api/workflows                       │  │
│  │  POST /api/workflows/:id/run                              │  │
│  │  GET /api/workflows/:id/runs                              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                Workflow Engine                            │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │  │
│  │  │ Scheduler│  │ Executor │  │ State   │  │ Handlers│    │  │
│  │  │         │  │         │  │ Store   │  │ (per type)│   │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Existing Modules                             │  │
│  │  hotspot_scan │ llm_generate │ video_render │ publish    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流

```
用户创建/编辑工作流
        │
        ▼
Workflow JSON (nodes + edges)
        │
        ▼
┌───────────────────┐
│ POST /api/workflows│ ──→ InsForge DB / 本地存储
└───────────────────┘
        │
        ▼ (触发)
┌───────────────────┐
│ 执行引擎          │
│ 1. 拓扑排序       │
│ 2. 逐节点执行     │
│ 3. 传递上下文     │
│ 4. 记录状态       │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ 运行状态 API      │ ──→ 前端轮询/WebSocket
└───────────────────┘
```

## 4. Data Model

### 4.0 存储方案

使用 InsForge 表存储：

| 表名 | 说明 |
|------|------|
| `workflows` | 工作流定义（JSON 序列化 nodes/edges） |
| `workflow_runs` | 运行历史 |
| `workflow_templates` | 预设模板 |

创建方式：通过 InsForge API (`POST /api/tables`) 或 SQL 直接建表。

**Workflow 表结构：**

```sql
CREATE TABLE workflows (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  nodes JSONB NOT NULL DEFAULT '[]',
  edges JSONB NOT NULL DEFAULT '[]',
  trigger_config JSONB NOT NULL DEFAULT '{}',
  enabled BOOLEAN DEFAULT true,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE workflow_runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL REFERENCES workflows(id),
  status TEXT NOT NULL DEFAULT 'pending',
  trigger_type TEXT NOT NULL,
  node_states JSONB NOT NULL DEFAULT '{}',
  context JSONB NOT NULL DEFAULT '{}',
  error TEXT,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

CREATE TABLE workflow_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  nodes JSONB NOT NULL DEFAULT '[]',
  edges JSONB NOT NULL DEFAULT '[]',
  thumbnail TEXT
);
```

### 4.1 Workflow

```typescript
interface Workflow {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  enabled: boolean;
  trigger: WorkflowTrigger;      // 主触发器配置
  createdAt: string;
  updatedAt: string;
  createdBy: string;
}

interface WorkflowTrigger {
  type: "manual" | "schedule" | "webhook" | "event";
  config: {
    cron?: string;               // schedule 类型
    webhookPath?: string;        // webhook 类型
    event?: string;              // event 类型
  };
}

interface WorkflowNode {
  id: string;
  type: string;                  // "trigger.schedule" | "action.hotspot_scan" | ...
  position: { x: number; y: number };
  config: Record<string, any>;
  label?: string;                // 用户自定义标签
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;         // 用于条件分支 ("true" | "false")
  label?: string;
}
```

### 4.2 WorkflowRun

```typescript
interface WorkflowRun {
  id: string;
  workflowId: string;
  status: "pending" | "running" | "success" | "failed" | "cancelled";
  triggerType: "manual" | "schedule" | "webhook" | "event";
  nodeStates: Record<string, NodeState>;
  context: Record<string, any>;  // 运行时上下文（传递给各节点）
  startedAt: string;
  finishedAt?: string;
  error?: string;
}

interface NodeState {
  status: "pending" | "running" | "done" | "failed" | "skipped";
  input?: any;
  output?: any;
  error?: string;
  startedAt?: string;
  finishedAt?: string;
  durationMs?: number;
}
```

### 4.3 WorkflowTemplate

```typescript
interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: "content" | "publish" | "analysis";
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  thumbnail?: string;            // 可选预览图
}
```

## 5. Node Types

### 5.1 触发器 (Trigger)

| Type | Label | Config | 说明 |
|------|-------|--------|------|
| `trigger.manual` | 手动触发 | `{}` | 用户点击运行 |
| `trigger.schedule` | 定时触发 | `{ cron: "0 9 * * *" }` | Cron 表达式 |
| `trigger.webhook` | Webhook | `{ secret: "xxx" }` | HTTP 触发（带鉴权） |
| `trigger.event` | 事件触发 | `{ event: "hotspot.new" }` | 系统事件 |

**Webhook 安全机制：**

每个 Webhook 触发器生成唯一 secret token，用于验证请求合法性。

```python
import hashlib
import hmac

class WebhookTrigger:
    def __init__(self):
        self.secret = secrets.token_urlsafe(32)
    
    def generate_url(self, workflow_id: str) -> str:
        """生成带 token 的 Webhook URL"""
        return f"/api/workflows/run/hook/{workflow_id}?token={self.secret}"
    
    def verify(self, workflow_id: str, token: str) -> bool:
        """验证 token"""
        return hmac.compare_digest(token, self.secret)
```

**Webhook 端点：**

```python
# POST /api/workflows/run/hook/:workflowId?token=xxx
async def webhook_handler(request):
    workflow_id = request.match_info['workflowId']
    token = request.query.get('token', '')
    
    # 验证 token
    workflow = await get_workflow(workflow_id)
    if not workflow or not verify_webhook_token(workflow, token):
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    # 执行工作流
    context = await request.json()
    run = await engine.execute(workflow, context, trigger_type="webhook")
    
    return web.json_response({"runId": run.id})
```

### 5.2 动作 (Action)

| Type | Label | Config | 说明 |
|------|-------|--------|------|
| `action.hotspot_scan` | 热点扫描 | `{ source, domain, limit }` | 扫描热点榜单 |
| `action.llm_generate` | LLM 生成 | `{ prompt, model, maxLength }` | 调用 LLM |
| `action.evidence_collect` | 素材采集 | `{ url, depth }` | 采集网页素材 |
| `action.storyboard` | 生成分镜 | `{ template, duration }` | 生成视频分镜 |
| `action.video_render` | 视频渲染 | `{ quality, voice }` | 渲染视频 |
| `action.image_gen` | 图片生成 | `{ prompt, style }` | AI 生成图片 |

### 5.3 发布 (Publish)

| Type | Label | Config | 说明 |
|------|-------|--------|------|
| `publish.weixin` | 发微信 | `{ draft, author }` | 微信公众号 |
| `publish.toutiao` | 发头条 | `{ draft }` | 今日头条 |
| `publish.douyin` | 发抖音 | `{ draft }` | 抖音 |
| `publish.xiaohongshu` | 发小红书 | `{ draft }` | 小红书 |

### 5.4 控制流 (Control)

| Type | Label | Config | 说明 |
|------|-------|--------|------|
| `control.condition` | 条件判断 | `{ conditions: [] }` | 根据条件分支 |
| `control.delay` | 延时 | `{ seconds }` | 等待指定秒数 |
| `control.loop` | 循环 | `{ count, items }` | 循环执行 |
| `control.stop` | 停止 | `{ reason }` | 终止工作流 |

**条件表达式语法（`control.condition`）：**

```typescript
interface ConditionConfig {
  logic: "and" | "or";           // 多条件组合方式
  conditions: ConditionItem[];
}

interface ConditionItem {
  field: string;                  // 上下文字段路径，如 "hotspot.score"
  operator: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" 
          | "contains" | "not_contains" 
          | "exists" | "not_exists"
          | "matches";            // 正则匹配
  value?: any;                    // 比较值（exists/not_exists 可省略）
}
```

**示例：**

```json
{
  "logic": "and",
  "conditions": [
    { "field": "hotspot.score", "operator": "gte", "value": 70 },
    { "field": "hotspot.domain", "operator": "eq", "value": "ai" }
  ]
}
```

**执行逻辑：**

```python
class ConditionHandler(NodeHandler):
    def evaluate(self, config: dict, context: dict) -> bool:
        logic = config.get("logic", "and")
        conditions = config.get("conditions", [])
        
        results = []
        for cond in conditions:
            field_value = self.resolve_field(cond["field"], context)
            result = self.compare(field_value, cond["operator"], cond.get("value"))
            results.append(result)
        
        if logic == "and":
            return all(results)
        else:  # or
            return any(results)
    
    def resolve_field(self, field: str, context: dict) -> any:
        """解析字段路径，如 'hotspot.score' -> context['hotspot']['score']"""
        parts = field.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
    
    def compare(self, actual: any, operator: str, expected: any) -> bool:
        if operator == "eq":
            return actual == expected
        elif operator == "neq":
            return actual != expected
        elif operator == "gt":
            return actual > expected
        elif operator == "gte":
            return actual >= expected
        elif operator == "lt":
            return actual < expected
        elif operator == "lte":
            return actual <= expected
        elif operator == "contains":
            return expected in actual
        elif operator == "not_contains":
            return expected not in actual
        elif operator == "exists":
            return actual is not None
        elif operator == "not_exists":
            return actual is None
        elif operator == "matches":
            import re
            return bool(re.search(expected, str(actual)))
        return False
```

**分支输出：**

条件节点有两个输出口：
- `true` 分支：条件为真时走此路
- `false` 分支：条件为假时走此路

```python
async def execute(self, config, context):
    result = self.evaluate(config, context)
    return {
        "result": result,
        "branch": "true" if result else "false"
    }
```

### 5.5 输出 (Output)

| Type | Label | Config | 说明 |
|------|-------|--------|------|
| `output.save_project` | 保存项目 | `{ title, category }` | 保存为内容项目 |
| `output.notify` | 通知 | `{ channel, message }` | 发送通知 |
| `output.export` | 导出 | `{ format, path }` | 导出文件 |

## 6. API

### 6.1 Workflow CRUD

```python
# GET /api/workflows
# 获取所有工作流
Response: {
  workflows: Workflow[],
  templates: WorkflowTemplate[]
}

# GET /api/workflows/:id
# 获取单个工作流
Response: Workflow

# POST /api/workflows
# 创建工作流
Body: {
  name: string,
  description?: string,
  nodes: WorkflowNode[],
  edges: WorkflowEdge[],
  trigger: WorkflowTrigger
}
Response: Workflow

# PUT /api/workflows/:id
# 更新工作流
Body: Partial<Workflow>
Response: Workflow

# DELETE /api/workflows/:id
# 删除工作流
Response: { ok: true }
```

### 6.2 执行

```python
# POST /api/workflows/:id/run
# 手动运行工作流
Body: {
  context?: Record<string, any>  # 运行时输入
}
Response: {
  runId: string,
  status: "pending" | "running"
}

# POST /api/workflows/:id/cancel
# 取消运行
Body: {
  runId: string
}
Response: { ok: true }
```

### 6.3 运行状态

```python
# GET /api/workflows/:id/runs
# 获取运行历史
Query: { limit?: number, offset?: number }
Response: {
  runs: WorkflowRun[],
  total: number
}

# GET /api/workflows/runs/:runId
# 获取单次运行状态
Response: WorkflowRun

# DELETE /api/workflows/:id/runs
# 清理运行历史（保留最近 N 条）
Query: { keep?: number }  # 默认 100
Response: { deleted: number }
```

**自动清理策略：**

每次工作流执行完成后，自动清理超过 100 条的旧记录：

```python
async def cleanup_runs(self, workflow_id: str, keep: int = 100):
    """保留最近 keep 条运行记录"""
    # 查询总数
    total = await db.query(
        "SELECT COUNT(*) FROM workflow_runs WHERE workflow_id = $1",
        workflow_id
    )
    
    if total > keep:
        # 删除超出的记录
        deleted = await db.execute("""
            DELETE FROM workflow_runs 
            WHERE workflow_id = $1 
            AND id NOT IN (
                SELECT id FROM workflow_runs 
                WHERE workflow_id = $1 
                ORDER BY started_at DESC 
                LIMIT $2
            )
        """, workflow_id, keep)
```

### 6.4 模板

```python
# GET /api/workflows/templates
# 获取预设模板
Response: WorkflowTemplate[]

# POST /api/workflows/from-template/:templateId
# 从模板创建工作流
Body: {
  name?: string  # 覆盖默认名
}
Response: Workflow
```

## 7. UI Design

### 7.0 前端文件结构

```
src/cn_social_agent/workbench/
  project_board.js        # 现有：项目看板（保留）
  workflow/
    index.js              # 主入口：Tab 切换 + 初始化
    editor.js             # 编辑器主控
    canvas.js             # SVG 画布（缩放/平移/选择）
    node-palette.js       # 左侧节点面板（拖拽源）
    node-renderer.js      # 节点 SVG 渲染
    edge-renderer.js      # 连线 SVG 渲染
    node-config.js        # 右侧配置面板
    run-status.js         # 运行状态可视化
    api.js                # API 调用封装
    templates.js          # 预设模板数据
    utils.js              # 工具函数（ID生成等）
```

**集成方式：**

在 `index.html` 中新增 Tab：

```html
<div class="tabs">
  <button class="tab active" data-tab="agent">Agent</button>
  <button class="tab" data-tab="project">项目</button>
  <button class="tab" data-tab="canvas">画布</button>
  <!-- 新增 -->
  <button class="tab" data-tab="workflow">工作流</button>
  <button class="tab" data-tab="knowledge">知识卡片</button>
</div>
```

**注意**：「项目」Tab 保持现有看板功能不变，「工作流」是新增 Tab。

### 7.1 工作流 Tab 布局

```
┌─────────────────────────────────────────────────────────────────┐
│  工作流                                                    [设置] │
├─────────────────────────────────────────────────────────────────┤
│  工作流列表                    │  画布区域                      │
│  ┌─────────────────────────┐  │  ┌───────────────────────────┐ │
│  │ + 新建工作流            │  │  │                           │ │
│  │                         │  │  │   [节点] ──→ [节点]      │ │
│  │ □ 每日热点生产线  ✓    │  │  │                           │ │
│  │ □ 热点即发        ✓    │  │  │      ↓                    │ │
│  │ □ 每周回顾        ✗    │  │  │   [节点] ──→ [节点]      │ │
│  │                         │  │  │                           │ │
│  │ ─────────────────────  │  │  └───────────────────────────┘ │
│  │ 模板                    │  │                                 │
│  │ [热点生产线]           │  │  节点配置面板                   │
│  │ [多平台发布]           │  │  ┌───────────────────────────┐ │
│  │ [内容质检]             │  │  │ 节点: LLM 生成            │ │
│  │                         │  │  │ Prompt: [____________]   │ │
│  └─────────────────────────┘  │  │ Model:  [fast ▼]        │ │
│                               │  │                           │ │
│                               │  │ [运行] [删除]             │ │
│                               │  └───────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```
│  工作流列表                    │  画布区域                      │
│  ┌─────────────────────────┐  │  ┌───────────────────────────┐ │
│  │ + 新建工作流            │  │  │                           │ │
│  │                         │  │  │   [节点] ──→ [节点]      │ │
│  │ □ 每日热点生产线  ✓    │  │  │                           │ │
│  │ □ 热点即发        ✓    │  │  │      ↓                    │ │
│  │ □ 每周回顾        ✗    │  │  │   [节点] ──→ [节点]      │ │
│  │                         │  │  │                           │ │
│  │ ─────────────────────  │  │  └───────────────────────────┘ │
│  │ 模板                    │  │                                 │
│  │ [热点生产线]           │  │  节点配置面板                   │
│  │ [多平台发布]           │  │  ┌───────────────────────────┐ │
│  │ [内容质检]             │  │  │ 节点: LLM 生成            │ │
│  │                         │  │  │ Prompt: [____________]   │ │
│  └─────────────────────────┘  │  │ Model:  [fast ▼]        │ │
│                               │  │                           │ │
│                               │  │ [运行] [删除]             │ │
│                               │  └───────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 节点编辑器

**画布交互：**
- 拖拽节点到画布
- 连线：从节点输出口拖到另一节点输入口
- 选中节点：显示配置面板
- 缩放：鼠标滚轮 / 按钮
- 平移：拖拽空白区域
- 删除：选中后 Delete 键

**编辑器功能：**

| 功能 | 快捷键 | 说明 |
|------|--------|------|
| 撤销 | Ctrl+Z | 撤销上一步操作 |
| 重做 | Ctrl+Shift+Z | 重做上一步操作 |
| 复制 | Ctrl+C | 复制选中节点 |
| 粘贴 | Ctrl+V | 粘贴节点（自动偏移位置） |
| 全选 | Ctrl+A | 选中所有节点 |
| 删除 | Delete / Backspace | 删除选中节点 |
| 保存 | Ctrl+S | 保存工作流 |
| 缩放适配 | Ctrl+0 | 缩放画布以适配所有节点 |
| 网格对齐 | 自动 | 节点拖拽时自动吸附到 20px 网格 |

**撤销/重做实现：**

```javascript
class HistoryManager {
  constructor() {
    this.undoStack = [];
    this.redoStack = [];
  }
  
  push(state) {
    this.undoStack.push(JSON.stringify(state));
    this.redoStack = [];  // 新操作清空重做栈
    
    // 限制历史长度
    if (this.undoStack.length > 50) {
      this.undoStack.shift();
    }
  }
  
  undo(currentState) {
    if (this.undoStack.length === 0) return null;
    
    this.redoStack.push(JSON.stringify(currentState));
    return JSON.parse(this.undoStack.pop());
  }
  
  redo(currentState) {
    if (this.redoStack.length === 0) return null;
    
    this.undoStack.push(JSON.stringify(currentState));
    return JSON.parse(this.redoStack.pop());
  }
}
```

**节点样式：**
```
┌─────────────────────┐
│ 🔥 热点扫描         │  ← 图标 + 标题
│ source: all         │  ← 关键配置摘要
│ limit: 5            │
└─────────────────────┘
  ○                    ← 输出口（圆点）
```

**颜色编码：**
- 触发器：橙色边框
- 动作：蓝色边框
- 发布：绿色边框
- 控制：紫色边框
- 输出：灰色边框

### 7.3 节点配置面板

点击节点时，右侧面板显示配置表单：

```yaml
节点类型: action.llm_generate
标签: [生成口播脚本    ]

Prompt:
┌─────────────────────────────────────┐
│ 根据以下热点生成口播脚本：          │
│ {{hotspot.title}}                   │
│                                     │
│ 要求：15-30秒，口语化，有观点      │
└─────────────────────────────────────┘

模型路由: [智能 ▼]
最大长度: [500]

[测试运行] [删除节点]
```

### 7.4 运行状态可视化

工作流运行时，节点显示状态指示：

```
┌─────────────────────┐
│ ✅ 热点扫描         │  ← 完成：绿色勾
│ found: 5 items      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 🔄 LLM 生成         │  ← 运行中：旋转图标
│ 2/3 items done      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ ⏳ 视频渲染         │  ← 等待中：灰色
└─────────────────────┘
```

## 8. Execution Engine

### 8.0 调度器

使用 Python 进程内调度（APScheduler），无需依赖系统 cron。

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class WorkflowScheduler:
    def __init__(self, engine: WorkflowEngine):
        self.engine = engine
        self.scheduler = AsyncIOScheduler()
        self.jobs: dict[str, str] = {}  # workflow_id -> job_id
    
    async def start(self):
        """启动调度器，加载所有 enabled 的定时工作流"""
        self.scheduler.start()
        
        # 从 DB 加载所有 enabled + schedule 类型的工作流
        workflows = await self.load_scheduled_workflows()
        for wf in workflows:
            self.schedule_workflow(wf)
    
    def schedule_workflow(self, workflow: Workflow):
        """注册定时任务"""
        if workflow.trigger.type != "schedule":
            return
        
        cron = workflow.trigger.config.get("cron")
        if not cron:
            return
        
        # 移除旧任务
        self.unschedule_workflow(workflow.id)
        
        # 解析 cron 表达式
        trigger = CronTrigger.from_crontab(cron)
        
        # 添加任务
        job = self.scheduler.add_job(
            self.run_workflow,
            trigger,
            args=[workflow.id],
            id=f"workflow_{workflow.id}",
            replace_existing=True,
        )
        
        self.jobs[workflow.id] = job.id
    
    def unschedule_workflow(self, workflow_id: str):
        """取消定时任务"""
        job_id = self.jobs.pop(workflow_id, None)
        if job_id:
            self.scheduler.remove_job(job_id)
    
    async def run_workflow(self, workflow_id: str):
        """执行工作流"""
        await self.engine.execute_by_id(workflow_id, trigger_type="schedule")
```

**启动时初始化：**

```python
# app 启动时
scheduler = WorkflowScheduler(engine)
await scheduler.start()
```

**工作流更新时：**

```python
# PUT /api/workflows/:id 更新后
if workflow.enabled and workflow.trigger.type == "schedule":
    scheduler.schedule_workflow(workflow)
else:
    scheduler.unschedule_workflow(workflow.id)
```

### 8.1 执行流程

```python
class WorkflowEngine:
    async def execute(self, workflow: Workflow, context: dict = None):
        run = self.create_run(workflow, context)
        
        # 1. 拓扑排序
        order = self.topological_sort(workflow.nodes, workflow.edges)
        
        # 2. 逐节点执行
        for node_id in order:
            node = workflow.get_node(node_id)
            
            # 检查前置条件
            if not self.check_prerequisites(node, run):
                run.node_states[node_id].status = "skipped"
                continue
            
            # 执行节点
            try:
                run.node_states[node_id].status = "running"
                output = await self.execute_node(node, run.context)
                
                run.node_states[node_id].status = "done"
                run.node_states[node_id].output = output
                
                # 传递输出到下游
                self.propagate_output(node_id, output, run)
                
            except Exception as e:
                run.node_states[node_id].status = "failed"
                run.node_states[node_id].error = str(e)
                
                # 检查是否继续
                if not self.can_continue_on_error(node, e):
                    run.status = "failed"
                    break
        
        run.status = "success" if run.status != "failed" else "failed"
        return run
```

### 8.2 节点处理器

每个节点类型有对应的处理器：

```python
class NodeHandler:
    async def execute(self, config: dict, context: dict) -> dict:
        """执行节点，返回输出"""
        raise NotImplementedError

class HotspotScanHandler(NodeHandler):
    async def execute(self, config, context):
        from cn_social_agent.tools.hotspots import tool_scan_hotspot_board
        
        result = await tool_scan_hotspot_board(
            per_page=config.get("limit", 5),
            source=config.get("source", "all"),
        )
        
        return {
            "hotspots": result.get("board", []),
            "count": len(result.get("board", []))
        }

class LLMGenerateHandler(NodeHandler):
    async def execute(self, config, context):
        # 使用现有 LLM 路由
        prompt = self.render_template(config["prompt"], context)
        
        result = await call_llm(
            prompt=prompt,
            model_route=config.get("model", "smart"),
            max_tokens=config.get("maxLength", 1000),
        )
        
        return {"text": result}

class ConditionHandler(NodeHandler):
    async def execute(self, config, context):
        expression = config["expression"]
        
        # 简单表达式求值
        result = self.evaluate(expression, context)
        
        return {"result": result, "branch": "true" if result else "false"}
```

### 8.3 节点复制/粘贴

复制节点时，自动处理：
1. 生成新 ID（避免冲突）
2. 偏移位置（避免重叠）
3. 保留配置

```python
def copy_nodes(self, nodes: list[WorkflowNode], offset: dict = None) -> list[WorkflowNode]:
    """复制节点列表"""
    if offset is None:
        offset = {"x": 40, "y": 40}
    
    new_nodes = []
    for node in nodes:
        new_node = WorkflowNode(
            id=f"node_{uuid.uuid4().hex[:8]}",
            type=node.type,
            position={
                "x": node.position["x"] + offset["x"],
                "y": node.position["y"] + offset["y"],
            },
            config=deep_copy(node.config),
            label=f"{node.label} (copy)" if node.label else None,
        )
        new_nodes.append(new_node)
    
    return new_nodes
```

**复制连线：**
- 如果复制的节点之间有连线，且连线两端节点都被复制，则自动创建新连线
- 如果只复制了连线一端的节点，则不复制该连线

### 8.4 上下文传递

节点输出会合并到运行上下文，供下游节点使用：

```python
def propagate_output(self, node_id: str, output: dict, run: WorkflowRun):
    """将节点输出传递到上下文"""
    # 使用节点 ID 作为命名空间
    run.context[node_id] = output
    
    # 同时设置一个简洁的引用（取第一个输出值）
    if output:
        first_key = next(iter(output))
        run.context[f"${node_id}"] = output[first_key]
```

模板语法：
```markdown
根据热点「{{scan_node.title}}」生成内容。
热度分数：{{scan_node.score}}
```

## 9. Implementation Plan

### Phase 1: 后端基础 (2-3 days)

| 任务 | 说明 |
|------|------|
| 数据模型 | Workflow / WorkflowRun 表结构 |
| CRUD API | 工作流增删改查 |
| 存储层 | InsForge DB / 本地 JSON fallback |

### Phase 2: 节点编辑器 (5-7 days)

| 任务 | 说明 |
|------|------|
| SVG 画布 | 基础画布 + 缩放/平移 |
| 节点渲染 | 不同类型节点的 SVG 绘制 |
| 拖拽交互 | 从面板拖入画布 |
| 连线 | 输出口到输入口的连线 |
| 选中/配置 | 点击节点显示配置面板 |
| 状态可视化 | 运行时节点状态指示 |

### Phase 3: 执行引擎 (3-4 days)

| 任务 | 说明 |
|------|------|
| 拓扑排序 | 节点执行顺序计算 |
| 节点处理器 | 各类型节点的 execute 实现 |
| 上下文传递 | 节点间数据传递 |
| 错误处理 | 失败重试、继续/终止策略 |
| 定时触发 | Cron 调度器 |

### Phase 4: 集成与模板 (2-3 days)

| 任务 | 说明 |
|------|------|
| 预设模板 | 3-5 个常用工作流 |
| 与现有功能集成 | 热点/LLM/视频/发布模块 |
| 运行历史 | 执行记录 UI |

### Phase 5: 打磨 (1-2 days)

| 任务 | 说明 |
|------|------|
| 暗色模式 | 跟随系统主题 |
| 快捷键 | Ctrl+S 保存、Delete 删除、Ctrl+Z 撤销等 |
| 导入/导出 | JSON 格式工作流 |
| 撤销/重做 | 编辑历史管理 |
| 节点复制粘贴 | Ctrl+C/V |
| 网格对齐 | 20px 网格自动吸附 |

**导入/导出格式（JSON）：**

```json
{
  "name": "每日热点生产线",
  "description": "扫描热点 → LLM 生成 → 保存项目",
  "nodes": [
    {
      "id": "node_1",
      "type": "trigger.schedule",
      "position": { "x": 100, "y": 100 },
      "config": { "cron": "0 9 * * *" }
    },
    {
      "id": "node_2",
      "type": "action.hotspot_scan",
      "position": { "x": 300, "y": 100 },
      "config": { "source": "all", "limit": 5 }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "node_1",
      "target": "node_2"
    }
  ],
  "trigger": {
    "type": "schedule",
    "config": { "cron": "0 9 * * *" }
  }
}
```

## 10. Testing

### 单元测试

- 工作流拓扑排序
- 节点处理器执行
- 上下文模板渲染
- 条件表达式求值

### 集成测试

- CRUD API 流程
- 工作流执行端到端
- 定时触发
- 错误恢复

### 手工测试

- 拖拽节点到画布
- 连线并运行
- 配置节点参数
- 查看运行历史

## 11. Risks

| Risk | Mitigation |
|------|------------|
| SVG 性能（大量节点） | 限制 v1 节点数 ≤ 50；使用 Canvas fallback |
| 定时触发可靠性 | 使用系统 cron + 心跳检测 |
| 节点处理器与现有模块耦合 | 通过 Handler 接口解耦 |
| 工作流 JSON 复杂度 | 提供模板 + 简化配置面板 |

## 12. Future Enhancements

- v2: 嵌套子工作流
- v2: 并行分支
- v2: 工作流市场
- v2: 实时日志流
- v3: 自定义节点（用户代码）
- v3: 工作流版本管理
