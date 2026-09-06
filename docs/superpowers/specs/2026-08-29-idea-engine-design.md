# Idea 引擎设计文档

> ⚠️ **状态声明（2026-08-30 更新）：** Idea 引擎保留在 Agent 右侧抽屉，但整体 UI 结构已改为左侧导航栏模式（顶栏删除、主侧栏统一）。UI 布局相关设计请以新结构为准。当前主线见 `docs/superpowers/plans/2026-08-30-knowhow-consolidation-migration.md`。

> 版本：v1.0  
> 日期：2026-08-29  
> 状态：设计阶段

## 一、概述

### 1.1 问题

当前内容创作的起点不清晰：
- 热点扫描只提供「发生了什么」，不提供「我值得做什么」
- 用户需要手动从热点中筛选、加工、变成可执行的选题
- 缺乏系统化的 idea 生成机制

### 1.2 目标

建立一个 **Idea 引擎**，实现：
- 多源素材自动汇聚
- AI 自动加工成选题
- 用户快速决策「做哪个」

### 1.3 设计原则

1. **连接器模式**：借鉴 OpenWorkBuddy 的 Connectors 架构，每个数据源是独立连接器
2. **本地优先**：数据不出本机，API Key 本地存储
3. **AI 加工**：素材 → AI 筛选 → 选题卡片
4. **可组合**：连接器可任意组合，按需启用

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Idea 引擎架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 连接器层（Connectors）                   │   │
│  │                                                         │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │ GitHub  │ │ HN API  │ │ V2EX    │ │ 少数派  │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │   │
│  │  │ 知乎    │ │ 小红书  │ │ 抖音    │ │ 公众号  │     │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                  │   │
│  │  │ 竞品监控│ │ 评论区  │ │ 知识库  │                  │   │
│  │  └─────────┘ └─────────┘ └─────────┘                  │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 素材池（Raw Materials）                  │   │
│  │                                                         │   │
│  │  统一格式：{ source, title, url, summary, tags, time } │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 AI 加工层（Processor）                   │   │
│  │                                                         │   │
│  │  · 相关性筛选：与用户领域相关吗？                       │   │
│  │  · 时效性判断：现在做还来得及吗？                       │   │
│  │  · 差异化分析：能提供什么独特视角？                     │   │
│  │  · 选题生成：标题 + Hook + 角度 + 难度                 │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 选题队列（Idea Queue）                   │   │
│  │                                                         │   │
│  │  · 按优先级排序                                         │   │
│  │  · 用户决策：做这个 / 推迟 / 放弃                       │   │
│  │  · 进入创作流程                                         │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 连接器标准

借鉴 OpenWorkBuddy 的 Agent Plugins 1.0.0 标准：

```typescript
interface IdeaConnector {
  // 连接器元信息
  id: string;
  name: string;
  description: string;
  icon: string;
  
  // 连接器能力
  capabilities: {
    source: boolean;      // 是否提供素材
    monitor: boolean;     // 是否支持监控
    realtime: boolean;    // 是否实时更新
  };
  
  // 核心方法
  fetch(): Promise<RawMaterial[]>;           // 获取素材
  monitor?(callback: (material: RawMaterial) => void): void;  // 监控更新
  configure?(config: ConnectorConfig): void; // 配置连接器
}

interface RawMaterial {
  source: string;      // 来源标识
  title: string;       // 标题
  url: string;         // 原文链接
  summary: string;     // 摘要
  tags: string[];      // 标签
  heat: number;        // 热度值
  timestamp: number;   // 发布时间
  metadata: Record<string, any>;  // 扩展字段
}

interface IdeaCard {
  id: string;
  title: string;           // 选题标题
  hook: string;            // 一句话 hook
  angles: string[];        // 可选角度
  source: RawMaterial;     // 原始素材
  heatScore: number;       // 热度评分 0-100
  difficultyScore: number; // 难度评分 0-100
  timeWindow: string;      // 时间窗口
  status: 'pending' | 'selected' | 'rejected' | 'expired';
  createdAt: number;
}
```

---

## 三、连接器详细设计

### 3.1 GitHub Trending 连接器

```typescript
class GitHubTrendingConnector implements IdeaConnector {
  id = 'github-trending';
  name = 'GitHub 热门';
  description = '追踪 GitHub Trending 项目';
  
  capabilities = {
    source: true,
    monitor: true,
    realtime: true
  };
  
  async fetch(): Promise<RawMaterial[]> {
    // 抓取 GitHub Trending 页面
    // 解析项目列表
    // 返回统一格式素材
  }
  
  monitor(callback) {
    // 定时轮询（每小时）
    // 发现新项目时触发回调
  }
}
```

