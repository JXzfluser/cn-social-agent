# 客户演示 / 部署 Runbook

目标：陌生人客户在 **1–2 天**内装上工作台，并能跟着走完「热点 → 口播/卡片 → 发布」。

---

## 0. 客户实例约定（运维级隔离）

每个付费客户一套实例，**不要**共享同一 env：

| 项 | 约定 |
|----|------|
| 目录 | 独立 clone 或 `data/customers/<slug>/` 挂载视频/卡片产物 |
| Env | `.env.<slug>`：InsForge、AGNES、平台 OAuth 密钥 |
| InsForge | 独立项目 / DB（或至少独立 Secrets 命名空间） |
| 账号 | 客户自己的抖音创作者、微信公众号；不要用你的号代发长期内容 |
| 标识 | 设 `USAGE_CUSTOMER_ID=<slug>`，用量日志按客户分开 |

示例：

```bash
export USAGE_CUSTOMER_ID=acme-devtools
export VIDEO_DATA_DIR=data/customers/acme-devtools/videos
export WORKBENCH_PORT=18081
```

---

## 1. 部署清单（上线前打勾）

### 本机 / 服务器

- [ ] Python 3.10+、`.venv`、`pip install -r requirements.txt`
- [ ] `ffmpeg` 在 PATH
- [ ] InsForge API `:7130`、控制台 `:7131` 健康（`scripts/insforge-health.sh`）
- [ ] `scripts/ensure_workbench_tables.py` 已跑
- [ ] 工作台可开：`PYTHONPATH=src WORKBENCH_STORE=insforge .venv/bin/python run_workbench.py`

### LLM / 成片

- [ ] `AGNES_API_KEY`（或配置文件）— 聊天 + L1
- [ ] 可选：Ollama / OpenRouter 作降级
- [ ] L0 不依赖 Agnes Video；L1 需 Agnes Video 已配置

### 平台账号（按合同选）

- [ ] **抖音**：创作者中心可登录；有 API 则配 OAuth，否则半自动上传 SOP
- [ ] **微信公众号**：AppID/Secret；草稿箱权限
- [ ] **小红书**（可选）：半自动 — 导出图文 + 创作者中心粘贴

### 冒烟（装完必跑）

```bash
WORKBENCH_URL=http://127.0.0.1:18081 .venv/bin/python scripts/smoke_insforge_workbench.py
WORKBENCH_URL=http://127.0.0.1:18081 .venv/bin/python scripts/smoke_video_workshop.py
WORKBENCH_URL=http://127.0.0.1:18081 .venv/bin/python scripts/smoke_chat_to_video.py
```

---

## 2. 演示日剧本（约 25–35 分钟）

**叙事：** 只讲「技术内容生产系统」，不讲通用 Agent / SCRM。

| 分钟 | 步骤 | 操作要点 | 成功标准 |
|------|------|----------|----------|
| 0–3 | 定调 | 痛点：有料发不出；验收：可发条数 | 客户点头 |
| 3–8 | 热点 | Agent 或热点页 `scan` → 点一条技术选题 | 出现可聊条目 |
| 8–18 | 口播 | 「做短视频」→ 确认分镜 → **L0 分镜草稿** 预览 | ≤90s 看到草稿；文案说清 L0≠成片 |
| 18–25 | 升级（可选） | 一镜或整片 **L1**；说明成本与队列 | 有进度/失败可解释 |
| 25–30 | 知识卡 | 卡片模式：招聘洞察或产品科普 → 导出 PNG | 看到可发图 |
| 30–35 | 发布 | 抖音半自动 **或** 公众号草稿；展示 SOP 文档 | 客户知道「下一步点哪里」 |

### 演示禁用

- 不要默认把 L0 说成「成片」
- 不要承诺全自动矩阵 / 小红书官方全自动
- 不要展开六月运营中台大盘功能

### 备用路径（网络/Agnes 挂了）

只演示 L0 + 知识卡导出 + 半自动发布说明；把 L1 放到「加强档含云费用」。

---

## 3. 周节奏模板（试点四周）

每周固定三次触点（可远程）：

| 日 | 动作 |
|----|------|
| 周一 | 热点扫描 → 确认本周 2–3 选题写入主题资产 |
| 周三 | 制作日：L0 全出；选定升 L1 / 出卡片 |
| 周五 | 发布 + 复盘；FDE 写 **卡点清单**；跑用量周报 |

```bash
USAGE_CUSTOMER_ID=<slug> PYTHONPATH=src .venv/bin/python scripts/usage_weekly_report.py --days 7
```

### 卡点清单字段（周五）

- 卡在哪一步（选题 / 脚本 / L0 / L1 / 发布 / 账号）
- 客户原话
- 本周是否改 skill / 模板
- 是否回灌主仓（PR 链接）

---

## 4. 黄金路径口令（给客户备忘）

1. 打开工作台 → Agent 或热点  
2. 选定题 →「做短视频」或「做知识卡」  
3. 先看 **分镜草稿（L0）**，结构 OK 再升 **成片（L1）**  
4. 下载 / 导出 → 按 SOP 发抖音或公众号  
5. 把链接回填到本周复盘表  

技能开关：确保启用 `tech-saas-content`；招聘场景启用 `hiring-insight-cards`。

---

## 5. 交接清单（试点结束）

- [ ] 成功标准数字已达成或书面偏差说明  
- [ ] 客户方操作人能独立跑通一次  
- [ ] 用量四周汇总已交付  
- [ ] 续约意向：retainer / 年费 / 结束  
- [ ] 匿名案例授权状态  
