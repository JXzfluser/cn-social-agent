import type { ReactNode } from "react";

export const chapterTitle = "能力轴";

export const steps: Array<(ctx: { themeInk: string }) => ReactNode> = [
  () => (
    <div className="slide">
      <h1>三条能力轴</h1>
      <p>对应三类高频岗位：Agent 开发 · 应用开发 · 全栈交付</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1 className="accent">1 编排</h1>
      <p>智能体怎么拆目标、调工具、管状态</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1 className="accent">2 检索</h1>
      <p>RAG 全链路：切分 → 向量 → 召回 → 融合</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1 className="accent">3 交付</h1>
      <p>模型原生进产品：选型 · Prompt · 评估</p>
    </div>
  ),
];