**素材加工规则：**
- 检测项目描述中的关键词
- 分析 Star 增长速度
- 识别技术栈和应用场景

### 3.2 Hacker News 连接器

```typescript
class HackerNewsConnector implements IdeaConnector {
  id = 'hacker-news';
  name = 'Hacker News';
  description = '追踪 HN 热门帖子';
  
  async fetch(): Promise<RawMaterial[]> {
    // 调用 HN API
    // 获取 Top Stories
    // 解析讨论热度
  }
}
```

**素材加工规则：**
- 分析标题中的技术关键词
- 检测讨论数量和质量
- 识别争议性话题

### 3.3 V2EX 连接器

```typescript
class V2EXConnector implements IdeaConnector {
  id = 'v2ex';
  name = 'V2EX';
  description = '追踪 V2EX 热门讨论';
  
  async fetch(): Promise<RawMaterial[]> {
    // 调用 V2EX API
    // 获取热门节点和话题
    // 分析技术社区关注点
  }
}
```

### 3.4 少数派连接器

```typescript
class SspaiConnector implements IdeaConnector {
  id = 'sspai';
  name = '少数派';
  description = '追踪少数派热门文章';
  
  async fetch(): Promise<RawMaterial[]> {
    // 抓取少数派首页
    // 解析热门文章
    // 分析效率工具类话题
  }
}
```

### 3.5 知乎热榜连接器

```typescript
class ZhihuConnector implements IdeaConnector {
  id = 'zhihu';
  name = '知乎热榜';
  description = '追踪知乎热门问题';
  
  async fetch(): Promise<RawMaterial[]> {
    // 抓取知乎热榜
    // 分析高赞回答
    // 识别知识类话题
  }
}
```

### 3.6 竞品监控连接器

```typescript
class CompetitorMonitorConnector implements IdeaConnector {
  id = 'competitor-monitor';
  name = '竞品监控';
  description = '监控对标账号的内容动态';
  
  private accounts: CompetitorAccount[] = [];
  
  async fetch(): Promise<RawMaterial[]> {
    // 获取所有对标账号的最新内容
    // 分析内容主题和热度
    // 识别差异化机会
  }
  
  addAccount(account: CompetitorAccount) {
    // 添加对标账号
  }
}

interface CompetitorAccount {
  platform: 'wechat' | 'toutiao' | 'xiaohongshu' | 'douyin';
  accountId: string;
  accountName: string;
  category: string;
}
```

### 3.7 用户痛点连接器

```typescript
class PainPointConnector implements IdeaConnector {
  id = 'pain-points';
  name = '用户痛点';
  description = '从评论区和问答社区挖掘用户需求';
  
  async fetch(): Promise<RawMaterial[]> {
    // 抓取历史内容的评论区
    // 分析高频问题
    // 提取用户痛点
  }
  
  // 分析评论中的痛点
  private analyzePainPoints(comments: string[]): PainPoint[] {
    // 使用 AI 提取痛点
    // 统计出现频率
    // 分类整理
  }
}
```

### 3.8 知识库连接器

```typescript
class KnowledgeBaseConnector implements IdeaConnector {
  id = 'knowledge-base';
  name = '知识库';
  description = '从已有素材中发现可复用的 idea';
  
  async fetch(): Promise<RawMaterial[]> {
    // 扫描用户的知识库
    // 识别可复用的素材
    // 关联当前热点
  }
}
```

---

## 四、AI 加工层设计

### 4.1 加工流程

```
原始素材 → 相关性筛选 → 时效性判断 → 差异化分析 → 选题生成
```

### 4.2 Prompt 设计

```typescript
const IDEA_GENERATION_PROMPT = `
你是一个内容选题专家。根据以下原始素材，生成一个内容选题。

原始素材：
- 标题：{title}
- 摘要：{summary}
- 来源：{source}
- 热度：{heat}
- 标签：{tags}

请生成：
1. 选题标题（吸引眼球，15字以内）
2. 一句话 hook（为什么值得做）
3. 2-3 个可选角度
4. 预估热度（1-5星）
5. 制作难度（1-5星）
6. 时间窗口（24h/48h/1周/不限）

输出格式：
{
  "title": "...",
  "hook": "...",
  "angles": ["...", "...", "..."],
  "heatScore": 4,
  "difficultyScore": 3,
  "timeWindow": "48h"
}
`;
```

