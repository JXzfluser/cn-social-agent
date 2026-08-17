import type { ReactNode } from "react";

export const chapterTitle = "面试检验";

export const steps: Array<(ctx: { themeInk: string }) => ReactNode> = [
  () => (
    <div className="slide">
      <h1>招人三问</h1>
      <p>问机制 · 问易错 · 问检验</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>要交付物</h1>
      <p>状态机、检索报告、A/B 数据——拒绝名词堆叠。</p>
    </div>
  ),
];
