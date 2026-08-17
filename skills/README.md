# Skills Directory

Workbench skills live here as `*/SKILL.md` (YAML front matter + body). The loader
scans recursively and injects matching skills into Agent prompts on demand.

## Layout

```
skills/
├── tech-saas-content/          # FDE vertical: tech SaaS content OS
│   ├── SKILL.md
│   └── pack.yaml               # default enable list + cost estimates
├── hiring-insight-cards/       # FDE vertical: 招聘洞察 cards
├── short-video-director/
├── short-video-researcher/
├── github-star-growth-video/
├── deep-analysis-video/
├── web-video-presentation/
├── ffmpeg-motion-cards/
└── demo-echo/
```

## Front matter

```yaml
---
id: skill-id
name: Human Name
description: One-line when this skill applies.
---
```

## FDE packs

For a customer instance, copy `tech-saas-content/pack.yaml` to
`data/customers/<slug>/pack.yaml`, set `USAGE_CUSTOMER_ID`, and enable the listed
skills in the workbench. Customize the 「客户覆盖」section inside the SKILL body;
promote stable edits back to this repo weekly.