### 4.3 筛选规则

```typescript
interface FilterRules {
  // 相关性规则
  relevance: {
    keywords: string[];      // 用户领域关键词
    excludeKeywords: string[]; // 排除关键词
    minScore: number;        // 最低相关性分数
  };
  
  // 时效性规则
  timeliness: {
    maxAge: number;          // 最大素材年龄（小时）
    priorityPlatforms: string[]; // 优先平台
  };
  
  // 差异化规则
  differentiation: {
    avoidTopics: string[];   // 避免的话题（已有内容）
    targetAngles: string[];  // 目标角度
  };
}
```

---

## 五、UI 设计

### 5.1 素材面板

```
┌──────────────────────────────────────────────────────┐
│  📡 素材来源                                         │
│                                                      │
│  ✅ GitHub Trending     [配置] [暂停]                │
│  ✅ Hacker News         [配置] [暂停]                │
│  ✅ V2EX                [配置] [暂停]                │
│  ☐ 知乎热榜             [启用]                       │
│  ☐ 竞品监控             [配置]                       │
│  ☐ 用户痛点             [配置]                       │
│                                                      │
│  ─────────────────────────────────────────────────── │
│                                                      │
│  📥 今日素材（23 条）                                │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 🔥 Project X - 1 天 3000 star                  │ │
│  │    GitHub │ 2 小时前 │ [查看详情] [生成选题]    │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 💬 如何评价 XX 框架？                           │ │
│  │    V2EX │ 5 小时前 │ [查看详情] [生成选题]      │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  [刷新素材] [清空已读]                              │
└──────────────────────────────────────────────────────┘
```

### 5.2 选题队列

```
┌──────────────────────────────────────────────────────┐
│  💡 选题队列（5 个待处理）                           │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 🔥 #1  这个项目为什么 1 天 3000 star？          │ │
│  │    来源：GitHub │ 热度：⭐⭐⭐⭐⭐              │ │
│  │    窗口：24h │ 难度：⭐⭐⭐                     │ │
│  │    Hook：不只是技术牛，更是因为它解决了 XXX     │ │
│  │                                                 │ │
│  │    角度：                                       │ │
│  │    · 技术解读：它是怎么做到的？                 │ │
│  │    · 热点蹭：现在做内容来得及                   │ │
│  │    · 痛点切入：它解决了什么问题？               │ │
│  │                                                 │ │
│  │    [✅ 做这个] [📌 收藏] [❌ 跳过]             │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ 📌 #2  XX 配置避坑指南                          │ │
│  │    来源：用户痛点 │ 热度：⭐⭐⭐⭐              │ │
│  │    窗口：1 周 │ 难度：⭐⭐                      │ │
│  │    Hook：评论区 23 人在问这个问题               │ │
│  │                                                 │ │
│  │    [✅ 做这个] [📌 收藏] [❌ 跳过]             │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 5.3 灵感碎片

```
┌──────────────────────────────────────────────────────┐
│  💭 灵感碎片                                          │
│                                                      │
│  快速记录你看到的、想到的：                            │
│                                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ [输入框：一句话、一个链接、一张截图]            │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  AI 自动：                                           │
│  · 识别类型（技术/观点/案例/问题）                   │
│  · 关联已有素材                                      │
│  · 生成选题建议                                      │
│                                                      │
│  ─────────────────────────────────────────────────── │
│                                                      │
│  📝 我的碎片（12 条）                                │
│                                                      │
│  · 「看到一个 XX 用法，可以做个教程」 → 已生成选题   │
│  · 「评论区都在问 XX，这是个痛点」 → 待处理          │
│  · 「XX 好像要出新版本了，提前准备」 → 已收藏        │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 六、数据流设计

### 6.1 素材采集流程

```
┌─────────────┐
│  定时任务   │
│  (每小时)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  遍历连接器 │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  fetch()    │
│  获取素材   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  去重检查   │
│  (URL 去重) │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  存入素材池 │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  AI 加工    │
│  生成选题   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  入选题队列 │
└─────────────┘
```

### 6.2 选题生成流程

```
┌─────────────┐
│  原始素材   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  相关性筛选 │
│  (关键词)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  时效性判断 │
│  (时间窗口) │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  差异化分析 │
│  (竞品对比) │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  AI 生成    │
│  选题卡片   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  人工审核   │
│  (做/收藏/  │
│   跳过)     │
└─────────────┘
```

