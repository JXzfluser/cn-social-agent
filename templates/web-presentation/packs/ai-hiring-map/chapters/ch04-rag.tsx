import type { ReactNode } from "react";

export const chapterTitle = "检索增强";

export const steps: Array<(ctx: { themeInk: string }) => ReactNode> = [
  () => (
    <div className="slide">
      <p className="eyebrow">能力轴 02</p>
      <h1>检索增强工程</h1>
      <p>RAG 是完整链路，不是「只会调 API」。</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>机制</h1>
      <div className="flow">
        <span>切分</span><i />
        <span>向量化</span><i />
        <span>混合检索</span><i />
        <span>生成</span>
      </div>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>易错</h1>
      <p>切分过碎语义断裂；召回噪声过多干扰判断。</p>
    </div>
  ),
  () => (
    <div className="slide">
      <h1>检验</h1>
      <p>拿出 <strong className="accent">Recall@K</strong>，说清如何重排与降噪。</p>
    </div>
  ),
];
