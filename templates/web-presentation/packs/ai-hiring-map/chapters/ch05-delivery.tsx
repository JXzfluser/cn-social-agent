import type { ReactNode } from "react";

export const chapterTitle = "模型原生交付";

export const steps: Array<(ctx: { themeInk: string }) => ReactNode> = [
  () => (
    <div className="slide">
      <p className="eyebrow">能力轴 03</p>
      <h1>模型原生交付</h1>
      <p>把模型嵌进产品架构，而不是包一层接口。</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>机制</h1>
      <div className="flow">
        <span>选型</span><i />
        <span>Prompt</span><i />
        <span>Schema</span><i />
        <span>评估</span>
      </div>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>易错</h1>
      <p>无视上下文上限、输出不稳定、延迟失控。</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>检验</h1>
      <p>展示<strong className="accent">调优前后对比数据</strong>与场景证据。</p>
    </div>
  ),
];
