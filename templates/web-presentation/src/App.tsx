import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { aspect, stageHeight, stageWidth, themeId, title as configTitle } from "./config";
import { chapters as compiledChapters } from "./chapters";
import { narrationKey, narrations } from "./narrations";
import { resolveTheme, type Theme } from "./themes";

type DiagramCard = { k?: string; t: string; d?: string };
type Diagram =
  | { type: "axes3"; items: DiagramCard[] }
  | { type: "pipeline"; items: string[] }
  | { type: "state"; nodes: string[]; loops?: string[] }
  | { type: "cards"; cols?: 1 | 2 | 3; items: DiagramCard[] }
  | { type: "compare"; left: DiagramCard; right: DiagramCard }
  | { type: "checklist"; items: string[] };

type SlideData = {
  eyebrow?: string;
  title: string;
  body?: string;
  narration?: string;
  outcome?: string;
  duration_ms?: number;
  flow?: string[];
  points?: string[];
  accent_title?: boolean;
  diagram?: Diagram;
};

type ChapterData = { title: string; role?: string; slides: SlideData[] };
type ContentDoc = { title?: string; chapters: ChapterData[] };

type NarrationClip = {
  text: string;
  audio?: string;
  duration_ms?: number;
  start_ms?: number;
};

function parseNarrationsPayload(data: unknown): Record<string, NarrationClip> {
  if (!data || typeof data !== "object") return {};
  const obj = data as Record<string, unknown>;
  if (obj.steps && typeof obj.steps === "object") {
    return obj.steps as Record<string, NarrationClip>;
  }
  const flat: Record<string, NarrationClip> = {};
  for (const [k, v] of Object.entries(obj)) {
    if (
      k === "version" ||
      k === "timeline" ||
      k === "qc" ||
      k === "voice" ||
      k === "total_ms"
    ) {
      continue;
    }
    if (v && typeof v === "object" && "text" in (v as object)) {
      flat[k] = v as NarrationClip;
    }
  }
  return flat;
}

function useQueryFlags() {
  return useMemo(() => {
    const q = new URLSearchParams(location.search);
    const ch = Math.max(0, Number.parseInt(q.get("ch") || "0", 10) || 0);
    const step = Math.max(0, Number.parseInt(q.get("step") || "0", 10) || 0);
    return { audio: q.get("audio") === "1", auto: q.get("auto") === "1", ch, step };
  }, []);
}

function DiagramAxes3({ items, theme }: { items: DiagramCard[]; theme: Theme }) {
  const a = items[0] || { t: "编排" };
  const b = items[1] || { t: "检索" };
  const c = items[2] || { t: "交付" };
  const ff = theme.fontBody;
  return (
    <div className="diagram" aria-hidden>
      <svg viewBox="0 0 900 420" role="img">
        <defs>
          <linearGradient id="axFill" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={theme.accent} stopOpacity="0.10" />
            <stop offset="100%" stopColor={theme.accent} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <polygon points="450,56 760,350 140,350" fill="url(#axFill)" stroke={theme.accent} strokeWidth="1.5" />
        <circle cx="450" cy="56" r="5" fill={theme.accent} />
        <circle cx="760" cy="350" r="5" fill={theme.accent} />
        <circle cx="140" cy="350" r="5" fill={theme.accent} />
        <text x="450" y="36" textAnchor="middle" fill={theme.ink} fontSize="26" fontWeight="600" fontFamily={ff}>
          {a.t}
        </text>
        <text x="450" y="88" textAnchor="middle" fill={theme.muted} fontSize="16" fontFamily={ff}>
          {a.d || a.k || ""}
        </text>
        <text x="140" y="388" textAnchor="middle" fill={theme.ink} fontSize="26" fontWeight="600" fontFamily={ff}>
          {b.t}
        </text>
        <text x="140" y="412" textAnchor="middle" fill={theme.muted} fontSize="16" fontFamily={ff}>
          {b.d || b.k || ""}
        </text>
        <text x="760" y="388" textAnchor="middle" fill={theme.ink} fontSize="26" fontWeight="600" fontFamily={ff}>
          {c.t}
        </text>
        <text x="760" y="412" textAnchor="middle" fill={theme.muted} fontSize="16" fontFamily={ff}>
          {c.d || c.k || ""}
        </text>
        <text x="450" y="230" textAnchor="middle" fill={theme.accent} fontSize="18" fontWeight="600" fontFamily={ff} letterSpacing="0.12em">
          可验证交付
        </text>
      </svg>
    </div>
  );
}

