/** stepKey -> audio path under public/ (optional). */
export const narrations: Record<string, { text: string; audio?: string }> = {
  "0:0": { text: "欢迎来到讲解演示。" },
  "0:1": { text: "每一口播节拍对应一个全屏步骤。" },
  "0:2": { text: "确认主题后，用 OBS 打开自动模式录屏。" },
};

export function narrationKey(chapter: number, step: number): string {
  return `${chapter}:${step}`;
}