---

## 七、存储设计

### 7.1 数据表

```sql
-- 素材表
CREATE TABLE wb_idea_materials (
  id UUID PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  connector_id VARCHAR NOT NULL,
  source VARCHAR NOT NULL,
  title TEXT NOT NULL,
  url TEXT,
  summary TEXT,
  tags JSONB DEFAULT '[]',
  heat INTEGER DEFAULT 0,
  raw_data JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  processed BOOLEAN DEFAULT FALSE
);

-- 选题表
CREATE TABLE wb_idea_cards (
  id UUID PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  material_id UUID REFERENCES wb_idea_materials(id),
  title TEXT NOT NULL,
  hook TEXT,
  angles JSONB DEFAULT '[]',
  heat_score INTEGER DEFAULT 0,
  difficulty_score INTEGER DEFAULT 0,
  time_window VARCHAR,
  status VARCHAR DEFAULT 'pending',  -- pending/selected/rejected/expired
  created_at TIMESTAMP DEFAULT NOW(),
  selected_at TIMESTAMP
);

-- 灵感碎片表
CREATE TABLE wb_idea_fragments (
  id UUID PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  content TEXT NOT NULL,
  fragment_type VARCHAR,  -- text/url/image
  auto_tags JSONB DEFAULT '[]',
  related_material_id UUID,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 连接器配置表
CREATE TABLE wb_idea_connectors (
  id UUID PRIMARY KEY,
  user_id VARCHAR NOT NULL,
  connector_id VARCHAR NOT NULL,
  config JSONB DEFAULT '{}',
  enabled BOOLEAN DEFAULT TRUE,
  last_sync_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 八、API 设计

### 8.1 连接器管理

```
GET    /api/idea/connectors              # 获取可用连接器列表
POST   /api/idea/connectors/:id/config   # 配置连接器
PUT    /api/idea/connectors/:id/toggle   # 启用/禁用连接器
GET    /api/idea/connectors/:id/status   # 获取连接器状态
```

### 8.2 素材管理

```
GET    /api/idea/materials               # 获取素材列表
POST   /api/idea/materials/refresh       # 手动刷新素材
DELETE /api/idea/materials/:id           # 删除素材
POST   /api/idea/materials/:id/generate  # 从素材生成选题
```

### 8.3 选题管理

```
GET    /api/idea/cards                   # 获取选题列表
PUT    /api/idea/cards/:id/select        # 选择选题（进入创作）
PUT    /api/idea/cards/:id/reject        # 拒绝选题
PUT    /api/idea/cards/:id/archive       # 收藏选题
GET    /api/idea/cards/:id/detail        # 获取选题详情
```

### 8.4 灵感碎片

```
GET    /api/idea/fragments               # 获取碎片列表
POST   /api/idea/fragments               # 添加碎片
DELETE /api/idea/fragments/:id           # 删除碎片
POST   /api/idea/fragments/:id/generate  # 从碎片生成选题
```

---

## 九、与现有系统的集成

### 9.1 与项目系统集成

```
选题 → 创建项目 → 自动关联
         ↓
    项目详情页显示「选题来源」
```

### 9.2 与画布系统集成

```
选题 → 进入研究阶段 → 画布自动创建
         ↓
    画布显示「选题信息」
```

### 9.3 与工作流系统集成

```
选题 → 触发自动化工作流
         ↓
    工作流自动执行（爬虫 → 分析 → 生成）
