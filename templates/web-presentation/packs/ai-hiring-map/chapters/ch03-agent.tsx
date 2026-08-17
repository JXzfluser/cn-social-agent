import type { ReactNode } from "react";

export const chapterTitle = "智能体编排";

export const steps: Array<(ctx: { themeInk: string }) => ReactNode> = [
  () => (
    <div className="slide">
      <p className="eyebrow">能力轴 01</p>
      <h1>智能体编排</h1>
      <p>按目标拆步骤、选工具、写状态，失败可回退——不是多聊几轮。</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>机制</h1>
      <div className="flow">
        <span>规划</span><i />
        <span>工具</span><i />
        <span>状态</span><i />
        <span>回退</span>
      </div>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>易错</h1>
      <p>无超时边界 → 循环调用；状态不同步 → 级联失败。</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>检验</h1>
      <p>能画出状态机，并<strong className="accent">复现一次回退</strong>。</p>
    </div>
  ),
];
