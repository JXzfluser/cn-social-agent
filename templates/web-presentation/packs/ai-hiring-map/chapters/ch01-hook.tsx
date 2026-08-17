import type { ReactNode } from "react";

export const chapterTitle = "开场";

export const steps: Array<(ctx: { themeInk: string }) => ReactNode> = [
  () => (
    <div className="slide">
      <p className="eyebrow">AI TALENT MAP</p>
      <h1>AI 招聘能力图谱</h1>
      <p>今天不讲「会用 AI」，讲招聘真正要看什么。</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>市场在变</h1>
      <p>岗位更看重<strong className="accent">可验证的交付物</strong>，而不是工具名词清单。</p>
    </div>
  ),
];
