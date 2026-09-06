# CN-Social-Agent 产品需求文档 (PRD)

**版本**: v1.0
**日期**: 2026-06-10
**作者**: 产品团队
**状态**: 初稿

---

## 1. 产品概述

### 1.1 产品定位

CN-Social-Agent 是一款面向内容运营者的多平台社交媒体 AI Agent 框架，支持钉钉、飞书、企业微信、微信公众号、微博、小红书等主流平台的智能内容生成与发布。

### 1.2 核心价值

- **一稿多发**:一次创作，多平台适配发布
- **智能生成**: 基于 LLM 的内容创作与再利用
- **工作流自动化**: 从内容抓取到发布的完整自动化流程
- **团队协作**: 审核机制与多用户支持

### 1.3 目标用户

| 用户类型 | 使用场景 | 核心需求 |
|----------|----------|----------|
| 内容运营者 | 日常内容发布 | 高效创作、多平台发布 |
| 自媒体人 | 个人品牌运营 | 原创内容、风格统一 |
| 企业市场部 | 品牌推广 | 合规审核、数据分析 |
| MCN机构 | 矩阵运营 |批量管理、效率提升 |

---

## 2. 功能需求

### 2.1 高优先级需求

#### 2.1.1 流式响应支持

| 属性 | 内容 |
|------|------|
| **需求编号** | F-001 |
| **需求类型** | 功能增强 |
| **优先级** | P0 |
| **关联模块** | agent/core.py, llm/*.py |

**背景与问题**

当前 `run_stream()` 方法仅模拟字符延迟输出，非真正的流式响应。用户在等待生成内容时体验不佳，无法实时看到生成进度。

**功能描述**

集成各 LLM 厂商的流式 API（OpenAI SSE、Minimax 等），实现 Server-Sent Events 推送，支持实时显示生成进度。

**验收标准**

- [ ]首次响应时间 < 500ms
- [ ] 支持中断生成
- [ ] 支持打字机效果显示
- [ ] 错误时显示友好提示

**实现方案**

```python
# 1. LLMBase 新增流式接口
async def chat_stream(
    self,
    messages: list[dict[str, str]],
    tools: Optional[list[dict[str, Any]]] = None,
) -> AsyncIterator[str]:
    """流式响应接口"""
    raise NotImplementedError

# 2. 各厂商实现
class QwenLLM(LLMBase):
    async def chat_stream(self, messages, tools=None) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream('POST', self.BASE_URL, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith('data: '):
                        yield self._parse_chunk(line[6:])

# 3. Agent 集成
async def run_stream(self, user_input: str, session_id: str,
                     on_token: Callable[[str], Awaitable[None]]):
    async for chunk in self._llm.chat_stream(messages):
        await on_token(chunk)
```

---

#### 2.1.2 智能上下文管理

| 属性 | 内容 |
|------|------|
| **需求编号** | F-002 |
| **需求类型** | 功能增强 |
| **优先级** | P0 |
| **关联模块** | agent/context_engine.py, agent/memory.py |

**背景与问题**

当前上下文管理存在以下问题：
1. Token 估算不准确（中文/英文统一按字符/4计算）
2. 消息压缩仅做简单统计，未生成语义摘要
3. 长对话无法从中间状态恢复

**功能描述**

实现智能上下文窗口管理，包括准确的 Token 估算、LLM 驱动的语义摘要、多层级压缩策略。

**验收标准**

- [ ] 中文 Token 估算误差 < 10%
- [ ] 英文 Token 估算误差 < 5%
- [ ] 摘要内容保留核心语义
- [ ] 支持对话快照保存与恢复
- [ ] 上下文上限内100% 准确

**实现方案**

```python
class ContextEngine:
    def __init__(self, max_tokens: int = 8000,
                 tokenizer: Optional[Tokenizer] = None):
        self._max_tokens = max_tokens
        self._compression_level = "balanced"  # light/balanced/aggressive

    def estimate_tokens(self, messages: list[dict]) -> int:
        """中英文分开的 Token 估算"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            chinese = len(re.findall(r'[一-鿿]', content))
            english = len(content) - chinese
            total += english / 4 + chinese / 2
        return int(total) + len(messages) * 3

    async def summarize_with_llm(self, messages: list[dict],
                                  llm_callable: Callable) -> str:
        """使用 LLM 生成语义化摘要"""
        prompt = self._build_summary_prompt(messages)
        return (await llm_callable([{"role": "user", "content": prompt}]))

    def compress_multi_level(self, messages: list[dict],
                            level: str = "balanced") -> list[dict]:
        """分层压缩策略"""
        threshold_ratios = {"light": 0.8, "balanced": 0.6, "aggressive": 0.4}
        # ...
```

---

#### 2.1.3 Webhook 可靠性保障

| 属性 | 内容 |
|------|------|
| **需求编号** | F-003 |
| **需求类型** | 功能增强 |
| **优先级** | P0 |
| **关联模块** | webhook/server.py, webhook/handlers.py |

**背景与问题**

当前 Webhook 处理缺少以下可靠性保障：
- 消息重复接收
- 处理失败无重试
- 消息处理超时

**功能描述**

实现消息幂等性保证、确认机制、失败重试队列、超时保护。

**验收标准**

- [ ] 消息去重（基于 message_id）
- [ ] 处理失败自动重试（指数退避，最多3次）
- [ ] 超时保护（单消息处理 < 30s）
- [ ] 消息处理 Exactly-Once 语义

**实现方案**

```python
class ReliableWebhookHandler(WebhookHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._processed_ids: set[str] = set()
        self._retry_queue: asyncio.Queue = asyncio.Queue()
        self._timeout_seconds = 30

    async def handle(self, request: web.Request) -> Optional[Message]:
        payload = await request.read()
        message_id = self._extract_message_id(payload)

        # 幂等性检查
        if message_id in self._processed_ids:
            logger.info(f"Duplicate message: {message_id}")
            return None
        self._processed_ids.add(message_id)

        # 超时保护
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._process_message(payload)
        except asyncio.TimeoutError:
            await self._enqueue_retry(message_id, payload)
            raise

    async def _enqueue_retry(self, message_id: str, payload: bytes):
        """失败消息入队等待重试"""
        await self._retry_queue.put({
            "message_id": message_id,
            "payload": payload,
            "retry_count": 0,
            "next_retry_at": datetime.now()
        })
```

---

#### 2.1.4 多图发布优化

| 属性 | 内容 |
|------|------|
| **需求编号** | F-004 |
| **需求类型** | 功能增强 |
| **优先级** | P0 |
| **关联模块** | social/weibo.py, social/xiaohongshu.py |

**背景与问题**

当前微博发布仅支持单张图片，限制了内容表达形式。

**功能描述**

支持微博1-9 张图片批量上传，小红书支持 9 图+视频笔记。

**验收标准**

- [ ] 微博支持 1-9 张图片
- [ ] 小红书支持 9 图
- [ ] 批量上传并发控制
- [ ] 上传失败自动降级

**实现方案**

```python
class WeiboPublisher:
    MAX_IMAGES = 9

    async def upload_images_concurrent(self, image_paths: list[str]) -> list[ImageResult]:
        """并发上传多张图片"""
        semaphore = asyncio.Semaphore(3)  # 最多3个并发

        async def upload_one(path: str) -> ImageResult:
            async with semaphore:
                return await self._upload_single(path)

        tasks = [upload_one(p) for p in image_paths]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def publish_with_images(self, post: Post, images: list[str]) -> PublishResult:
        if len(images) > self.MAX_IMAGES:
            images = images[:self.MAX_IMAGES]  # 截断

        results = await self.upload_images_concurrent(images)
        image_ids = [r.image_id for r in results if not isinstance(r, Exception)]

        return await self._do_publish(post, image_ids=image_ids)
```

---

#### 2.1.5 敏感词动态管理

| 属性 | 内容 |
|------|------|
| **需求编号** | F-005 |
| **需求类型** | 新功能 |
| **优先级** | P0 |
| **关联模块** | verify/filter.py, config/ |

**背景与问题**

敏感词硬编码在代码中，无法动态更新，无法满足合规要求。

**功能描述**

敏感词库支持数据库存储，提供管理 API，支持分类和风险等级。

**验收标准**

- [ ] 敏感词数据库持久化
- [ ] 提供 CRUD API
- [ ] 支持敏感词分类（广告法/时政/低俗等）
- [ ] 支持风险等级（高/中/低）
- [ ] 匹配命中返回友好提示

**实现方案**

```python
class SensitiveWordManager:
    def __init__(self, db_path: str):
        self._init_db()

    def _init_db(self):
        """初始化敏感词表"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sensitive_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'general',
                risk_level TEXT DEFAULT 'medium',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def check(self, content: str) -> CheckResult:
        """内容检测"""
        found = []
        for row in self._conn.execute("SELECT word, category, risk_level FROM sensitive_words"):
            if row[0] in content:
                found.append({
                    "word": row[0],
                    "category": row[1],
                    "risk_level": row[2]
                })
        return CheckResult(has_violation=bool(found), violations=found)
```

---

### 2.2 中优先级需求

#### 2.2.1 多模型智能路由

| 属性 | 内容 |
|------|------|
| **需求编号** | F-006 |
| **需求类型** | 功能增强 |
| **优先级** | P1 |
| **关联模块** | llm/base.py, llm/models.py |

**功能描述**

实现模型能力注册表，根据任务类型自动路由，支持模型降级和熔断。

**验收标准**

- [ ] 支持配置多个 LLM 模型
- [ ]简单问答自动路由到轻量模型
- [ ] 复杂生成路由到高质量模型
- [ ] 模型失败自动降级
- [ ] 成本统计与优化建议

**实现方案**

```python
class ModelRouter:
    def __init__(self, models: dict[ModelTier, LLMBase]):
        self._models = models
        self._fallback_chains = {
            "qwen-premium": ["qwen-plus", "zhipu", "minimax"]
        }

    async def route(self, task: str, require_capabilities: list[str] = None) -> LLMBase:
        """根据任务复杂度选择模型"""
        if self._is_simple_task(task):
            return self._models[ModelTier.FAST]
        elif self._is_complex_task(task):
            return self._models[ModelTier.PREMIUM]
        return self._models[ModelTier.BALANCED]

    async def call_with_fallback(self, messages: list[dict],
                                 preferred_tier: ModelTier) -> LLMResponse:
        """带降级的模型调用"""
        for model_key in self._get_fallback_chain(preferred_tier):
            try:
                model = self._models.get(model_key)
                return await model.chat(messages)
            except Exception as e:
                logger.warning(f"Model {model_key} failed: {e}")
                continue
        raise LLMError("All models failed")
```

---

#### 2.2.2 批量任务编排

| 属性 | 内容 |
|------|------|
| **需求编号** | F-007 |
| **需求类型** | 功能增强 |
| **优先级** | P1 |
| **关联模块** | scheduler/scheduler.py, crawler/crawler.py |

**功能描述**

支持批量 URL 输入、内容池管理、定时任务可视化编排、任务依赖控制。

**验收标准**

- [ ]批量 URL导入（CSV/TXT）
- [ ] 内容去重检测
- [ ] 定时任务可视化配置
- [ ] 任务执行状态实时展示
- [ ] 任务依赖与执行顺序控制

**实现方案**

```python
@dataclass
class BatchTask:
    task_id: str
    sources: list[ContentSource]  # URL列表
    platforms: list[str]
    schedule_config: ScheduleConfig
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)

class BatchTaskExecutor:
    async def execute(self, task: BatchTask) -> BatchResult:
        # 1. 内容抓取
        contents = await self._crawl_batch(task.sources)

        # 2. 去重检测
        unique_contents = self._dedup(contents)

        # 3. 内容处理
        processed = []
        for content in unique_contents:
            result = await self._process_content(content)
            processed.append(result)

        # 4. 发布
        return await self._publish_to_platforms(processed, task.platforms)
```

---

#### 2.2.3 跨平台内容适配

| 属性 | 内容 |
|------|------|
| **需求编号** | F-008 |
| **需求类型** | 功能增强 |
| **优先级** | P1 |
| **关联模块** | social/publisher.py, repurposer/repurposer.py |

**功能描述**

各平台内容模板系统、自动字数/格式适配、平台特定 emoji/标签处理。

**验收标准**

- [ ] 平台内容模板管理
- [ ] 自动字数适配
- [ ] 平台特定格式转换
- [ ] 标签自动转换（微博 #tag# vs 小红书 #tag#）

**实现方案**

```python
class PlatformContentAdapter:
    """平台内容适配器"""

    PLATFORM_CONFIGS = {
        "weibo": {
            "max_length": 2000,
            "image_format": "jpg",
            "hashtag_format": "#{tag}#",
            "supports_mention": True,
        },
        "xiaohongshu": {
            "max_length": 1000,
            "image_format": "jpg",
            "hashtag_format": "#{tag}#",
            "supports_mention": True,
        },
    }

    def adapt(self, content: str, target_platform: str) -> str:
        config = self.PLATFORM_CONFIGS[target_platform]

        # 1. 字数截断
        if len(content) > config["max_length"]:
            content = self._truncate(content, config["max_length"])

        # 2. 标签格式转换
        content = self._convert_hashtags(content, config["hashtag_format"])

        return content
```

---

#### 2.2.4 收件箱增强

| 属性 | 内容 |
|------|------|
| **需求编号** | F-009 |
| **需求类型** | 功能增强 |
| **优先级** | P1 |
| **关联模块** | inbox/inbox.py |

**功能描述**

智能消息分类、会话视图、快速回复模板、高级搜索与筛选。

**验收标准**

- [ ] 多视图支持（列表/卡片/时间线）
- [ ] 智能标签分类
- [ ] 高级筛选条件
- [ ] 收藏夹功能
- [ ] 批量操作

**实现方案**

```python
class EnhancedInbox(AgentInbox):
    class ViewMode(Enum):
        LIST = "list"
        CARD = "card"
        TIMELINE = "timeline"

    @dataclass
    class FilterOptions:
        priority: Optional[str] = None
        starred: Optional[bool] = None
        platform: Optional[str] = None
        date_range: Optional[tuple[datetime, datetime]] = None
        search_query: Optional[str] = None
        has_attachment: Optional[bool] = None

    async def query_enhanced(self, options: FilterOptions,
                              view: ViewMode = ViewMode.LIST) -> list[InboxItem]:
        """增强的查询接口"""
        conditions = []
        params = []

        if options.priority:
            conditions.append("priority = ?")
            params.append(options.priority)

        if options.starred is not None:
            conditions.append("starred = ?")
            params.append(int(options.starred))

        if options.date_range:
            conditions.append("created_at BETWEEN ? AND ?")
            params.extend([*options.date_range])

        #全文搜索
        if options.search_query:
            conditions.append("content MATCH ?")
            params.append(options.search_query)

        return await self.query(QueryOptions(conditions, params, view))
```

---

#### 2.2.5 审核工作流自动化

| 属性 | 内容 |
|------|------|
| **需求编号** | F-010 |
| **需求类型** | 功能增强 |
| **优先级** | P1 |
| **关联模块** | review/web.py, review/db.py |

**功能描述**

分级审核机制、低风险内容自动通过、审核历史追溯、移动端审核支持。

**验收标准**

- [ ] 三级审核流程（初审/复审/终审）
- [ ] 质量分 ≥ 90 自动通过
- [ ] 批量审核功能
- [ ] 审核报表导出
- [ ] 移动端快捷审核

**实现方案**

```python
class EnhancedReviewWorkflow:
    REVIEW_LEVELS = ['initial', 'senior', 'final']
    AUTO_APPROVE_THRESHOLD = 90

    def _determine_review_level(self, quality_score: int) -> str:
        if quality_score >= 85:
            return 'initial'
        elif quality_score >= 70:
            return 'senior'
        return 'final'

    async def submit_for_review(self, state: WorkflowState,
                                 options: dict) -> dict:
        review_item = {
            "review_level": self._determine_review_level(state.quality_score),
            "assigned_reviewer": self._assign_reviewer(options),
        }

        # 自动审核
        if (state.quality_score >= self.AUTO_APPROVE_THRESHOLD and
            state.analysis_result.get('violation_level') == 'safe'):
            review_item['status'] = 'auto_approved'

        return review_item

    async def batch_review(self, review_ids: list[str],
                           action: str, feedback: str = None) -> BatchResult:
        """批量审核"""
        results = []
        for review_id in review_ids:
            result = await self.review(review_id, action, feedback)
            results.append(result)
        return BatchResult(total=len(results), successful=sum(1 for r in results if r.success))
```

---

#### 2.2.6 数据看板

| 属性 | 内容 |
|------|------|
| **需求编号** | F-011 |
| **需求类型** | 新功能 |
| **优先级** | P1 |
| **关联模块** | dashboard/web.py |

**功能描述**

内容生成统计、平台发布成功率、用户交互分析、自定义报表导出。

**验收标准**

- [ ] 实时统计数据展示
- [ ] 7天趋势图表
- [ ] 平台分布饼图
- [ ] 质量指标追踪
- [ ]报表导出（Excel/PDF）

**实现方案**

```python
@dataclass
class DashboardStats:
    realtime: dict[str, int]           # 实时统计
    trends: dict[str, list[int]]       # 趋势数据
    platforms: dict[str, int]          # 平台分布
    quality: dict[str, float]          # 质量指标

class DashboardAPI:
    async def get_stats(self, period: str = "7d") -> DashboardStats:
        return DashboardStats(
            realtime={
                "generated_today": await self._count_generated_today(),
                "pending_review": await self._count_pending(),
                "unread_messages": await self._count_unread(),
            },
            trends={
                "daily_generated": await self._get_daily_generated(period),
                "approval_rate": await self._get_approval_rate(period),
            },
            platforms=await self._get_platform_distribution(),
            quality={
                "avg_quality_score": await self._get_avg_quality(),
                "avg_review_time": await self._get_avg_review_time(),
            }
        )
```

---

### 2.3 低优先级需求

#### 2.3.1 A/B 测试变体

| 属性 | 内容 |
|------|------|
| **需求编号** | F-012 |
| **需求类型** | 新功能 |

**功能描述**

支持生成多个内容变体，变体效果追踪，自动选择最优变体。

**验收标准**

- [ ]一次生成 3-5 个变体
- [ ] 变体效果数据追踪
- [ ] 最优变体自动推荐

---

#### 2.3.2 草稿箱与版本管理

| 属性 | 内容 |
|------|------|
| **需求编号** | F-013 |
| **需求类型** | 新功能 |

**功能描述**

内容草稿自动保存、历史版本对比、一键回滚。

**验收标准**

- [ ] 自动保存草稿
- [ ] 版本历史记录
- [ ] 对比视图
- [ ] 回滚功能

---

#### 2.3.3 团队协作

| 属性 | 内容 |
|------|------|
| **需求编号** | F-014 |
| **需求类型** | 新功能 |

**功能描述**

用户角色管理、操作权限控制、操作日志审计。

**验收标准**

- [ ] 角色定义（管理员/运营/审核）
- [ ] 权限矩阵
- [ ] 操作日志
- [ ] 审计报表

---

### 2.4 创新功能需求

#### 2.4.1 多 Agent 协作网络

| 属性 | 内容 |
|------|------|
| **需求编号** | F-015 |
| **需求类型** | 创新功能 |

**功能描述**

专业化 Agent 池（内容 Agent、审核 Agent、发布 Agent）、任务智能分解与路由、Agent 间通信协议。

**验收标准**

- [ ] Agent 池管理
- [ ] 任务自动路由
- [ ] 协作状态可视化

---

#### 2.4.2 热点话题发现

| 属性 | 内容 |
|------|------|
| **需求编号** | F-016 |
| **需求类型** | 创新功能 |

**功能描述**

社交媒体热点监控、话题趋势预测、自动内容选题建议。

**验收标准**

- [ ] 热点数据源接入
- [ ] 趋势分析图表
- [ ] 选题建议推送

---

#### 2.4.3 本地模型支持

| 属性 | 内容 |
|------|------|
| **需求编号** | F-017 |
| **需求类型** | 创新功能 |

**功能描述**

Ollama/llama.cpp 集成、本地向量数据库、混合云部署模式。

**验收标准**

- [ ] Ollama 集成
- [ ] 本地推理优化
- [ ] 云端/本地切换

---

## 3. 非功能性需求

### 3.1 性能需求

| 指标 | 要求 | 说明 |
|------|------|------|
| 首 token 延迟 | < 500ms | 流式响应 |
| 内容生成时间 | < 10s |1000字以内 |
| 消息处理吞吐 | > 100/s | Webhook |
| API响应时间 | < 200ms | 99分位 |

### 3.2 可用性需求

| 指标 | 要求 |
|------|------|
| 系统可用性 | 99.9% |
| 消息丢失率 | < 0.1% |
| 数据持久性 | 99.99% |

### 3.3 安全需求

| 需求 | 说明 |
|------|------|
| API Key 加密 | 必须使用环境变量或加密存储 |
| 密码强度 | 禁止弱密码，必须8 位以上 |
| JWT 安全 | 禁止默认密钥，强制环境变量配置 |
| 数据隔离 | 多租户数据严格隔离 |

### 3.4 兼容性需求

| 需求 | 说明 |
|------|------|
| Python 版本 | >= 3.10 |
| 浏览器 | Chrome/Firefox/Safari 最新版 |
| 移动端 | iOS14+, Android 10+ |

---

## 4. 优先级矩阵

| 优先级 | 数量 | 功能列表 |
|--------|------|----------|
| **P0** | 5 | 流式响应、上下文管理、Webhook可靠性、多图发布、敏感词管理 |
| **P1** | 6 | 多模型路由、批量任务编排、跨平台适配、收件箱增强、审核自动化、数据看板 |
| **P2** | 5 | A/B测试、草稿箱、团队协作、媒体库、多通道通知 |
| **P3** | 3 | 多Agent协作、热点发现、本地模型 |

---

## 5. 实施计划

### 第一阶段 (Month 1-2) - 核心体验

```
┌─────────────────────────────────────────────┐
│ P0 功能优先级 │
├─────────────────────────────────────────────┤
│ 1. 流式响应支持                              │
│ 2. 敏感词动态管理                            │
│ 3. Webhook可靠性保障                         │
│ 4. 多图发布优化                              │
│ 5. 智能上下文管理                            │
└─────────────────────────────────────────────┘
```

**里程碑**: 核心交互体验提升，消息处理可靠性保障

### 第二阶段 (Month 3-4) - 效率提升

```
┌─────────────────────────────────────────────┐
│ P1 功能优先级                                │
├─────────────────────────────────────────────┤
│ 1. 多模型智能路由                            │
│ 2. 批量任务编排                              │
│ 3. 跨平台内容适配                            │
│ 4. 收件箱增强                                │
│ 5. 审核工作流自动化                          │
│ 6. 数据看板                                  │
└─────────────────────────────────────────────┘
```

**里程碑**: 运营效率显著提升，数据驱动优化

### 第三阶段 (Month 5+) - 创新突破

```
┌─────────────────────────────────────────────┐
│ P2/P3 功能优先级                             │
├─────────────────────────────────────────────┤
│ 1. A/B 测试支持                              │
│ 2. 草稿箱与版本管理                          │
│ 3. 团队协作 │
│ 4. 多 Agent 协作网络                         │
│ 5. 热点话题发现                              │
│ 6. 本地模型支持                              │
└─────────────────────────────────────────────┘
```

**里程碑**: 差异化竞争力构建，满足企业级需求

---

## 6. 附录

### 6.1 术语表

| 术语 | 说明 |
|------|------|
| LLM | Large Language Model，大语言模型 |
| 流式响应 | Streaming，实时逐字输出 |
| Webhook | 平台消息回调机制 |
| Token | 语言模型最小处理单元 |
| RAG | Retrieval-Augmented Generation，检索增强生成 |

### 6.2 参考资料

- 项目代码: `/Users/zfl/projects/cn-social-agent`
- 设计文档: `DESIGN.md`
- 使用文档: `USAGE.md`

### 6.3 变更记录

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|----------|------|
| v1.0 | 2026-06-10 | 初始版本 | Claude |

---

**文档结束**