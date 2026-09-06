# FDE 交付包（技术内容操作系统）

本目录支撑「卖结果、不卖座位」的 30 天试点：驻场/陪跑把产能跑通，再把重复劳动抽回产品。

| 文档 | 用途 |
|------|------|
| [30-day-pilot-offer.md](./30-day-pilot-offer.md) | 售前一页纸（报价、交付、不含项） |
| [demo-deploy-runbook.md](./demo-deploy-runbook.md) | 部署清单 + 演示日剧本 + 周节奏 |
| [lead-pipeline.md](./lead-pipeline.md) | 潜客池、发现访谈脚本、关单检查表 |
| [leads.csv](./leads.csv) | 10 个线索跟踪表（填真实联系人） |

相关技能（驻场可定制后回灌）：

- `skills/tech-saas-content/` — 技术 SaaS 内容流水线
- `skills/hiring-insight-cards/` — 招聘洞察知识卡

用量与成本（内部）：

```bash
PYTHONPATH=src .venv/bin/python scripts/usage_weekly_report.py
# 或 GET /api/usage/summary?days=7
```