```

---

## 十、实施计划

### Phase 1：核心连接器（2 周）

- [ ] 实现连接器基础框架
- [ ] GitHub Trending 连接器
- [ ] Hacker News 连接器
- [ ] V2EX 连接器
- [ ] AI 加工层基础功能
- [ ] 选题队列 UI

### Phase 2：扩展连接器（2 周）

- [ ] 少数派连接器
- [ ] 知乎热榜连接器
- [ ] 竞品监控连接器
- [ ] 灵感碎片功能

### Phase 3：深度集成（2 周）

- [ ] 用户痛点连接器
- [ ] 知识库连接器
- [ ] 与项目系统集成
- [ ] 与画布系统集成

### Phase 4：优化迭代（持续）

- [ ] AI 筛选规则优化
- [ ] 连接器性能优化
- [ ] 用户反馈迭代

---

## 十一、技术栈

| 组件 | 技术选型 |
|------|---------|
| 连接器框架 | TypeScript + Node.js |
| 数据抓取 | Puppeteer / Cheerio |
| AI 加工 | OpenAI API / 本地模型 |
| 存储 | InsForge (PostgreSQL) |
| 前端 | React + Tailwind CSS |
| 定时任务 | node-cron |

---

## 十二、深度评审

### 12.1 创新点分析

| 创新点 | 竞品现状 | 我们的差异化 | 用户价值 |
|--------|---------|-------------|---------|
| **连接器模式** | 大多是单一数据源 | 多源汇聚 + 可插拔 | 一个入口看所有素材 |
| **AI 加工层** | 只展示原始热点 | 素材 → 选题卡片 | 不用自己筛选加工 |
| **选题队列** | 无优先级管理 | 按热度/时效排序 | 快速决策做哪个 |
| **灵感碎片** | 无快速捕获 | 一句话记录 + AI 整理 | 灵感不丢失 |
| **竞品监控** | 无差异化分析 | 对标账号 + 差异机会 | 找到蓝海话题 |
| **痛点挖掘** | 无用户需求分析 | 评论区 + 问答社区 | 做用户真正需要的 |

### 12.2 用户体验设计

#### 12.2.1 首次使用引导

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  👋 欢迎使用 Idea 引擎                                      │
│                                                             │
│  让我们帮你找到值得做的内容                                  │
│                                                             │
│  Step 1: 选择你的领域                                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│  │ 技术    │ │ 产品    │ │ 设计    │ │ 商业    │         │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘         │
│                                                             │
│  Step 2: 添加数据源                                         │
│  ✅ GitHub Trending（推荐）                                 │
│  ✅ Hacker News（推荐）                                     │
│  ☐ V2EX                                                    │
│  ☐ 知乎                                                    │
│                                                             │
│  Step 3: 设置关键词（可选）                                 │
│  [React] [Node.js] [AI] [效率工具]                         │
│                                                             │
│  [开始采集素材 →]                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 12.2.2 日常使用流程

```
每日打开 → 查看新素材 → 选择选题 → 进入创作
   │            │            │           │
   │            │            │           └── 自动创建项目
   │            │            └── AI 生成选题卡片
   │            └── 多源素材自动汇聚
   └── 灵感碎片随手记
```

#### 12.2.3 交互设计细节

**素材卡片交互：**
- 悬停显示详情
- 点击展开 AI 分析
- 左滑：跳过
- 右滑：生成选题
- 上滑：收藏

**选题卡片交互：**
- 点击「做这个」→ 自动创建项目 + 进入画布
- 点击「收藏」→ 保存到选题库
- 点击「跳过」→ 标记为已处理
- 长按：编辑选题

### 12.3 与现有系统深度集成

#### 12.3.1 与 Agent 系统集成

```
┌─────────────────────────────────────────────────────────────┐
│  Agent 对话中直接调用 Idea 引擎                              │
│                                                             │
│  用户：帮我找一些关于 React 的选题                           │
│                                                             │
│  Agent：                                                    │
│  我从 GitHub Trending 找到了 3 个相关项目：                 │
│                                                             │
│  1. 🔥 Project X - React 新状态管理库                       │
│     1 天 2000 star，解决 XXX 问题                          │
│     [生成选题] [查看详情]                                   │
│                                                             │
│  2. 💡 Project Y - React 性能优化工具                       │
│     3 天 500 star，主打 XXX 特性                           │
│     [生成选题] [查看详情]                                   │
│                                                             │
│  3. 📌 Project Z - React 组件库                            │
│     1 周 1000 star，面向 XXX 场景                          │
│     [生成选题] [查看详情]                                   │
│                                                             │
│  要我帮你生成选题吗？                                       │
└─────────────────────────────────────────────────────────────┘
```

#### 12.3.2 与项目系统集成

```
选题 → 创建项目时自动填充：
  · 项目标题 = 选题标题
  · 项目描述 = 选题 Hook
  · 项目来源 = 素材链接
  · 项目标签 = 素材标签

项目详情页显示：
  ┌─────────────────────────────────────────┐
  │  📋 项目信息                            │
  │                                         │
  │  标题：这个项目为什么 1 天 3000 star？  │
  │  来源：[GitHub Trending 原文]           │
  │  选题时间：2026-08-29 10:30             │
  │  选题热度：⭐⭐⭐⭐⭐                   │
  │                                         │
  │  [查看原始素材] [编辑选题]              │
  └─────────────────────────────────────────┘
```

#### 12.3.3 与画布系统集成

```
选择选题后 → 自动在画布创建节点：
  · 选题节点（标题 + Hook）
  · 原始素材节点（链接 + 摘要）
  · 相关素材节点（AI 推荐）

