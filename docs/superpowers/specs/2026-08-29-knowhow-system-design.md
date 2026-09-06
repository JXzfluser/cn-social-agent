# Know-How 系统设计

> 基于 PARA + Zettelkasten 混合架构的个人知识管理系统

## 1. 背景与目标

### 1.1 当前痛点

| 功能 | 问题 |
|------|------|
| **主题资产** | 只读聚合，没有自有数据存储 |
| **项目** | 创作过程状态，不是沉淀的知识 |
| **学习** | 独立模块，未与内容创作关联 |

三者割裂：学习不会自动变成内容灵感，项目过程不会沉淀为经验，主题资产只是被动展示。

### 1.2 设计目标

**知识沉淀**：把学习、创作过程中的经验沉淀下来，下次遇到类似话题能快速复用。

### 1.3 理论基础

- **PARA** (Tiago Forte)：Projects → Areas → Resources → Archives
- **Zettelkasten** (Niklas Luhmann)：原子化笔记 + 双向链接
- **MOCs** (Maps of Content)：话题中心的索引页
- **Progressive Summarization**：分层提炼知识

## 2. 系统架构

### 2.1 混合架构

```
Know-How 系统
├── 📁 PARA 层（行动导向）
│   ├── Projects（进行中的创作）
│   ├── Areas（持续关注的领域：工作流改进）
│   ├── Resources（可复用的知识资源）
│   └── Archives（已完成的内容）
│
├── 🔗 Zettelkasten 层（思考导向）
│   ├── 原子化笔记（一个想法一条）
│   ├── 双向链接（笔记之间互相引用）
│   └── 标签系统（多维度分类）
│
└── 🗺️ MOC 层（话题中心）
    └── 每个话题一个 MOC 页，聚合相关知识
```

### 2.2 与现有功能映射

| 现有功能 | Know-How 位置 | 变化 |
|---------|--------------|------|
| 主题资产 | MOC (话题中心) | 从只读聚合变为知识中心 |
| 项目 | PARA Projects | 保留，增加经验沉淀 |
| 学习笔记 | PARA Resources + Zettelkasten | 融入，不再独立 Tab |
| 工作流记录 | PARA Areas | 保留，增强链接 |

## 3. 数据模型

### 3.1 Topic Hub (话题中心 = MOC)

```sql
CREATE TABLE wb_topic_hubs (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    topic_key TEXT NOT NULL,        -- 话题唯一标识
    topic TEXT NOT NULL,             -- 话题显示名
    summary TEXT,                    -- 一句话总结
    linked_topics JSONB DEFAULT '[]', -- 双向链接的话题
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(user_id, topic_key)
);
```

### 3.2 Notes (原子化笔记)

```sql
CREATE TABLE wb_topic_notes (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    topic_key TEXT NOT NULL,         -- 所属话题
    content TEXT NOT NULL,           -- 笔记内容
    source_type TEXT,                -- 来源类型：learning/research/workflow/manual
    tags JSONB DEFAULT '[]',         -- 标签：概念/实践/踩坑/灵感
    linked_notes JSONB DEFAULT '[]', -- 链接的其他笔记
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 3.3 Workflow Records (工作流记录)

```sql
CREATE TABLE wb_topic_workflows (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    topic_key TEXT NOT NULL,
    method TEXT,                     -- 方法名称
    what_worked TEXT,                -- 有效做法
    what_didnt_work TEXT,            -- 避免做法
    quality_rating INTEGER,          -- 质量评分 1-5
    duration_minutes INTEGER,        -- 耗时
    content_type TEXT,               -- 内容类型
    created_at TIMESTAMP
);
```

## 4. API 设计

### 4.1 话题中心 API

```
GET    /api/knowhow/topics              -- 获取所有话题列表
GET    /api/knowhow/{key}               -- 获取话题详情（含笔记、工作流、资产）
POST   /api/knowhow/{key}               -- 创建/更新话题
DELETE /api/knowhow/{key}               -- 删除话题
```

### 4.2 笔记 API

```
GET    /api/knowhow/{key}/notes         -- 获取话题下的笔记
POST   /api/knowhow/{key}/notes         -- 创建笔记
PATCH  /api/knowhow/notes/{id}          -- 更新笔记
DELETE /api/knowhow/notes/{id}          -- 删除笔记
```

### 4.3 工作流 API

```
GET    /api/knowhow/{key}/workflows     -- 获取工作流记录
POST   /api/knowhow/{key}/workflows     -- 创建工作流记录
```

### 4.4 链接 API

```
POST   /api/knowhow/{key}/link          -- 添加话题链接
DELETE /api/knowhow/{key}/link/{target} -- 删除话题链接
```

## 5. UI 设计

### 5.1 话题中心页

```
┌─────────────────────────────────────────────────┐
│ 🗺️ LangGraph 图编排                              │
│ "用有向图把 Agent 的多个步骤编排起来"              │
│                                                 │
│ 相关话题: [[状态管理]] [[工作流编排]] [[多Agent]]  │
├─────────────────────────────────────────────────┤
│                                                 │
│ 📝 知识笔记 (6)                                  │
│ ┌─────────────────────────────────────────────┐ │
│ │ • 状态图的核心是 State + Reducer (概念)       │ │
│ │ • 条件边可以实现动态路由 (实践)               │ │
│ │ • 踩坑：节点返回增量而非完整状态 (踩坑)       │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ 📋 工作流记录 (2)                                │
│ ┌─────────────────────────────────────────────┐ │
│ │ • 有效：多角度对比效果好                      │ │
│ │ • 避免：纯罗列不好                           │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ 📦 内容资产 (3)                                  │
│ • 知识卡片 x2  • 短视频 x1                      │
│                                                 │
│ [+ 添加笔记] [+ 记录工作流]                      │
└─────────────────────────────────────────────────┘
```

### 5.2 笔记编辑

- 支持 Markdown 格式
- 支持 `[[话题名]]` 语法创建双向链接
- 支持标签选择：概念/实践/踩坑/灵感

## 6. 实施路径

### Phase 1 (已完成): 基础 API + 表结构
- ✅ 研究笔记 CRUD
- ✅ 工作流记录 CRUD
- ✅ 学习洞察 CRUD
- ✅ 前端区域展示

### Phase 2: 增强数据模型
- [ ] 创建 wb_topic_hubs 表
- [ ] 增强 wb_topic_notes 支持双向链接
- [ ] 创建话题链接 API
- [ ] 迁移现有数据

### Phase 3: 话题中心页 UI
- [ ] 重构主题资产详情页为话题中心页
- [ ] 添加双向链接展示和编辑
- [ ] 添加标签系统
- [ ] 整合内容资产展示

### Phase 4: 智能关联
- [ ] 学习模块自动同步到话题中心
- [ ] 创作完成后自动提示记录工作流
- [ ] 基于链接的相关话题推荐

## 7. 成功标准

- [ ] 用户可以在话题中心添加原子化笔记
- [ ] 笔记之间可以建立双向链接
- [ ] 工作流经验可以沉淀并复用
- [ ] 学习内容与创作内容关联
- [ ] 话题之间形成知识图谱
