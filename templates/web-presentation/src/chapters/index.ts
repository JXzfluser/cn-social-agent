import * as ch01 from "./ch01-demo";

export type Chapter = {
  title: string;
  steps: typeof ch01.steps;
};

export const chapters: Chapter[] = [
  { title: ch01.chapterTitle, steps: ch01.steps },
];