画布显示：
  ┌─────────────────────────────────────────┐
  │                                         │
  │  [选题] ────── [原始素材]              │
  │     │              │                    │
  │     └────── [相关素材1]                │
  │     │              │                    │
  │     └────── [相关素材2]                │
  │                                         │
  └─────────────────────────────────────────┘
```

#### 12.3.4 与工作流系统集成

```
选题 → 触发自动化工作流：

工作流 1：深度研究
  触发：用户选择选题
  执行：
    1. 爬取原始文章全文
    2. 搜索相关内容
    3. AI 生成研究摘要
    4. 更新画布节点

工作流 2：内容生成
  触发：用户完成研究
  执行：
    1. 基于研究资料
    2. AI 生成初稿
    3. 自动排版
    4. 输出草稿

工作流 3：发布准备
  触发：用户完成创作
  执行：
    1. 适配各平台格式
    2. 生成封面图
    3. 准备发布文案
    4. 排期建议
```

### 12.4 商业化考量

#### 12.4.1 免费版 vs 付费版

| 功能 | 免费版 | 付费版 |
|------|--------|--------|
| 连接器数量 | 3 个 | 无限 |
| 每日素材采集 | 50 条 | 无限 |
| AI 加工次数 | 10 次/天 | 无限 |
| 竞品监控 | 1 个账号 | 无限 |
| 灵感碎片 | 20 条 | 无限 |
| 选题历史 | 7 天 | 永久 |
| 数据导出 | ❌ | ✅ |

#### 12.4.2 增值服务

```
┌─────────────────────────────────────────────────────────────┐
│  💎 增值服务                                                │
│                                                             │
│  1. AI 选题优化（¥99/月）                                   │
│     · 更精准的选题推荐                                      │
│     · 竞品深度分析                                          │
│     · 爆款模式识别                                          │
│                                                             │
│  2. 高级连接器（¥49/月）                                    │
│     · 小红书热榜                                            │
│     · 抖音热点                                              │
│     · 公众号监控                                            │
│                                                             │
│  3. 团队协作（¥199/月）                                     │
│     · 多人共享选题库                                        │
│     · 选题审批流程                                          │
│     · 数据看板                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 12.5 风险分析

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| **数据源反爬** | 高 | 高 | 多代理池 + 限速 + API 优先 |
| **AI 生成质量不稳定** | 中 | 高 | 人工审核 + 反馈优化 |
| **用户使用频率低** | 中 | 中 | 每日推送 + 习惯培养 |
| **竞品跟进** | 高 | 中 | 持续创新 + 深度集成 |
| **隐私合规** | 低 | 高 | 本地优先 + 数据加密 |

#### 12.5.1 数据源反爬风险

**当前状态：**
- GitHub Trending：页面抓取，有反爬机制
- Hacker News：官方 API，稳定
- V2EX：官方 API，稳定
- 少数派：页面抓取，可能被封

**应对措施：**
1. **API 优先**：优先使用官方 API
2. **多代理池**：轮换 IP 地址
3. **限速控制**：每分钟不超过 10 次请求
4. **缓存机制**：相同内容 24h 内不重复抓取
5. **降级方案**：抓取失败时使用缓存数据

#### 12.5.2 AI 生成质量风险

**当前状态：**
- AI 生成的选题可能不够精准
- Hook 可能不够吸引人
- 角度可能不够独特

**应对措施：**
1. **人工审核**：所有选题需要用户确认
2. **反馈机制**：用户可以标记「好/坏」选题
3. **持续优化**：基于反馈调整 Prompt
4. **多模型对比**：使用多个 AI 模型生成，选择最佳

### 12.6 竞品差异化

#### 12.6.1 vs Notion Content Pipeline

| 维度 | Notion | 我们 |
|------|--------|------|
| **入口** | 手动创建数据库 | 自动采集素材 |
| **筛选** | 人工筛选 | AI 自动筛选 |
| **加工** | 手动填写属性 | AI 自动生成选题 |
| **监控** | 无 | 实时监控更新 |
| **集成** | 需要手动配置 | 与创作流程深度集成 |

**我们的优势：**
- 更自动化，减少手动操作
- AI 帮用户做 80% 的工作
- 与创作流程无缝衔接

#### 12.6.2 vs Buffer/Hootsuite

