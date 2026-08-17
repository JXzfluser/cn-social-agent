import * as ch01 from "./ch01-hook";
import * as ch02 from "./ch02-axes";
import * as ch03 from "./ch03-agent";
import * as ch04 from "./ch04-rag";
import * as ch05 from "./ch05-delivery";
import * as ch06 from "./ch06-interview";
import * as ch07 from "./ch07-cta";

export type Chapter = {
  title: string;
  steps: typeof ch01.steps;
};

export const chapters: Chapter[] = [
  { title: ch01.chapterTitle, steps: ch01.steps },
  { title: ch02.chapterTitle, steps: ch02.steps },
  { title: ch03.chapterTitle, steps: ch03.steps },
  { title: ch04.chapterTitle, steps: ch04.steps },
  { title: ch05.chapterTitle, steps: ch05.steps },
  { title: ch06.chapterTitle, steps: ch06.steps },
  { title: ch07.chapterTitle, steps: ch07.steps },
];
