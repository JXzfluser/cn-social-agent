import type { ReactNode } from "react";

export const chapterTitle = "开场";

/** Each entry is one full-screen step (one narration beat). */
export const steps: Array<(ctx: { themeInk: string }) => ReactNode> = [
  () => (
    <div className="slide">
      <div className="slide-inner">
        <p className="eyebrow">Presentation</p>
        <h1>讲解演示</h1>
        <hr className="rule" />
        <p>把文章变成可点击驱动的舞台，再录成片。</p>
      </div>
    </div>
  ),
  () => (
    <div className="slide">
      <div className="slide-inner">
        <h1>
          一口播 <span className="accent">=</span> 一步
        </h1>
        <hr className="rule" />
        <p>不要在同一帧堆叠项目符号。</p>
      </div>
    </div>
  ),
  () => (
    <div className="slide">
      <div className="slide-inner">
        <h1>自动模式</h1>
        <hr className="rule" />
        <p>打开 ?auto=1，按空格后按音频节奏推进，配合录制一镜到底。</p>
      </div>
    </div>
  ),
];