| 维度 | Buffer | 我们 |
|------|--------|------|
| **定位** | 发布工具 | 创作工具 |
| **Idea 来源** | 无 | 多源采集 |
| **内容生产** | 不涉及 | AI 辅助创作 |
| **数据分析** | 发布后分析 | 选题前分析 |

**我们的优势：**
- 覆盖完整创作流程
- 不只是发布，还有生产
- 数据驱动选题决策

#### 12.6.3 vs n8n/Make

| 维度 | n8n | 我们 |
|------|-----|------|
| **定位** | 通用自动化 | 内容创作专用 |
| **使用门槛** | 需要技术背景 | 零门槛 |
| **预置模板** | 通用 | 内容创作专用 |
| **AI 能力** | 需要自己配置 | 内置 AI 加工 |

**我们的优势：**
- 更垂直，更专业
- 开箱即用，无需配置
- AI 原生，不是后加的

### 12.7 实施细节

#### 12.7.1 连接器开发规范

```typescript
// 连接器模板
export class MyConnector implements IdeaConnector {
  id = 'my-connector';
  name = '我的连接器';
  description = '描述这个连接器做什么';
  icon = '🔗';
  
  capabilities = {
    source: true,      // 是否提供素材
    monitor: true,     // 是否支持监控
    realtime: false    // 是否实时更新
  };
  
  private config: ConnectorConfig;
  
  constructor(config: ConnectorConfig) {
    this.config = config;
  }
  
  async fetch(): Promise<RawMaterial[]> {
    // 1. 获取数据
    const data = await this.fetchData();
    
    // 2. 转换格式
    const materials = this.transform(data);
    
    // 3. 返回结果
    return materials;
  }
  
  monitor(callback: (material: RawMaterial) => void): void {
    // 1. 设置定时器
    setInterval(async () => {
      const materials = await this.fetch();
      materials.forEach(callback);
    }, this.config.interval || 3600000); // 默认 1 小时
  }
  
  private async fetchData(): Promise<any[]> {
    // 实现数据获取逻辑
    throw new Error('Not implemented');
  }
  
  private transform(data: any[]): RawMaterial[] {
    // 实现数据转换逻辑
    throw new Error('Not implemented');
  }
}
```

#### 12.7.2 AI 加工 Prompt 模板

```typescript
export const IDEA_GENERATION_PROMPTS = {
  // 技术类选题
  technical: `
你是一个技术内容选题专家。根据以下技术热点，生成一个技术解读选题。

技术热点：
- 项目名称：{title}
- 项目描述：{description}
- Star 数量：{stars}
- 技术栈：{techStack}

请生成：
1. 选题标题（技术向，吸引开发者，15字以内）
2. 一句话 hook（为什么这个技术值得关注）
3. 2-3 个解读角度
4. 预估热度（1-5星）
5. 制作难度（1-5星）
6. 时间窗口（24h/48h/1周/不限）

输出格式：
{
  "title": "...",
  "hook": "...",
  "angles": ["...", "...", "..."],
  "heatScore": 4,
  "difficultyScore": 3,
  "timeWindow": "48h"
}
`,

  // 观点类选题
  opinion: `
你是一个观点内容选题专家。根据以下话题，生成一个观点输出选题。

话题：
- 原文标题：{title}
- 原文摘要：{summary}
- 讨论热度：{heat}

请生成：
1. 选题标题（观点鲜明，引发讨论，15字以内）
2. 一句话 hook（你的核心观点）
3. 2-3 个论证角度
4. 预估热度（1-5星）
5. 制作难度（1-5星）
6. 时间窗口（24h/48h/1周/不限）

输出格式：同上
`,

  // 教程类选题
  tutorial: `
你是一个教程内容选题专家。根据以下痛点，生成一个教程选题。

痛点：
- 用户问题：{question}
- 出现频率：{frequency}
- 相关技术：{tech}

请生成：
1. 选题标题（教程向，吸引学习者，15字以内）
2. 一句话 hook（能学到什么）
3. 2-3 个教学角度
4. 预估热度（1-5星）
5. 制作难度（1-5星）
6. 时间窗口（24h/48h/1周/不限）

输出格式：同上
`
};
```

#### 12.7.3 数据库迁移脚本

