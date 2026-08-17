# OpenClaw 热点短视频系列（GitHub Star 增长选题）

> 选题仓库：https://github.com/openclaw/openclaw  
> 定位：个人 AI 助手（Own Your Data）· 程序员向口播  
> 状态：三集 **L0 分镜草稿** 已出片（可在工坊升级 L1）

## 成片清单

| 集 | 角度 | 时长档 | 标题 | 项目 ID | 本地文件 |
|----|------|--------|------|---------|----------|
| 1 | 入门 `intro` | 45s | OpenClaw本地部署：3步跑通个人AI助手 | `d6d44013-012a-4f64-bc11-c5a594e1d1d3` | `data/videos/d6d44013-…/final.mp4` |
| 2 | 核心思想 `idea` | 45s | 拒绝云端监控：打造本地私有AI助手 | `0863953f-04f1-46b6-afa6-af13d94c7872` | `data/videos/0863953f-…/final.mp4` |
| 3 | 对比 `compare` | 60s | OpenClaw vs ChatGPT：开发者别装错工具 | `957867ed-d74b-4dc6-994c-16cc94c80fb3` | `data/videos/957867ed-…/final.mp4` |

打开：http://127.0.0.1:18081/?mode=video → 左侧项目列表。

## 内容大纲

### EP1 入门
钩子（星数/涨速）→ 是什么 → 谁适合 → 三步跑通 → 一个坑 → CTA「入门」

### EP2 核心思想
钩子（为什么到处都是）→ Own Your Data → 旧痛（聊天在别人云上）→ 一句话 → CTA 收藏

### EP3 对比
钩子（别装错）→ vs 云端 Chat / vs IDE Agent → 谁适合谁 → CTA 评论主力工具

## 产品能力配套

- 工坊：**内容角度**（入门/核心思想/对比）自动建议时长
- Agent 工具：`github_rising_repos` / `github_repo_insight`
- Skill：`skills/github-star-growth-video/`
- 复现脚本：`scripts/produce_github_openclaw_series.py`

## 下一步建议

1. 对 hook/cta 镜点「此镜升级成片」(L1)  
2. 会话侧可删冗余调试会话  
3. 换仓库：改 `GH_REPO=owner/name` 再跑脚本
