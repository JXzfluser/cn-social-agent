## Design Context

### Users
内容创作者、独立开发者、Agent 拥趸——在 CN Workbench 跑「Agent 对话 / 短视频制片 / 知识卡片 / 画布 / Know-How 管理」全链路。使用场景：桌面端为主（移动端兜底），多任务并行，需要工具感和控制感，不需要「玩具感」。Idea Engine 用户关注热点选题 → 自动生成选题卡 → 选中即创建内容项目。

### Brand Personality
**cyberpunk · bold · immersive**

- cyberpunk: 深色背景 + 霓虹渐变 + 等宽字体——让界面看起来像未来控制台，技术感拉满。
- bold: 大胆的渐变色、清晰的对比、无畏惧的视觉冲击——不是保守的工具，是有态度的产品。
- immersive: 沉浸式暗色体验，让用户感觉置身于专业的工作站，而非普通网页。

情绪目标：**酷炫与专注**，让用户觉得「我在用一个很酷的工具」，同时保持高效沉浸。

### Aesthetic Direction
**深色科技 × 霓虹渐变 × 等宽技术美学**

- 深色为主：近黑底（#0a0a0a）+ 微灰面板（#111113）+ 霓虹渐变点缀。
- 渐变系统：主渐变 linear-gradient(135deg, #3B82F6, #8B5CF6) 用于 primary 按钮和高亮；辅助渐变 linear-gradient(135deg, #10B981, #06B6D4) 用于成功状态；警告渐变 linear-gradient(135deg, #F59E0B, #EF4444) 用于危险操作。
- 字体：**JetBrains Mono / Fira Code 等宽字体优先**——标题、正文、按钮全部等宽，强化技术美学；回退到 SF Mono / ui-monospace。
- 图标：**Lucide**（CDN 或本地内联）——线性、1.5px stroke、方端，与等宽字体气质一致。
- 圆角：中等偏小——主圆角 12px、控件 8px、chip 6px、pill 999px。
- 描边：1px 半透明白线（rgba(255,255,255,0.08)），用发光效果替代阴影分组。
- 动效：适度。仅：状态切换 150ms ease、hover glow 100ms、入场 250ms opacity+translateY、dialog fade+scale。允许：霓虹发光、渐变流动、微妙脉冲。尊重 `prefers-reduced-motion`。

**References**: Linear Dark（深色玻璃）、Vercel Dashboard（status pill、代码细节）、Raycast（命令面板、kbd 提示）、Arc Browser（现代UI、圆角、渐变）。
**Anti-references**: 纯白背景、紫色渐变AI风、粗圆角卡片墙、emoji当图标、Notion灰白卡片堆叠、传统企业软件。

### Design Principles
1. **等宽即身份** — JetBrains Mono 无处不在（标题/正文/按钮/状态）；层级靠字重和颜色差，不靠字号差。
2. **渐变即层次** — 多色渐变用于 primary action / active state / 技术标识；静态颜色用于次要元素；禁止纯色块堆砌。
3. **暗色即沉浸** — 近黑背景 + 半透明白线 + 微发光效果；让界面像控制台/IDE，不是普通网页。
4. **技术即美学** — Agent / 工具调用 / 路径 / ID / status 用等宽字体 + 霓虹色标识；让「我在控制 Agent」的酷炫感可见。
5. **大胆即前卫** — 拥抱渐变、发光、对比；不畏惧视觉冲击；但保持克制，不为炫技牺牲可用性。
6. **双主题对称** — 深色为主，浅色为辅（未来扩展）；两套独立调色板；不为某一主题牺牲另一主题。

### Design Tokens（落地的 CSS 变量约定）

**深色（默认）**
- `--bg: #0a0a0a`（近黑，微带灰）
- `--panel: #111113` / `--panel-2: #1a1a1f`
- `--ink: #fafafa` / `--ink-2: #a1a1aa` / `--muted: #6b6b73`
- `--line: rgba(255,255,255,0.08)` / `--line-strong: rgba(255,255,255,0.15)`
- `--accent: linear-gradient(135deg, #3B82F6, #8B5CF6)`（蓝紫渐变，主色）
- `--accent-solid: #6366F1`（纯色版本，用于需要纯色的场景）
- `--accent-ink: #eef2ff`
- `--ok: linear-gradient(135deg, #10B981, #06B6D4)`（翡翠青）
- `--ok-solid: #10B981`
- `--warn: linear-gradient(135deg, #F59E0B, #EF4444)`（橙红渐变）
- `--warn-solid: #F59E0B`
- `--danger: #EF4444`（纯红）
- `--violet: linear-gradient(135deg, #8B5CF6, #D946EF)`（紫粉渐变）
- `--violet-solid: #8B5CF6`
- `--font: "JetBrains Mono", "Fira Code", "SF Mono", ui-monospace, monospace`
- `--radius: 12px` / `--radius-sm: 8px` / `--radius-chip: 6px`
- `--shadow-sm: 0 0 0 1px rgba(255,255,255,0.05)`
- `--shadow-md: 0 4px 24px rgba(0,0,0,0.4)`
- `--shadow-glow: 0 0 20px rgba(99,102,241,0.3)`（霓虹发光）
- `--transition: 150ms cubic-bezier(.4,0,.2,1)`
- `--transition-fast: 100ms cubic-bezier(.4,0,.2,1)`
- `--transition-slow: 250ms cubic-bezier(.4,0,.2,1)`
- color-scheme: dark

**渐变预设**
- `--gradient-primary: linear-gradient(135deg, #3B82F6, #8B5CF6)`
- `--gradient-success: linear-gradient(135deg, #10B981, #06B6D4)`
- `--gradient-warning: linear-gradient(135deg, #F59E0B, #EF4444)`
- `--gradient-violet: linear-gradient(135deg, #8B5CF6, #D946EF)`
- `--gradient-rainbow: linear-gradient(135deg, #3B82F6, #8B5CF6, #D946EF, #EC4899)`

**发光效果**
- `--glow-primary: 0 0 20px rgba(99,102,241,0.4)`
- `--glow-success: 0 0 20px rgba(16,185,129,0.4)`
- `--glow-danger: 0 0 20px rgba(239,68,68,0.4)`