function DiagramPipeline({ items, theme }: { items: string[]; theme: Theme }) {
  const n = Math.max(1, items.length);
  const w = 860;
  const gap = 24;
  const boxW = Math.min(200, (w - gap * (n - 1)) / n);
  const startX = (900 - (boxW * n + gap * (n - 1))) / 2;
  const ff = theme.fontBody;
  return (
    <div className="diagram" aria-hidden>
      <svg viewBox="0 0 900 140" role="img">
        {items.map((label, i) => {
          const x = startX + i * (boxW + gap);
          return (
            <g key={i}>
              <line
                x1={x}
                y1={100}
                x2={x + boxW}
                y2={100}
                stroke={theme.accent}
                strokeWidth="1.5"
              />
              <text
                x={x + boxW / 2}
                y={72}
                textAnchor="middle"
                fill={theme.ink}
                fontSize="22"
                fontWeight="600"
                fontFamily={ff}
              >
                {label}
              </text>
              <text
                x={x + 4}
                y={96}
                fill={theme.accent}
                fontSize="12"
                fontWeight="600"
                fontFamily={ff}
                letterSpacing="0.08em"
              >
                {String(i + 1).padStart(2, "0")}
              </text>
              {i < n - 1 ? (
                <path
                  d={`M ${x + boxW + 6} 100 L ${x + boxW + gap - 6} 100`}
                  stroke={theme.line}
                  strokeWidth="1"
                  strokeDasharray="3 4"
                />
              ) : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function DiagramState({
  nodes,
  loops,
  theme,
}: {
  nodes: string[];
  loops?: string[];
  theme: Theme;
}) {
  const xs = [120, 340, 560, 780];
  const ff = theme.fontBody;
  return (
    <div className="diagram" aria-hidden>
      <svg viewBox="0 0 900 220" role="img">
        {nodes.slice(0, 4).map((label, i) => (
          <g key={i}>
            <rect
              x={xs[i]! - 72}
              y={52}
              width="144"
              height="56"
              rx="2"
              fill="transparent"
              stroke={theme.line}
              strokeWidth="1.25"
            />
            <line
              x1={xs[i]! - 72}
              y1={52}
              x2={xs[i]! - 72}
              y2={108}
              stroke={theme.accent}
              strokeWidth="2"
            />
            <text
              x={xs[i]}
              y={88}
              textAnchor="middle"
              fill={theme.ink}
              fontSize="22"
              fontWeight="600"
              fontFamily={ff}
            >
              {label}
            </text>
            {i < Math.min(3, nodes.length - 1) ? (
              <path
                d={`M ${xs[i]! + 78} 80 L ${xs[i + 1]! - 78} 80`}
                stroke={theme.accent}
                strokeWidth="1"
                strokeDasharray="4 5"
              />
            ) : null}
          </g>
        ))}
        {(loops || []).slice(0, 2).map((lab, i) => (
          <text
            key={lab}
            x={450}
            y={170 + i * 28}
            textAnchor="middle"
            fill={theme.muted}
            fontSize="18"
            fontFamily={ff}
          >
            ↺ {lab}
          </text>
        ))}
      </svg>
    </div>
  );
}

function DiagramCards({
  items,
  cols,
}: {
  items: DiagramCard[];
  cols?: 1 | 2 | 3;
}) {
  return (
    <div className={`card-grid cols-${cols || 1}`}>
      {items.map((it, i) => (
        <div className="viz-card" key={i}>
          {it.k ? <div className="k">{it.k}</div> : null}
          <div className="t">{it.t}</div>
          {it.d ? <p className="d">{it.d}</p> : null}
        </div>
      ))}
    </div>
  );
}

function DiagramCompare({ left, right }: { left: DiagramCard; right: DiagramCard }) {
  return (
    <div className="card-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
      <div className="viz-card">
        {left.k ? <div className="k">{left.k}</div> : null}
        <div className="t">{left.t}</div>
        {left.d ? <p className="d">{left.d}</p> : null}
      </div>
      <div className="viz-card">
        {right.k ? <div className="k">{right.k}</div> : null}
        <div className="t">{right.t}</div>
        {right.d ? <p className="d">{right.d}</p> : null}
      </div>
    </div>
  );
}

function DiagramChecklist({ items }: { items: string[] }) {
  return (
    <ul className="points">
      {items.map((t, i) => (
        <li key={i}>
          <span className="idx">{String(i + 1).padStart(2, "0")}</span>
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

function renderDiagram(d: Diagram, theme: Theme): ReactNode {
  switch (d.type) {
    case "axes3":
      return <DiagramAxes3 items={d.items} theme={theme} />;
    case "pipeline":
      return <DiagramPipeline items={d.items} theme={theme} />;
    case "state":
      return <DiagramState nodes={d.nodes} loops={d.loops} theme={theme} />;
    case "cards":
      return <DiagramCards items={d.items} cols={d.cols} />;
    case "compare":
      return <DiagramCompare left={d.left} right={d.right} />;
    case "checklist":
      return <DiagramChecklist items={d.items} />;
    default:
      return null;
  }
}

function renderSlide(slide: SlideData, _theme: Theme, animKey: string): ReactNode {
  const hasLead = !!(slide.eyebrow || slide.title);
  return (
    <div className="slide">
      <div className="slide-inner" key={animKey}>
        {slide.eyebrow ? <p className="eyebrow">{slide.eyebrow}</p> : null}
        <h1 className={slide.accent_title ? "accent" : undefined}>{slide.title}</h1>
        {hasLead ? <hr className="rule" /> : null}
        {slide.flow && slide.flow.length ? (
          <div className="flow">
            {slide.flow.flatMap((item, i) => {
              const nodes = [<span key={"s" + i}>{item}</span>];
              if (i < slide.flow!.length - 1) nodes.push(<i key={"i" + i} />);
              return nodes;
            })}
          </div>
        ) : null}
        {slide.body ? (
          <p
            className="body"
            style={{ marginTop: slide.flow || slide.diagram ? 20 : 0 }}
          >
            {slide.body}
          </p>
        ) : null}
        {slide.points?.length ? (
          <ul className="points">
            {slide.points.map((p, i) => (
              <li key={i}>
                <span className="idx">{String(i + 1).padStart(2, "0")}</span>
                <span>{p}</span>
              </li>
            ))}
          </ul>
        ) : null}
        {slide.diagram ? renderDiagram(slide.diagram, _theme) : null}
        {slide.outcome ? (
          <div className="outcome" role="note">
            <span className="outcome-tag">实测结果</span>
            <span className="outcome-text">{slide.outcome}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function App() {
  const theme = resolveTheme(themeId);
  const flags = useQueryFlags();
  const [doc, setDoc] = useState<ContentDoc | null>(null);
  const [liveNarrations, setLiveNarrations] = useState<Record<string, NarrationClip>>(
    {}
  );
  const [ch, setCh] = useState(flags.ch);
  const [step, setStep] = useState(flags.step);
  const [scale, setScale] = useState(1);
  const [autoArmed, setAutoArmed] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cleanRecord = flags.auto;

  useEffect(() => {
    let cancelled = false;
    const loadNarrations = () => {
      fetch("./narrations.json", { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (!cancelled && data) {
            setLiveNarrations(parseNarrationsPayload(data));
          }
        })
        .catch(() => {});
    };
    const load = () => {
      fetch("./content.json", { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (!cancelled && data && Array.isArray(data.chapters) && data.chapters.length) {
            setDoc(data as ContentDoc);
          }
        })
        .catch(() => {});
      loadNarrations();
    };
    load();
    const onMsg = (ev: MessageEvent) => {
      const data = ev.data;
      if (!data || typeof data !== "object") return;
      if (data.type === "pres:reload-content") {
        load();
        try {
          window.parent.postMessage({ type: "pres:content-acked" }, "*");
        } catch {
          /* ignore */
        }
      }
      if (data.type === "pres:set-content" && data.content && Array.isArray(data.content.chapters)) {
        setDoc(data.content as ContentDoc);
        try {
          window.parent.postMessage({ type: "pres:content-acked" }, "*");
        } catch {
          /* ignore */
        }
      }
      if (data.type === "pres:reload-narrations") {
        loadNarrations();
      }
      if (data.type === "pres:arm-auto") {
        setAutoArmed(true);
      }
      if (data.type === "pres:go" && typeof data.ch === "number" && typeof data.step === "number") {
        setCh(data.ch);
        setStep(data.step);
      }
    };
    window.addEventListener("message", onMsg);
    try {
      window.parent.postMessage({ type: "pres:ready" }, "*");
    } catch {
      /* ignore */
    }
    return () => {
      cancelled = true;
      window.removeEventListener("message", onMsg);
    };
  }, []);

  const chapters = useMemo(() => {
    if (doc?.chapters?.length) {
      return doc.chapters.map((c, ci) => ({
        title: c.title,
        steps: (c.slides || []).map(
          (s, si) => () => renderSlide(s, theme, `${ci}-${si}-${s.title || ""}`)
        ),
      }));
    }
    return compiledChapters;
  }, [doc, theme]);

  const pageTitle = doc?.title || configTitle;
  const totalSteps = chapters.reduce((n, c) => n + c.steps.length, 0);
  const flatIndex =
    chapters.slice(0, ch).reduce((n, c) => n + c.steps.length, 0) + step;

  useEffect(() => {
    try {
      window.parent.postMessage({ type: "pres:pos", ch, step }, "*");
    } catch {
      /* ignore */
    }
  }, [ch, step]);

  useEffect(() => {
    if (!chapters.length) return;
    let nextCh = Math.min(ch, chapters.length - 1);
    const maxStep = Math.max(0, (chapters[nextCh]?.steps.length || 1) - 1);
    let nextStep = Math.min(step, maxStep);
    if (nextCh !== ch) setCh(nextCh);
    if (nextStep !== step) setStep(nextStep);
  }, [chapters, ch, step]);

  useEffect(() => {
    const fit = () => {
      const sx = window.innerWidth / stageWidth;
      const sy = window.innerHeight / stageHeight;
      setScale(Math.max(0.05, Math.min(sx, sy)));
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  const advance = (dir: 1 | -1) => {
    const chapter = chapters[ch];
    if (!chapter) return;
    let nextStep = step + dir;
    let nextCh = ch;
    if (nextStep >= chapter.steps.length) {
      if (ch + 1 < chapters.length) {
        nextCh = ch + 1;
        nextStep = 0;
      } else return;
    } else if (nextStep < 0) {
      if (ch > 0) {
        nextCh = ch - 1;
        nextStep = chapters[nextCh].steps.length - 1;
      } else return;
    }
    setCh(nextCh);
    setStep(nextStep);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "PageDown") {
        e.preventDefault();
        advance(1);
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        advance(-1);
      } else if (e.key === "f" || e.key === "F") {
        e.preventDefault();
        const root = document.documentElement;
        if (!document.fullscreenElement) {
          root.requestFullscreen?.().catch(() => {});
        } else {
          document.exitFullscreen?.().catch(() => {});
        }
      } else if (e.key === " " || e.code === "Space") {
        e.preventDefault();
        if (flags.auto && !autoArmed) {
          setAutoArmed(true);
          return;
        }
        advance(1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  useEffect(() => {
    if (!flags.audio && !(flags.auto && autoArmed)) return;
    const key = narrationKey(ch, step);
    const clip = liveNarrations[key] || narrations[key];
    const slideNow = doc?.chapters?.[ch]?.slides?.[step];
    const el = audioRef.current;
    if (!el) return;
    let advanced = false;
    const goNext = () => {
      if (advanced) return;
      advanced = true;
      advance(1);
    };
    if (clip?.audio) {
      el.src = clip.audio;
      el.play().catch(() => {});
      el.addEventListener("ended", goNext);
      const safetyMs = Math.max(
        4000,
        (clip.duration_ms || slideNow?.duration_ms || 0) + 800
      );
      const t = window.setTimeout(goNext, safetyMs);
      return () => {
        el.removeEventListener("ended", goNext);
        window.clearTimeout(t);
      };
    }
    el.removeAttribute("src");
    el.load();
    if (flags.auto && autoArmed) {
      const text =
        slideNow?.narration ||
        slideNow?.body ||
        clip?.text ||
        "";
      const ms =
        clip?.duration_ms ||
        slideNow?.duration_ms ||
        Math.max(2200, (text.length || 12) * 120);
      const t = window.setTimeout(goNext, ms);
      return () => window.clearTimeout(t);
    }
  }, [ch, step, flags.audio, flags.auto, autoArmed, doc, liveNarrations]);

  const chapter = chapters[ch];
  const renderStep = chapter?.steps[step];
  document.title = pageTitle;

  const shellW = Math.round(stageWidth * scale);
  const shellH = Math.round(stageHeight * scale);

  return (
    <div
      className="viewport"
      style={
        {
          ["--accent"]: theme.accent,
          ["--accent-soft"]: theme.accentSoft || "transparent",
          ["--muted"]: theme.muted,
          ["--ink"]: theme.ink,
          ["--bg"]: theme.bg,
          ["--bg2"]: theme.bg2 || theme.bg,
          ["--surface"]: theme.surface,
          ["--line"]: theme.line,
          ["--font-display"]: theme.fontDisplay,
          ["--font-body"]: theme.fontBody,
          ["--grain"]: String(theme.grain ?? 0.045),
          color: theme.ink,
          fontFamily: theme.fontBody,
          background: theme.bg2 || theme.bg,
        } as Record<string, string>
      }
      onClick={() => advance(1)}
    >
      <div
        className="stage-shell"
        style={{
          width: shellW,
          height: shellH,
          position: "relative",
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        <div
          className="stage"
          style={{
            width: stageWidth,
            height: stageHeight,
            background: theme.bg,
            transform: `scale(${scale})`,
            transformOrigin: "top left",
            fontFamily: theme.fontBody,
            position: "absolute",
            left: 0,
            top: 0,
          }}
          data-aspect={aspect}
        >
          <div className="stage-bg" />
          {!cleanRecord && (
            <>
              <div className="folio folio-tl">{pageTitle.slice(0, 18)}</div>
              <div className="folio folio-tr">
                {String(flatIndex + 1).padStart(2, "0")} / {String(totalSteps).padStart(2, "0")}
              </div>
              <div className="folio folio-bl">{chapters[ch]?.title || ""}</div>
            </>
          )}
          {!cleanRecord && (
            <div className="hint">
              {aspect}
              {flags.auto ? (autoArmed ? " · AUTO" : " · 空格开始") : " · ←→ · F"}
            </div>
          )}
          {flags.auto && !autoArmed && (
            <div className="slide">
              <div className="slide-inner" style={{ textAlign: "left", maxWidth: "14em" }}>
                <p className="eyebrow">Record</p>
                <h1>按空格开始</h1>
                <hr className="rule" />
                <p className="body">浏览器录制或 OBS 开录后，再按空格开播。F 进入全屏。</p>
              </div>
            </div>
          )}
          {!(flags.auto && !autoArmed) && renderStep
            ? renderStep({ themeInk: theme.ink })
            : null}
          {!cleanRecord && (
            <div className="chrome" onClick={(e) => e.stopPropagation()}>
              <button type="button" onClick={() => advance(-1)}>
                上一步
              </button>
              <div className="bar">
                <i
                  style={{
                    width: `${((flatIndex + 1) / Math.max(1, totalSteps)) * 100}%`,
                  }}
                />
              </div>
              <button type="button" onClick={() => advance(1)}>
                下一步
              </button>
            </div>
          )}
        </div>
      </div>
      <audio ref={audioRef} preload="auto" />
    </div>
  );
}
