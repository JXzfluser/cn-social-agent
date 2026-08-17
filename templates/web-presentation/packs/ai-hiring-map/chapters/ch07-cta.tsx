import type { ReactNode } from "react";

export const chapterTitle = "行动";

export const steps: Array<(ctx: { themeInk: string }) => ReactNode> = [
  () => (
    <div className="slide">
      <h1>先画图谱</h1>
      <p>再对 JD，再写面试题。</p>
    </div>
  ),
  () => (
    <div className="slide">
      <p className="eyebrow">AI TALENT MAP</p>
      <h1>AI 招聘能力图谱</h1>
      <p>编排 · 检索 · 交付 —— 用检验说话。</p>
    </div>
  ),
];