```sql
-- Idea 引擎数据表

-- 素材表
CREATE TABLE wb_idea_materials (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR NOT NULL,
  connector_id VARCHAR NOT NULL,
  source VARCHAR NOT NULL,
  title TEXT NOT NULL,
  url TEXT,
  summary TEXT,
  tags JSONB DEFAULT '[]',
  heat INTEGER DEFAULT 0,
  raw_data JSONB DEFAULT '{}',
  processed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_idea_materials_user ON wb_idea_materials(user_id);
CREATE INDEX idx_idea_materials_connector ON wb_idea_materials(connector_id);
CREATE INDEX idx_idea_materials_created ON wb_idea_materials(created_at DESC);

-- 选题表
CREATE TABLE wb_idea_cards (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR NOT NULL,
  material_id UUID REFERENCES wb_idea_materials(id),
  title TEXT NOT NULL,
  hook TEXT,
  angles JSONB DEFAULT '[]',
  heat_score INTEGER DEFAULT 0,
  difficulty_score INTEGER DEFAULT 0,
  time_window VARCHAR,
  status VARCHAR DEFAULT 'pending',
  project_id UUID,
  created_at TIMESTAMP DEFAULT NOW(),
  selected_at TIMESTAMP,
  rejected_at TIMESTAMP
);

-- 索引
CREATE INDEX idx_idea_cards_user ON wb_idea_cards(user_id);
CREATE INDEX idx_idea_cards_status ON wb_idea_cards(status);
CREATE INDEX idx_idea_cards_created ON wb_idea_cards(created_at DESC);

-- 灵感碎片表
CREATE TABLE wb_idea_fragments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR NOT NULL,
  content TEXT NOT NULL,
  fragment_type VARCHAR DEFAULT 'text',
  auto_tags JSONB DEFAULT '[]',
  related_material_id UUID,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_idea_fragments_user ON wb_idea_fragments(user_id);

-- 连接器配置表
CREATE TABLE wb_idea_connectors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR NOT NULL,
  connector_id VARCHAR NOT NULL,
  config JSONB DEFAULT '{}',
  enabled BOOLEAN DEFAULT TRUE,
  last_sync_at TIMESTAMP,
  sync_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, connector_id)
);

-- 索引
CREATE INDEX idx_idea_connectors_user ON wb_idea_connectors(user_id);

-- 选题库（收藏的选题）
CREATE TABLE wb_idea_library (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR NOT NULL,
  card_id UUID REFERENCES wb_idea_cards(id),
  tags JSONB DEFAULT '[]',
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_idea_library_user ON wb_idea_library(user_id);
```

---

## 十三、总结

### 13.1 核心价值

Idea 引擎解决了内容创作的起点问题：
- **从哪来**：多源素材自动汇聚
- **怎么筛**：AI 自动筛选加工
- **做哪个**：选题队列快速决策

### 13.2 差异化优势

1. **连接器模式**：可插拔、可扩展
2. **AI 原生**：不是后加 AI，而是 AI 驱动
3. **深度集成**：与创作流程无缝衔接
4. **本地优先**：数据安全、隐私合规

### 13.3 实施路径

```
Phase 1（2周）：核心连接器 + AI 加工 + 选题队列
    ↓
Phase 2（2周）：扩展连接器 + 灵感碎片
    ↓
Phase 3（2周）：深度集成 + 竞品监控
    ↓
Phase 4（持续）：优化迭代 + 用户反馈
```

### 13.4 成功指标

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| 日活用户 | 100+ | 登录统计 |
| 每日素材采集 | 500+ 条 | 数据库统计 |
| 选题生成率 | 30%+ | 素材 → 选题转化 |
| 选题采纳率 | 50%+ | 选题 → 创作转化 |
| 用户满意度 | 4.5+ | NPS 调研 |

---

## 十四、参考

- OpenWorkBuddy Connectors 架构
- n8n 节点设计模式
- Notion Content Pipeline 模型
- Buffer 内容日历设计
- CapCut Mate 自动化架构

---

## 十五、附录

### 15.1 术语表

| 术语 | 定义 |
|------|------|
| **连接器（Connector）** | 接入外部数据源的标准化模块 |
| **素材（Raw Material）** | 从数据源采集的原始信息 |
| **选题（Idea Card）** | 经过 AI 加工的可执行选题 |
| **灵感碎片（Fragment）** | 用户随手记录的想法 |
| **选题队列（Idea Queue）** | 待处理的选题列表 |
| **选题库（Idea Library）** | 收藏的选题存档 |

### 15.2 相关文档

- [内容工作台架构设计](./2026-07-26-insforge-agent-workbench-design.md)
- [短视频工作流设计](./2026-07-26-short-video-workshop-design.md)
- [工作流编辑器设计](./2026-08-26-workflow-editor-design.md)

