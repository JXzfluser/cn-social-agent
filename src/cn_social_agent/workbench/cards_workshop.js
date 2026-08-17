/** Knowledge card workshop — loaded by index.html as /static/cards_workshop.js */
(function (global) {
  const defaultCover = {
    seriesEn: "AI TALENT MAP",
    seriesCn: "AI 岗位能力图谱",
    title: "AI 招聘能力图谱",
    gradientPart: "",
    description: "三张卡片拆解智能体编排、RAG 工程与模型原生交付：各含定义、机制与易错点、可检验的落地案例。",
    tags: ["Agent 编排", "RAG 工程", "全栈交付"],
    imageUrl: "",
    edition: "",
    marketNote: "",
  };
  const defaultKnowledge = [
    {
      seriesEn: "AI TALENT MAP", seriesCn: "AI 岗位能力图谱",
      topicTitle: "智能体编排与协同",
      card_kind: "concept",
      concept: "Agent 不是「多聊几轮」：它按目标拆解步骤、选择工具、写入状态，失败可回退。常见误解是把单次 Function Calling 当成完整智能体系统。",
      keyPoint: "- 【机制】规划→工具调用（含 MCP）→状态写入→失败回退的闭环\n- 【易错】无超时/权限边界时，工具失败会循环调用或越权\n- 【检验】能画出状态机，并用 LangGraph 复现一次失败回退",
      realPoints: [],
      flow: ["规划", "工具调用", "状态回写", "交付"],
      example: "规划 Agent 拆需求后，检索/编码/质检三类执行 Agent 并行产出；质检失败回写规划节点，最终交付带来源引用的报告。",
      quote: "", source: "", metric: "", metric_note: "", compare_left: "", compare_right: "",
    },
    {
      seriesEn: "AI TALENT MAP", seriesCn: "AI 岗位能力图谱",
      topicTitle: "RAG 检索工程化",
      card_kind: "steps",
      concept: "RAG 用「先检索后生成」把回答钉在可控语料上；质量取决于切片、召回与重排，不是换更大模型。误解：向量库上线即等于知识库可用。",
      keyPoint: "- 【机制】解析→切片→Embedding→多路召回→Rerank→带出处生成\n- 【易错】切片过碎丢上下文，或只靠向量忽略关键词召回\n- 【检验】抽 20 问对比命中原文率与幻觉率是否可量化",
      realPoints: [],
      flow: ["切片", "召回", "重排", "带出处"],
      example: "制度库接入后，提问先命中条款再生成答复；答案旁标注文档名与段落，人工可一键跳转复核。",
      quote: "", source: "", metric: "", metric_note: "", compare_left: "", compare_right: "",
    },
    {
      seriesEn: "AI TALENT MAP", seriesCn: "AI 岗位能力图谱",
      topicTitle: "模型原生全栈交付",
      card_kind: "keypoints",
      concept: "模型原生交付把推理做成产品能力：流式会话、路由降级、观测与部署一体，而不是页面上挂一个 Chat API。误解：会调 SDK 就算全栈 AI。",
      keyPoint: "- 【机制】SSE/WebSocket 流式、会话状态、模型路由与超时降级\n- 【易错】同步阻塞易超时；缺 token/费用与错误可观测\n- 【检验】能演示「界面→API→路由→部署」闭环并压测并发",
      realPoints: [],
      flow: ["界面", "流式API", "路由", "部署"],
      example: "用 FastAPI + SSE 推流，前端按 token 渲染；主模型超时自动切备用模型，并在面板展示延迟与失败原因。",
      quote: "", source: "", metric: "", metric_note: "", compare_left: "", compare_right: "",
    },
  ];

  const VISUAL_STYLES = {
    academic: { id: "academic", label: "学术蓝", accent: "#1d4ed8", accent2: "#1e3a8a", ink: "#0f172a", muted: "#475569", paper: "#f8fafc", paper2: "#eef2ff", paper3: "#e0e7ff", soft: "rgba(29,78,216,0.10)" },
    warm: { id: "warm", label: "暖文学", accent: "#9a3412", accent2: "#7c2d12", ink: "#1c1917", muted: "#78716c", paper: "#faf6f1", paper2: "#f3ebe3", paper3: "#e7d9cc", soft: "rgba(154,52,18,0.10)" },
    tech: { id: "tech", label: "暗科技", accent: "#22d3ee", accent2: "#0891b2", ink: "#e2e8f0", muted: "#94a3b8", paper: "#0f172a", paper2: "#111827", paper3: "#1e293b", soft: "rgba(34,211,238,0.12)" },
    magazine: { id: "magazine", label: "杂志红", accent: "#be123c", accent2: "#9f1239", ink: "#1c1917", muted: "#78716c", paper: "#fff7f7", paper2: "#ffe4e6", paper3: "#fecdd3", soft: "rgba(190,18,60,0.10)" },
    mono: { id: "mono", label: "极简黑白", accent: "#171717", accent2: "#404040", ink: "#0a0a0a", muted: "#525252", paper: "#fafafa", paper2: "#f5f5f5", paper3: "#e5e5e5", soft: "rgba(23,23,23,0.08)" },
  };
  const CARD_KINDS = [
    { id: "quote", label: "金句" },
    { id: "keypoints", label: "要点" },
    { id: "compare", label: "对比" },
    { id: "steps", label: "步骤" },
    { id: "data", label: "数据" },
    { id: "concept", label: "概念" },
  ];
  const DIAGRAM_TYPES = [
    { id: "flow", label: "流程 flow" },
    { id: "cycle", label: "循环 cycle" },
    { id: "compare", label: "对比 compare" },
    { id: "stack", label: "分层 stack" },
    { id: "callout", label: "强调 callout" },
    { id: "bullets", label: "要点 bullets" },
  ];
  const CAT_DEFAULT_STYLE = {
    hiring_insight: "academic",
    product_explain: "tech",
    skill_roadmap: "warm",
    industry_brief: "magazine",
  };

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));
  }

  function createWorkshop(opts) {
    const $ = (id) => document.getElementById(id);
    const api = opts.api;
    const onLlmRefresh = opts.onLlmRefresh || (() => {});
    const state = {
      cover: null,
      knowledge: [],
      frontMatter: null,
      sources: [],
      evidencePack: { evidences: [], count: 0 },
      packId: "",
      activeTab: "cover",
      activeHistoryId: "",
      exporting: false,
      publishing: false,
      scanning: false,
      researching: false,
      composing: false,
      inited: false,
      category: "hiring_insight",
      categories: [],
      footerLabel: "招聘洞察",
      noteLabel: "市场信号",
      isTemplatePreview: false,
      qualityWarning: "",
      qualityGatePass: true,
      handoff: null,
      contentProjectId: "",
    };

    function degradedComposeMessage(data) {
      if (!data) return "";
      if (data.mode === "cached" || data.llmError) {
        const reason = String(data.llmError || "").trim();
        return `成刊已降级：AI 生成失败，当前内容来自内置模板${reason ? `（${reason}）` : ""}。建议重试成刊。`;
      }
      const depth = data.depth || {};
      if (depth && depth.ok === false) {
        return depth.hint || ("成刊未达标：" + ((depth.failed || []).slice(0, 4).join("、") || "质检未过"));
      }
      if (data.quality_gate_pass === false && data.quality_hint) {
        return data.quality_hint;
      }
      const padded = (data.knowledge || []).filter((k) => k && k.paddedFromTheme).length;
      if (padded) {
        return `有 ${padded} 张卡使用了模板补全（非证据成刊），导出前请核对内容。`;
      }
      return "";
    }

    function renderQualityPanelFromState(data) {
      const QP = global.QualityPanel;
      const panel = $("kcQualityPanel");
      const errHost = $("kcActionError");
      if (!QP || !panel) return;
      const depth = (data && data.depth) || state.lastDepth;
      if (!depth && !(data && data.quality_items)) {
        QP.clear(panel);
        if (errHost) QP.clear(errHost);
        return;
      }
      const report = data && data.quality_items
        ? {
            ok: !!(data.quality_gate_pass !== false && (!depth || depth.ok !== false)),
            track: "journal",
            title: "成刊质量",
            items: data.quality_items,
            blockers: (data.quality_items || [])
              .filter((i) => i.status === "fail")
              .map((i) => i.label + (i.detail ? "（" + i.detail + "）" : "")),
            hint: data.quality_hint || (depth && depth.hint) || "",
          }
        : QP.fromJournalDepth(depth);
      QP.render(panel, report, {
        blockLabel: report.ok ? "" : "导出被拦截",
      });
      if (errHost) {
        if (data && (data.llmError || data.mode === "cached")) {
          QP.renderError(errHost, data.llmError || "成刊已降级为模板", {
            onAction: (id) => {
              if (id === "switch_model" && global.openLlmSettings) global.openLlmSettings();
              else if (id === "retry" || id === "retry_compose") composeJournal().catch(() => {});
            },
          });
        } else if (!report.ok && report.blockers && report.blockers.length) {
          QP.renderError(
            errHost,
            {
              code: "journal_quality",
              title: "成刊质检未过",
              reason: "还差：" + report.blockers.slice(0, 4).join("、"),
              detail: report.hint || "",
              actions: [
                { id: "retry", label: "重新成刊" },
                { id: "force_export", label: "仍要强制导出" },
              ],
            },
            {
              onAction: (id) => {
                if (id === "retry") composeJournal().catch(() => {});
                if (id === "force_export") exportAll({ force: true }).catch(() => {});
              },
            }
          );
        } else {
          QP.clear(errHost);
        }
      }
    }

    function currentCat() {
      return state.categories.find((c) => c.id === state.category) || {
        id: "hiring_insight",
        label: "招聘洞察",
        topic_label: "主题",
        topic_placeholder: "",
        action_label: "深采并成刊",
        description: "",
        default_topics: [],
        cover_layout: "classic",
        know_layout: "talent",
        palette: "teal",
        decor: "rings",
        template_label: "能力图谱",
        seriesEn: "AI TALENT MAP",
        seriesCn: "AI 岗位能力图谱",
        default_title: "AI 招聘能力图谱",
        preview: {},
      };
    }

    function applyCategoryUI() {
      const cat = currentCat();
      state.footerLabel = cat.footer_label || cat.label || "知识卡片";
      state.noteLabel = cat.note_label || "市场信号";
      const label = $("kcTopicLabel");
      if (label) label.textContent = cat.topic_label || "主题";
      const input = $("kcRolesInput");
      if (input) {
        input.placeholder = cat.topic_placeholder || "";
      }
      const scanBtn = $("kcScanBtn");
      if (scanBtn && !state.scanning) scanBtn.textContent = "快扫";
      const hint = $("kcCatHint");
      if (hint) {
        const tpl = cat.template_label || cat.label || "";
        hint.textContent = `${cat.description || ""}${tpl ? " · 模版：" + tpl : ""}`;
      }
      const meta = $("kcPreviewMeta");
      if (meta) {
        const tpl = cat.template_label || "";
        const layout = cat.cover_layout || "classic";
        meta.textContent = state.isTemplatePreview
          ? `模版预览 · ${tpl} · ${layout}`
          : `${cat.label || "卡片"} · ${tpl || "封面 + 知识点"}`;
      }
      document.querySelectorAll("#kcCatList .kc-cat").forEach((b) => {
        b.classList.toggle("active", b.dataset.id === state.category);
      });
    }

    function showTemplatePreview() {
      const cat = currentCat();
      const prev = cat.preview || {};
      const pc = prev.cover || {};
      const pk = (prev.knowledge || [])[0] || {};
      state.isTemplatePreview = true;
      state.activeHistoryId = "";
      state.cover = {
        seriesEn: cat.seriesEn || "SERIES",
        seriesCn: cat.seriesCn || "知识卡片",
        title: pc.title || cat.default_title || cat.label || "模版预览",
        gradientPart: "",
        description: pc.description || cat.description || "",
        tags: Array.isArray(pc.tags) ? pc.tags.slice() : [],
        imageUrl: "",
        edition: "预览",
        marketNote: pc.marketNote || "",
      };
      state.knowledge = [
        {
          seriesEn: state.cover.seriesEn,
          seriesCn: state.cover.seriesCn,
          topicTitle: pk.topicTitle || "示例知识点",
          concept: pk.concept || "",
          keyPoint: pk.keyPoint || "",
          realPoints: [],
          flow: Array.isArray(pk.flow) ? pk.flow.slice() : [],
          example: pk.example || "",
        },
      ];
      state.frontMatter = null;
      state.activeTab = "cover";
      if ($("kcScanNote")) {
        $("kcScanNote").textContent = `模版预览：${cat.template_label || cat.label}（切换分类可对比；点击「深采」或「快扫」生成真实内容）`;
        $("kcScanNote").className = "status";
      }
      applyCategoryUI();
      syncEditionInput(state.cover);
      showSources();
      renderTabs();
      renderEditor();
      renderPreview();
      syncPublishBtn();
    }

    function renderCategories() {
      const box = $("kcCatList");
      if (!box) return;
      box.innerHTML = state.categories.map((c) =>
        `<button type="button" class="kc-cat ${c.id === state.category ? "active" : ""}" data-id="${esc(c.id)}">
          <span class="n">${esc(c.label)}</span>
          <span class="d">${esc(c.template_label || c.description || "")}</span>
        </button>`
      ).join("");
      box.querySelectorAll(".kc-cat").forEach((b) => {
        b.onclick = () => {
          const next = b.dataset.id;
          if (next === state.category && state.isTemplatePreview) return;
          state.category = next;
          const cat = currentCat();
          const input = $("kcRolesInput");
          if (input && !(input.value || "").trim() && cat.default_topics && cat.default_topics.length) {
            input.value = cat.default_topics.join("、");
          }
          showTemplatePreview();
        };
      });
      applyCategoryUI();
    }

    function editionNumber(c) {
      const m = String((c && c.edition) || "").match(/(\d+)/);
      return m ? Math.max(1, parseInt(m[1], 10)) : 1;
    }

    function hashStr(s) {
      let h = 0;
      const t = String(s || "");
      for (let i = 0; i < t.length; i++) h = ((h << 5) - h + t.charCodeAt(i)) | 0;
      return Math.abs(h);
    }

    /** Tag / title mood → illustration + color family. */
    function tagMood(tags, title, description) {
      const j = [...(tags || []), title || "", description || ""].join(" ").toLowerCase();
      if (/agent|编排|智能体|langgraph|mcp|协同|工具调用/.test(j)) return "agent";
      if (/rag|检索|向量|embedding|知识库|召回|rerank/.test(j)) return "rag";
      if (/招聘|面试|岗位|人才|jd|猎头|候选人|能力图谱/.test(j)) return "hire";
      if (/口播|视频|抖音|成片|制片|剪辑/.test(j)) return "media";
      if (/产品|交付|全栈|发布|工作台|功能|场景/.test(j)) return "ship";
      if (/路线|技能|成长|学习|入门|进阶|里程碑/.test(j)) return "road";
      if (/行业|趋势|市场|简报|热点|洞察/.test(j)) return "pulse";
      return "generic";
    }

    /** Drop mode/meta chips from hero so semantic tags lead the cover. */
    function displayTags(tags) {
      const skip = /^(实时扫描|内置数据|缓存|ai生成|示例)$/i;
      const list = (tags || []).map((t) => String(t || "").trim()).filter(Boolean);
      const kept = list.filter((t) => !skip.test(t));
      return (kept.length ? kept : list).slice(0, 5);
    }

    /** Mood-first palette; category is fallback when mood is generic. */
    function resolvePaletteName(mood, catId, catPalette, seed) {
      const byMood = {
        agent: "teal",      // 编排：青绿，偏系统/协作
        rag: "ocean",       // 检索：海蓝，偏信息流
        hire: "teal",       // 招聘：与能力图谱一致
        media: "copper",    // 口播/视频：暖铜，偏内容创作
        ship: "copper",     // 产品交付：暖色行动感
        road: "forest",     // 技能路线：森林绿生长感
        pulse: "ink",       // 行业速览：墨蓝资讯感
        generic: null,
      };
      const byCat = {
        hiring_insight: "teal",
        product_explain: "ocean",
        skill_roadmap: "forest",
        industry_brief: "ink",
      };
      const moodName = byMood[mood];
      if (moodName) return moodName;
      return byCat[catId] || catPalette || "teal";
    }

    /**
     * Category locks layout; mood + tags drive color & decor so covers match topic.
     */
    function coverTheme(c) {
      const cat = currentCat();
      const n = editionNumber(c);
      const tags = displayTags(c.tags);
      const seed = hashStr([c.title, tags.join("·"), c.description || "", cat.id || ""].join("|"));
      const mood = tagMood(tags, c.title, c.description);
      const palettes = {
        teal: { name: "teal", accent: "#0f766e", accent2: "#115e59", ink: "#0f172a", muted: "#3f5a55", paper: "#f4faf8", paper2: "#e8f3ef", paper3: "#d7e8e2", soft: "rgba(15,118,110,0.12)" },
        ink: { name: "ink", accent: "#1e3a5f", accent2: "#0f2744", ink: "#0b1220", muted: "#4a5b72", paper: "#f4f6f9", paper2: "#e8edf4", paper3: "#d8e0eb", soft: "rgba(30,58,95,0.12)" },
        ocean: { name: "ocean", accent: "#0369a1", accent2: "#075985", ink: "#0c1a24", muted: "#3d5a6e", paper: "#f2f8fb", paper2: "#e3f0f7", paper3: "#cfe4f0", soft: "rgba(3,105,161,0.12)" },
        forest: { name: "forest", accent: "#3f6212", accent2: "#365314", ink: "#14532d", muted: "#4d5c40", paper: "#f5f7f1", paper2: "#e9eee2", paper3: "#d8e2cc", soft: "rgba(63,98,18,0.12)" },
        slate: { name: "slate", accent: "#475569", accent2: "#334155", ink: "#0f172a", muted: "#64748b", paper: "#f8fafc", paper2: "#f1f5f9", paper3: "#e2e8f0", soft: "rgba(71,85,105,0.10)" },
        copper: { name: "copper", accent: "#9a3412", accent2: "#7c2d12", ink: "#1c1917", muted: "#6b5348", paper: "#faf6f3", paper2: "#f3ebe4", paper3: "#e8d9cc", soft: "rgba(154,52,18,0.12)" },
      };
      const styleId = (c.visual_style || state.visual_style || CAT_DEFAULT_STYLE[cat.id] || "").trim();
      let p;
      let paletteName;
      if (styleId && VISUAL_STYLES[styleId]) {
        p = { ...VISUAL_STYLES[styleId], name: styleId };
        paletteName = styleId;
      } else {
        paletteName = resolvePaletteName(mood, cat.id, cat.palette, seed);
        p = { ...(palettes[paletteName] || palettes.teal) };
        if (seed % 2 === 1) {
          p = { ...p, accent: p.accent2, accent2: p.accent };
        }
      }
      const decorByMood = {
        agent: "nodes", rag: "layers", hire: "rings", media: "grid",
        ship: "grid", road: "arcs", pulse: "bars", generic: cat.decor || "rings",
      };
      const hookStyles = ["banner", "stack", "orbit", "rail"];
      return {
        ...p,
        layout: cat.cover_layout || "classic",
        decor: decorByMood[mood] || cat.decor || "rings",
        knowLayout: cat.know_layout || "talent",
        issue: n || 1,
        seed,
        mood,
        paletteName,
        visualStyle: styleId || "",
        hookStyle: hookStyles[seed % hookStyles.length],
        templateLabel: cat.template_label || cat.label || "",
        tagCount: tags.length,
      };
    }

    function decorGeometry(theme, tags) {
      const a = theme.accent;
      const soft = theme.soft;
      const muted = "rgba(100,116,139,0.22)";
      const seed = theme.seed || 0;
      const label = clipUi((tags && tags[0]) || String(theme.issue).padStart(2, "0"), 6);
      const ox = 20 + (seed % 40);
      const oy = 10 + ((seed >> 3) % 30);

      if (theme.decor === "nodes" || theme.mood === "agent") {
        return `<svg viewBox="0 0 480 720" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
          <circle cx="${280 + ox / 2}" cy="${240 + oy}" r="150" stroke="${a}" stroke-opacity="0.14" stroke-width="1.4"/>
          <circle cx="${280 + ox / 2}" cy="${240 + oy}" r="88" stroke="${a}" stroke-opacity="0.22" stroke-width="1.4"/>
          <circle cx="200" cy="200" r="22" fill="${soft}" stroke="${a}" stroke-opacity="0.5"/>
          <circle cx="360" cy="260" r="18" fill="${a}" fill-opacity="0.35"/>
          <circle cx="280" cy="360" r="26" fill="${soft}" stroke="${a}" stroke-opacity="0.55" stroke-width="1.5"/>
          <circle cx="180" cy="340" r="14" fill="${a}" fill-opacity="0.25"/>
          <path d="M200 200 L280 360 L360 260 L200 200" stroke="${a}" stroke-opacity="0.35" stroke-width="1.6"/>
          <path d="M180 340 L280 360" stroke="${a}" stroke-opacity="0.28" stroke-width="1.4"/>
          <text x="120" y="520" fill="${a}" fill-opacity="0.45" font-size="36" font-weight="750">${esc(label)}</text>
          <path d="M120 540 H360" stroke="${muted}" stroke-width="1.2"/>
        </svg>`;
      }
      if (theme.decor === "layers" || theme.mood === "rag") {
        return `<svg viewBox="0 0 480 720" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
          <rect x="90" y="160" width="300" height="70" rx="12" fill="${soft}" stroke="${a}" stroke-opacity="0.25"/>
          <rect x="110" y="250" width="300" height="70" rx="12" fill="${soft}" stroke="${a}" stroke-opacity="0.35"/>
          <rect x="130" y="340" width="300" height="70" rx="12" fill="${a}" fill-opacity="0.12" stroke="${a}" stroke-opacity="0.45"/>
          <rect x="150" y="430" width="300" height="70" rx="12" fill="${a}" fill-opacity="0.22" stroke="${a}" stroke-opacity="0.55"/>
          <path d="M240 230 V250 M260 320 V340 M280 410 V430" stroke="${a}" stroke-opacity="0.4" stroke-width="2"/>
          <text x="100" y="560" fill="${a}" fill-opacity="0.4" font-size="32" font-weight="700">${esc(label)}</text>
        </svg>`;
      }
      if (theme.decor === "grid") {
        return `<svg viewBox="0 0 480 720" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
          <rect x="80" y="120" width="320" height="480" stroke="${a}" stroke-opacity="0.18" stroke-width="1.2"/>
          <path d="M80 240 H400 M80 360 H400 M80 480 H400 M180 120 V600 M280 120 V600" stroke="${a}" stroke-opacity="0.12" stroke-width="1"/>
          <circle cx="${340 - (seed % 20)}" cy="${200 + oy}" r="36" fill="${soft}" stroke="${a}" stroke-opacity="0.35" stroke-width="1.2"/>
          <text x="100" y="170" fill="${a}" fill-opacity="0.4" font-size="40" font-weight="700">${esc(label)}</text>
        </svg>`;
      }
      if (theme.decor === "arcs") {
        return `<svg viewBox="0 0 480 720" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
          <path d="M60 640 Q240 ${100 + oy} 420 640" stroke="${a}" stroke-opacity="0.2" stroke-width="2" fill="none"/>
          <path d="M100 640 Q240 ${200 + oy} 380 640" stroke="${a}" stroke-opacity="0.28" stroke-width="1.6" fill="none"/>
          <path d="M140 640 Q240 ${300 + oy} 340 640" stroke="${a}" stroke-opacity="0.35" stroke-width="1.4" fill="none"/>
          <circle cx="240" cy="${360 + (seed % 40)}" r="18" fill="${soft}" stroke="${a}" stroke-opacity="0.4"/>
          <text x="140" y="200" fill="${a}" fill-opacity="0.35" font-size="34" font-weight="700">${esc(label)}</text>
        </svg>`;
      }
      if (theme.decor === "bars") {
        const h = [140, 260, 340, 420, 300].map((v, i) => v - ((seed >> i) % 40));
        return `<svg viewBox="0 0 480 720" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
          <rect x="100" y="${620 - h[0]}" width="48" height="${h[0]}" fill="${a}" fill-opacity="0.12"/>
          <rect x="168" y="${620 - h[1]}" width="48" height="${h[1]}" fill="${a}" fill-opacity="0.18"/>
          <rect x="236" y="${620 - h[2]}" width="48" height="${h[2]}" fill="${a}" fill-opacity="0.28"/>
          <rect x="304" y="${620 - h[3]}" width="48" height="${h[3]}" fill="${a}" fill-opacity="0.38"/>
          <rect x="372" y="${620 - h[4]}" width="48" height="${h[4]}" fill="${a}" fill-opacity="0.22"/>
          <path d="M90 180 H400" stroke="${muted}" stroke-width="1.2"/>
          <text x="100" y="160" fill="${a}" fill-opacity="0.4" font-size="32" font-weight="700">${esc(label)}</text>
        </svg>`;
      }
      return `<svg viewBox="0 0 480 720" fill="none" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
        <circle cx="${300 - ox / 3}" cy="${280 + oy / 2}" r="168" stroke="${a}" stroke-opacity="0.16" stroke-width="1.4"/>
        <circle cx="${300 - ox / 3}" cy="${280 + oy / 2}" r="112" stroke="${a}" stroke-opacity="0.22" stroke-width="1.4"/>
        <circle cx="${300 - ox / 3}" cy="${280 + oy / 2}" r="48" fill="${soft}" stroke="${a}" stroke-opacity="0.35" stroke-width="1.2"/>
        <path d="M120 520 H420" stroke="${muted}" stroke-width="1.2"/>
        <path d="M160 560 H380" stroke="${muted}" stroke-width="1.2"/>
        <rect x="210" y="430" width="180" height="120" rx="4" stroke="${a}" stroke-opacity="0.22" stroke-width="1.2"/>
        <path d="M230 470 H370 M230 500 H330" stroke="${a}" stroke-opacity="0.55" stroke-width="2.2" stroke-linecap="round"/>
        <text x="220" y="490" fill="${a}" fill-opacity="0.55" font-size="22" font-weight="700">${esc(label)}</text>
      </svg>`;
    }

    /** Hero tag band — first thing eyes hit; style varies by seed. */
    function coverHookBand(tagList, theme) {
      if (!tagList.length) return "";
      const a = theme.accent;
      const style = theme.hookStyle || "banner";
      const hero = tagList[0];
      const rest = tagList.slice(1, 4);
      if (style === "orbit") {
        return `<div style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:0 0 22px;">
          <span style="padding:14px 26px;font-size:28px;font-weight:780;letter-spacing:.06em;color:#fff;background:${a};border-radius:999px;box-shadow:0 10px 28px ${a}33;">${esc(clipUi(hero, 12))}</span>
          ${rest.map((t, i) => `<span style="padding:10px 16px;font-size:18px;font-weight:650;color:${i ? theme.muted : theme.ink};background:${i ? "#fff" : theme.soft};border:1px solid ${a}40;border-radius:999px;">${esc(clipUi(t, 10))}</span>`).join("")}
        </div>`;
      }
      if (style === "rail") {
        return `<div style="display:grid;grid-template-columns:auto 1fr;gap:16px;align-items:stretch;margin:0 0 22px;max-width:720px;">
          <div style="min-width:160px;padding:20px 18px;background:${a};color:#fff;display:flex;flex-direction:column;justify-content:center;">
            <div style="font-size:12px;letter-spacing:.22em;opacity:.85;margin-bottom:8px;">HOOK</div>
            <div style="font-size:26px;font-weight:780;line-height:1.2;">${esc(clipUi(hero, 12))}</div>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:10px;align-content:center;">
            ${rest.map((t) => `<span style="padding:12px 16px;font-size:18px;font-weight:650;color:${theme.ink};background:#fff;border:1px solid ${a}40;">${esc(clipUi(t, 10))}</span>`).join("") || `<span style="color:${theme.muted};font-size:18px;">标签驱动本期构图</span>`}
          </div>
        </div>`;
      }
      if (style === "stack") {
        return `<div style="display:flex;flex-direction:column;gap:10px;margin:0 0 22px;max-width:560px;">
          ${tagList.slice(0, 3).map((t, i) => {
            const bg = i === 0 ? a : (i === 1 ? theme.soft : "#fff");
            const color = i === 0 ? "#fff" : theme.ink;
            const border = i === 0 ? "0" : `1px solid ${a}40`;
            return `<div style="padding:${i === 0 ? "16px 22px" : "12px 18px"};font-size:${i === 0 ? 26 : 20}px;font-weight:${i === 0 ? 780 : 650};color:${color};background:${bg};border:${border};">${esc(clipUi(t, 14))}</div>`;
          }).join("")}
        </div>`;
      }
      // banner
      return `<div style="margin:0 0 22px;max-width:720px;">
        <div style="display:inline-flex;align-items:center;gap:12px;padding:12px 14px 12px 12px;background:linear-gradient(90deg,${a} 0%,${theme.accent2} 100%);color:#fff;box-shadow:0 12px 32px ${a}28;">
          <span style="padding:6px 10px;background:rgba(255,255,255,.18);font-size:12px;letter-spacing:.2em;font-weight:700;">TAG</span>
          <span style="font-size:26px;font-weight:780;letter-spacing:.04em;">${esc(clipUi(hero, 14))}</span>
        </div>
        ${rest.length ? `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">${rest.map((t) => `<span style="padding:8px 14px;font-size:16px;font-weight:650;color:${a};background:${theme.soft};border:1px solid ${a}33;">${esc(clipUi(t, 10))}</span>`).join("")}</div>` : ""}
      </div>`;
    }

    /** TOC from knowledge cards — promise of what's inside. */
    function coverInsideStrip(theme, knowledge) {
      const all = knowledge || [];
      const topics = all
        .map((k) => String((k && k.topicTitle) || "").trim())
        .filter(Boolean);
      if (!topics.length) return "";
      const a = theme.accent;
      const compact = topics.length > 5;
      const rows = topics.map((t, i) =>
        `<div style="display:flex;align-items:baseline;gap:12px;padding:${compact ? "6px" : "10px"} 0;border-bottom:1px solid ${a}22;">
          <span style="font-size:14px;font-weight:750;letter-spacing:.14em;color:${a};min-width:2.2em;">${String(i + 1).padStart(2, "0")}</span>
          <span style="font-size:${compact ? 18 : 20}px;font-weight:650;color:${theme.ink};line-height:1.3;word-break:break-word;">${esc(t)}</span>
        </div>`
      ).join("");
      return `<div style="margin-top:26px;max-width:640px;padding:16px 18px;background:rgba(255,255,255,0.72);border:1px solid ${a}28;backdrop-filter:blur(6px);">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px;">
          <div style="font-size:13px;letter-spacing:.22em;color:${a};font-weight:750;">本期目录</div>
          <div style="font-size:13px;color:${theme.muted};">${all.length} 张知识点 · 翻开看</div>
        </div>
        ${rows}
      </div>`;
    }

    function clipUi(s, n) {
      const t = String(s ?? "").replace(/\s+/g, " ").trim();
      if (t.length <= n) return t;
      return t.slice(0, Math.max(0, n - 1)).replace(/[，。、；;,.\s]+$/g, "") + "…";
    }

    const COVER_QR_URL = "/static/assets/wechat-qr.png";

    /** Bottom-right brand QR — sized for 1080×1440 cover, scannable after 2× export. */
    function coverQrBlock(theme, opts = {}) {
      const size = opts.size || 128;
      const showCaption = opts.caption !== false;
      return `<div style="display:flex;flex-direction:column;align-items:center;gap:8px;flex-shrink:0;">
        <div style="padding:12px;background:#fff;border:1px solid ${theme.accent}2e;border-radius:4px;">
          <img src="${COVER_QR_URL}" alt="公众号二维码" width="${size}" height="${size}"
            style="display:block;width:${size}px;height:${size}px;object-fit:contain;" crossorigin="anonymous" />
        </div>
        ${showCaption
          ? `<div style="text-align:center;line-height:1.35;">
              <div style="font-size:14px;letter-spacing:.2em;color:${theme.accent};font-weight:750;">扫码关注</div>
              <div style="font-size:13px;letter-spacing:.08em;color:${theme.muted};margin-top:2px;">微信公众号</div>
            </div>`
          : ""}
      </div>`;
    }

    function coverFooterRow(theme, leftHtml) {
      return `<div style="flex-shrink:0;padding-top:22px;border-top:1px solid ${theme.accent}33;display:flex;align-items:flex-end;justify-content:space-between;gap:28px;">
        <div style="flex:1;min-width:0;">${leftHtml || ""}</div>
        ${coverQrBlock(theme)}
      </div>`;
    }

    function renderCoverTags(tagList, theme) {
      const n = tagList.length;
      const a = theme.accent;
      if (n === 0) return "";
      // Compact footer chips — hook band already carries the hero tag up top
      const chips = tagList.map((t, i) => {
        const styles = [
          `color:#fff;background:${a};border:0;`,
          `color:${theme.ink};background:#fff;border:1px solid ${a}48;`,
          `color:${a};background:${theme.soft};border:1px dashed ${a}59;`,
          `color:${theme.muted};background:#f8fafc;border:1px solid rgba(100,116,139,0.25);`,
        ];
        return `<span style="padding:10px 14px;font-size:16px;font-weight:650;letter-spacing:.03em;${styles[Math.min(i, 3)]}">${esc(clipUi(t, 10))}</span>`;
      }).join("");
      return `<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">${chips}</div>`;
    }

    function renderCoverHtml(c) {
      const theme = coverTheme(c);
      const tagList = displayTags(c.tags);
      const knowledge = state.knowledge || [];
      const hookHtml = coverHookBand(tagList, theme);
      const insideHtml = coverInsideStrip(theme, knowledge);
      const tagsHtml = renderCoverTags(tagList, theme);
      const a = theme.accent;
      const decorSvg = decorGeometry(theme, tagList);
      const decorBlock = c.imageUrl
        ? `<img src="${esc(c.imageUrl)}" alt="" style="position:absolute;right:28px;top:160px;width:440px;height:680px;object-fit:cover;opacity:.55;border:1px solid ${a}30;" />`
        : `<div style="position:absolute;right:12px;top:170px;width:440px;height:700px;opacity:.9;">${decorSvg}</div>`;
      const market = c.marketNote
        ? `<div style="margin-top:20px;max-width:640px;padding:14px 16px;border-left:4px solid ${a};background:${theme.soft};">
            <div style="font-size:15px;letter-spacing:.2em;margin-bottom:6px;color:${a};font-weight:700;">${esc(state.noteLabel)}</div>
            <div style="font-size:22px;line-height:1.5;color:${theme.muted};font-weight:400;">${esc(clipUi(c.marketNote, 56))}</div>
          </div>` : "";
      const editionLabel = c.edition || `第 ${theme.issue} 期`;
      const editionBadge = `<div style="display:inline-flex;align-items:center;gap:10px;padding:10px 18px;border:1px solid ${a}4d;background:rgba(255,255,255,0.88);">
            <span style="font-size:13px;letter-spacing:.22em;color:${a};font-weight:700;">ISSUE</span>
            <span style="font-size:22px;font-weight:750;color:${theme.ink};letter-spacing:.04em;">${esc(editionLabel)}</span>
          </div>`;
      const knowBadge = knowledge.length
        ? `<span style="font-size:14px;letter-spacing:.08em;color:${theme.muted};padding:8px 12px;border:1px solid ${a}33;background:rgba(255,255,255,.7);">${knowledge.length} 张知识点</span>`
        : "";
      const variantHint = state.isTemplatePreview
        ? `<span style="font-size:15px;color:${theme.muted};letter-spacing:.06em;">色板 · ${esc(theme.paletteName || theme.name)} · ${esc(theme.mood)}</span>`
        : "";
      const bg = `linear-gradient(165deg,${theme.paper} 0%,${theme.paper2} 48%,${theme.paper3} 100%)`;
      const wash = `radial-gradient(80% 55% at 95% -5%, ${theme.soft}, transparent 55%), radial-gradient(50% 45% at -5% 105%, rgba(148,163,184,0.14), transparent 65%)`;
      const previewBadge = state.isTemplatePreview
        ? `<div style="position:absolute;right:48px;top:36px;z-index:5;padding:8px 14px;background:${a};color:#fff;font-size:14px;font-weight:700;letter-spacing:.12em;">模版预览</div>`
        : "";
      const descClamp = insideHtml ? 2 : 3;
      const descLen = insideHtml ? 48 : 84;

      if (theme.layout === "masthead") {
        return `<div class="kc-canvas" data-export="cover" style="background:${bg};overflow:hidden;">
          ${previewBadge}
          <div style="position:absolute;inset:0;pointer-events:none;background:${wash};"></div>
          <div style="position:absolute;left:0;right:0;top:0;height:120px;background:${a};"></div>
          <div style="position:absolute;right:40px;bottom:80px;width:360px;height:520px;opacity:.85;">${c.imageUrl ? "" : decorSvg}</div>
          ${c.imageUrl ? `<img src="${esc(c.imageUrl)}" alt="" style="position:absolute;right:40px;bottom:80px;width:360px;height:520px;object-fit:cover;opacity:.5;" />` : ""}
          <div style="position:relative;z-index:2;height:100%;display:flex;flex-direction:column;padding:36px 72px 64px;box-sizing:border-box;">
            <div style="display:flex;align-items:center;justify-content:space-between;color:#fff;min-height:72px;">
              <div style="display:flex;align-items:center;gap:12px;">
                <span style="font-size:18px;letter-spacing:.28em;font-weight:750;">${esc(c.seriesEn)}</span>
                <span style="opacity:.7;font-size:20px;">${esc(c.seriesCn)}</span>
              </div>
              <div style="display:flex;align-items:center;gap:10px;">
                ${knowledge.length ? `<span style="font-size:14px;letter-spacing:.08em;color:rgba(255,255,255,.92);padding:8px 12px;border:1px solid rgba(255,255,255,.35);background:rgba(255,255,255,.12);">${knowledge.length} 张知识点</span>` : ""}
                <div style="padding:8px 14px;background:rgba(255,255,255,0.18);font-size:20px;font-weight:700;">${esc(editionLabel)}</div>
              </div>
            </div>
            <div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding-top:28px;max-width:700px;min-height:0;">
              ${variantHint ? `<div style="margin-bottom:12px;">${variantHint}</div>` : ""}
              ${hookHtml}
              <h1 style="font-size:64px;line-height:1.12;font-weight:800;color:${theme.ink};margin:0;letter-spacing:-0.03em;">${esc(c.title || "")}</h1>
              <div style="width:72px;height:5px;margin:22px 0;background:${a};"></div>
              <p style="font-size:26px;line-height:1.55;color:${theme.muted};margin:0;display:-webkit-box;-webkit-line-clamp:${descClamp};-webkit-box-orient:vertical;overflow:hidden;">${esc(clipUi(c.description, descLen))}</p>
              ${insideHtml}
              ${market}
            </div>
            ${coverFooterRow(theme, tagsHtml)}
          </div>
        </div>`;
      }

      if (theme.layout === "split") {
        const sideTags = tagList.map((t, i) =>
          `<div style="padding:14px 12px;margin-bottom:10px;font-size:${i === 0 ? 22 : 18}px;font-weight:${i === 0 ? 750 : 600};color:${i === 0 ? "#fff" : theme.ink};background:${i === 0 ? a : "#fff"};border:1px solid ${a}40;">${esc(clipUi(t, 10))}</div>`
        ).join("");
        const sideTopics = (knowledge || []).map((k, i) =>
          `<div style="padding:8px 0;border-top:1px solid ${a}22;font-size:15px;color:${theme.ink};line-height:1.35;word-break:break-word;">
            <span style="color:${a};font-weight:750;margin-right:6px;">${String(i + 1).padStart(2, "0")}</span>${esc(k.topicTitle || "")}
          </div>`
        ).join("");
        return `<div class="kc-canvas" data-export="cover" style="background:${bg};overflow:hidden;">
          ${previewBadge}
          <div style="position:absolute;inset:0;pointer-events:none;background:${wash};"></div>
          <div style="position:absolute;left:0;top:0;bottom:0;width:220px;background:${theme.paper2};border-right:1px solid ${a}28;padding:80px 20px 220px;box-sizing:border-box;">
            <div style="font-size:13px;letter-spacing:.2em;color:${a};font-weight:700;margin-bottom:20px;">TAGS</div>
            <div style="max-height:420px;overflow:hidden;">
              ${sideTags || `<div style="color:${theme.muted};font-size:16px;">本期标签</div>`}
            </div>
            ${sideTopics ? `<div style="margin-top:24px;"><div style="font-size:12px;letter-spacing:.18em;color:${a};font-weight:700;margin-bottom:8px;">INSIDE</div>${sideTopics}</div>` : ""}
            <div style="position:absolute;left:20px;right:20px;bottom:48px;">
              ${coverQrBlock(theme, { size: 120 })}
            </div>
          </div>
          <div style="position:absolute;right:20px;top:160px;width:320px;height:520px;opacity:.75;">${c.imageUrl ? "" : decorSvg}</div>
          <div style="position:relative;z-index:2;height:100%;margin-left:220px;padding:72px 64px 64px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:space-between;">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
                <div style="display:flex;align-items:center;gap:10px;">
                  <span style="font-size:17px;letter-spacing:.24em;font-weight:750;color:${a};">${esc(c.seriesEn)}</span>
                  <span style="font-size:18px;color:${theme.muted};">${esc(c.seriesCn)}</span>
                </div>
                <div style="display:flex;gap:8px;align-items:center;">${knowBadge}${editionBadge}</div>
              </div>
              ${variantHint ? `<div style="margin-top:14px;">${variantHint}</div>` : ""}
              ${hookHtml}
              <h1 style="font-size:58px;line-height:1.14;font-weight:800;color:${theme.ink};margin:8px 0 0;max-width:560px;">${esc(c.title || "")}</h1>
              <div style="width:64px;height:5px;margin:20px 0;background:${a};"></div>
              <p style="font-size:24px;line-height:1.55;color:${theme.muted};margin:0;max-width:560px;display:-webkit-box;-webkit-line-clamp:${descClamp};-webkit-box-orient:vertical;overflow:hidden;">${esc(clipUi(c.description, descLen))}</p>
              ${market}
            </div>
            <div style="font-size:16px;color:${theme.muted};letter-spacing:.12em;">CONTENT SPREAD · ${esc(String(theme.issue).padStart(2, "0"))} · ${esc(theme.mood)}</div>
          </div>
        </div>`;
      }

      if (theme.layout === "watermark") {
        return `<div class="kc-canvas" data-export="cover" style="background:${bg};overflow:hidden;">
          ${previewBadge}
          <div style="position:absolute;inset:0;pointer-events:none;background:${wash};"></div>
          <div style="position:absolute;right:-40px;top:80px;font-size:420px;line-height:0.8;font-weight:900;color:${a};opacity:0.07;letter-spacing:-0.06em;user-select:none;">${String(theme.issue).padStart(2, "0")}</div>
          <div style="position:absolute;left:0;top:0;bottom:0;width:10px;background:${a};"></div>
          ${decorBlock}
          <div style="position:relative;z-index:2;height:100%;display:flex;flex-direction:column;justify-content:space-between;padding:72px 72px 64px;box-sizing:border-box;">
            <div>
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px;">
                <div>
                  <div style="font-size:18px;letter-spacing:.28em;font-weight:750;color:${a};">${esc(c.seriesEn)}</div>
                  <div style="font-size:20px;color:${theme.muted};margin-top:6px;">${esc(c.seriesCn)}</div>
                </div>
                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end;">${knowBadge}${editionBadge}</div>
              </div>
              ${variantHint ? `<div style="margin-top:20px;">${variantHint}</div>` : ""}
              ${hookHtml}
              <h1 style="font-size:64px;line-height:1.1;font-weight:820;color:${theme.ink};margin:8px 0 0;max-width:700px;">${esc(c.title || "")}</h1>
              <div style="width:88px;height:6px;margin:24px 0 18px;background:${a};"></div>
              <p style="font-size:26px;line-height:1.55;color:${theme.muted};margin:0;max-width:640px;display:-webkit-box;-webkit-line-clamp:${descClamp};-webkit-box-orient:vertical;overflow:hidden;">${esc(clipUi(c.description, descLen))}</p>
              ${insideHtml}
              ${market}
            </div>
            ${coverFooterRow(theme, tagsHtml)}
          </div>
        </div>`;
      }

      return `<div class="kc-canvas" data-export="cover" style="background:${bg};overflow:hidden;">
        ${previewBadge}
        <div style="position:absolute;inset:0;pointer-events:none;background:${wash};"></div>
        <div style="position:absolute;left:0;top:0;bottom:0;width:10px;background:linear-gradient(180deg,${a} 0%,${theme.accent2} 100%);"></div>
        <div style="position:absolute;right:0;top:0;width:36%;height:100%;pointer-events:none;background:linear-gradient(90deg,transparent,${theme.soft});"></div>
        ${decorBlock}
        <div style="position:relative;z-index:2;height:100%;display:flex;flex-direction:column;justify-content:space-between;padding:72px 72px 64px;box-sizing:border-box;overflow:hidden;">
          <div style="min-height:0;flex:1;display:flex;flex-direction:column;">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-shrink:0;flex-wrap:wrap;">
              <div style="display:flex;align-items:center;gap:12px;">
                <span style="font-size:18px;letter-spacing:.28em;font-weight:750;color:${a};">${esc(c.seriesEn)}</span>
                <span style="width:1px;height:14px;background:rgba(100,116,139,0.4);"></span>
                <span style="font-size:20px;color:${theme.muted};">${esc(c.seriesCn)}</span>
              </div>
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">${knowBadge}${editionBadge}</div>
            </div>
            ${variantHint ? `<div style="margin-top:16px;">${variantHint}</div>` : ""}
            <div style="margin-top:18px;">${hookHtml}</div>
            <h1 style="font-size:62px;line-height:1.14;font-weight:780;color:${theme.ink};margin:4px 0 0;max-width:680px;letter-spacing:-0.03em;word-break:break-word;">
              ${esc(c.title || "")}
            </h1>
            <div style="width:72px;height:5px;margin:22px 0 18px;background:${a};flex-shrink:0;border-radius:2px;"></div>
            <p style="font-size:26px;line-height:1.55;font-weight:400;max-width:640px;color:${theme.muted};margin:0;display:-webkit-box;-webkit-line-clamp:${descClamp};-webkit-box-orient:vertical;overflow:hidden;">${esc(clipUi(c.description, descLen))}</p>
            ${insideHtml}
            ${market}
          </div>
          ${coverFooterRow(theme, tagsHtml)}
        </div>
      </div>`;
    }

    function splitPointLabel(raw) {
      const t = String(raw || "").replace(/^[-•·\s]+/, "").trim();
      const m = t.match(/^【(机制|易错|检验|定义|要点|实践)】\s*(.*)$/);
      if (m) return { label: m[1], text: m[2] || t };
      const m2 = t.match(/^(机制|易错|检验|常见陷阱|面试追问)[：:]\s*(.*)$/);
      if (m2) {
        const map = { 常见陷阱: "易错", 面试追问: "检验" };
        return { label: map[m2[1]] || m2[1], text: m2[2] || t };
      }
      return { label: "", text: t };
    }

    function pointIcon(label, color) {
      if (label === "易错") {
        return `<svg width="34" height="34" viewBox="0 0 28 28" fill="none"><path d="M14 4 L25 23 H3 Z" stroke="${color}" stroke-width="1.6" fill="rgba(180,83,9,0.10)"/><path d="M14 11 v6" stroke="${color}" stroke-width="1.8" stroke-linecap="round"/><circle cx="14" cy="20" r="1.2" fill="${color}"/></svg>`;
      }
      if (label === "检验") {
        return `<svg width="34" height="34" viewBox="0 0 28 28" fill="none"><circle cx="14" cy="14" r="10" stroke="${color}" stroke-width="1.6" fill="rgba(3,105,161,0.08)"/><path d="M9 14.5 l3.2 3.2 6.5-7" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`;
      }
      return `<svg width="34" height="34" viewBox="0 0 28 28" fill="none"><rect x="4" y="7" width="8" height="8" rx="1.5" stroke="${color}" stroke-width="1.5" fill="rgba(15,118,110,0.10)"/><rect x="16" y="13" width="8" height="8" rx="1.5" stroke="${color}" stroke-width="1.5" fill="rgba(15,118,110,0.06)"/><path d="M12 11 H16 M16 11 L14.5 9.5 M16 11 L14.5 12.5" stroke="${color}" stroke-width="1.4" stroke-linecap="round"/></svg>`;
    }

    function diagramNodesFrom(raw, fallbackLabels) {
      const out = [];
      for (const n of raw || []) {
        if (out.length >= 5) break;
        if (n && typeof n === "object" && n.label) {
          out.push({ label: String(n.label).trim(), note: String(n.note || "").trim() });
        } else if (typeof n === "string" && n.trim()) {
          out.push({ label: n.trim(), note: "" });
        }
      }
      if (!out.length && fallbackLabels && fallbackLabels.length) {
        for (const s of fallbackLabels) {
          if (out.length >= 5) break;
          const t = String(s || "").trim();
          if (t) out.push({ label: t, note: "" });
        }
      }
      return out.filter((n) => n.label).slice(0, 5);
    }

    function flowDiagram(nodesOrSteps, theme) {
      const a = (theme && theme.accent) || "#0f766e";
      const ink = (theme && theme.ink) || "#0f172a";
      const soft = (theme && theme.soft) || "rgba(15,118,110,0.04)";
      const items = diagramNodesFrom(nodesOrSteps).slice(0, 5);
      if (items.length < 2) return "";
      const nodes = items.map((n, i) => {
        const box = `<div style="min-width:0;flex:1;padding:14px 10px;text-align:center;border:1px solid ${a}48;background:#fff;">
          <div style="font-size:14px;letter-spacing:.14em;color:${a};margin-bottom:6px;font-weight:700;">${String(i + 1).padStart(2, "0")}</div>
          <div style="font-size:22px;line-height:1.3;color:${ink};font-weight:650;word-break:break-word;">${esc(n.label || "")}</div>
          ${n.note ? `<div style="margin-top:4px;font-size:15px;color:${(theme && theme.muted) || "#64748b"};line-height:1.35;">${esc(clipUi(n.note, 28))}</div>` : ""}
        </div>`;
        const arrow = i < items.length - 1
          ? `<div style="flex:0 0 32px;display:flex;align-items:center;justify-content:center;color:${a};font-size:26px;font-weight:700;">→</div>`
          : "";
        return box + arrow;
      }).join("");
      return `<div style="display:flex;align-items:stretch;gap:0;margin:0 0 20px;padding:16px 14px;border:1px solid ${a}29;background:${soft};">
        ${nodes}
      </div>`;
    }

    function cycleDiagram(nodes, theme) {
      const a = (theme && theme.accent) || "#0f766e";
      const ink = (theme && theme.ink) || "#0f172a";
      const soft = (theme && theme.soft) || "rgba(15,118,110,0.08)";
      const muted = (theme && theme.muted) || "#64748b";
      const items = diagramNodesFrom(nodes).slice(0, 5);
      if (items.length < 2) return "";
      const n = items.length;
      const size = 340;
      const cx = size / 2;
      const cy = size / 2;
      const r = 118;
      const dots = items.map((item, i) => {
        const ang = (-Math.PI / 2) + (i * 2 * Math.PI) / n;
        const x = cx + r * Math.cos(ang);
        const y = cy + r * Math.sin(ang);
        return `<div style="position:absolute;left:${x}px;top:${y}px;transform:translate(-50%,-50%);width:120px;text-align:center;">
          <div style="width:58px;height:58px;margin:0 auto 6px;border-radius:50%;background:${a};color:#fff;display:flex;align-items:center;justify-content:center;font-size:17px;font-weight:750;">${String(i + 1).padStart(2, "0")}</div>
          <div style="font-size:20px;font-weight:700;color:${ink};line-height:1.25;word-break:break-word;">${esc(item.label || "")}</div>
          ${item.note ? `<div style="font-size:13px;color:${muted};margin-top:2px;line-height:1.3;">${esc(clipUi(item.note, 20))}</div>` : ""}
        </div>`;
      }).join("");
      return `<div style="margin:0 0 20px;padding:18px;border:1px solid ${a}29;background:${soft};display:flex;justify-content:center;">
        <div style="position:relative;width:${size}px;height:${size}px;">
          <div style="position:absolute;left:50%;top:50%;width:${r * 2}px;height:${r * 2}px;margin-left:-${r}px;margin-top:-${r}px;border:2px dashed ${a}55;border-radius:50%;box-sizing:border-box;"></div>
          <div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:72px;height:72px;border-radius:50%;background:${a};color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:750;letter-spacing:.08em;">CYCLE</div>
          ${dots}
        </div>
      </div>`;
    }

    function stackDiagram(nodes, theme) {
      const a = (theme && theme.accent) || "#0f766e";
      const soft = (theme && theme.soft) || "rgba(15,118,110,0.08)";
      const muted = (theme && theme.muted) || "#64748b";
      const items = diagramNodesFrom(nodes).slice(0, 5);
      if (!items.length) return "";
      // bottom-up: last node is base (widest)
      const ordered = items.slice().reverse();
      const bars = ordered.map((item, i) => {
        const fromBottom = i;
        const widthPct = 72 + fromBottom * (28 / Math.max(ordered.length - 1, 1));
        const displayIdx = items.length - i;
        const bgAlpha = Math.round(28 + fromBottom * (50 / Math.max(ordered.length - 1, 1)));
        return `<div style="width:${widthPct}%;margin:0 auto 8px;padding:14px 18px;background:${a}${bgAlpha.toString(16).padStart(2, "0")};box-sizing:border-box;display:flex;align-items:center;gap:12px;border:1px solid ${a}55;">
          <span style="font-size:14px;font-weight:750;letter-spacing:.12em;color:${a};">${String(displayIdx).padStart(2, "0")}</span>
          <div style="min-width:0;flex:1;">
            <div style="font-size:22px;font-weight:700;color:${(theme && theme.ink) || "#0f172a"};line-height:1.25;word-break:break-word;">${esc(item.label || "")}</div>
            ${item.note ? `<div style="font-size:14px;color:${muted};margin-top:2px;word-break:break-word;">${esc(item.note)}</div>` : ""}
          </div>
        </div>`;
      }).join("");
      return `<div style="margin:0 0 18px;padding:16px 12px 8px;border:1px solid ${a}29;background:${soft};">
        <div style="font-size:12px;letter-spacing:.18em;color:${muted};font-weight:700;margin-bottom:10px;text-align:center;">STACK · 自下而上</div>
        ${bars}
      </div>`;
    }

    function bulletsDiagram(nodes, theme) {
      const a = (theme && theme.accent) || "#0f766e";
      const ink = (theme && theme.ink) || "#0f172a";
      const soft = (theme && theme.soft) || "rgba(15,118,110,0.06)";
      const muted = (theme && theme.muted) || "#64748b";
      const items = diagramNodesFrom(nodes).slice(0, 5);
      if (!items.length) return "";
      const rows = items.map((item, i) =>
        `<div style="display:grid;grid-template-columns:48px 1fr;gap:14px;align-items:start;padding:12px 0;border-top:1px solid ${a}22;">
          <div style="width:40px;height:40px;border-radius:50%;background:${a};color:#fff;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:750;">${String(i + 1).padStart(2, "0")}</div>
          <div style="min-width:0;padding-top:4px;">
            <div style="font-size:22px;font-weight:700;color:${ink};line-height:1.3;word-break:break-word;">${esc(item.label || "")}</div>
            ${item.note ? `<div style="margin-top:4px;font-size:16px;color:${muted};line-height:1.4;word-break:break-word;">${esc(item.note)}</div>` : ""}
          </div>
        </div>`
      ).join("");
      return `<div style="margin:0 0 18px;padding:4px 12px 8px;border:1px solid ${a}29;background:${soft};border-left:4px solid ${a};">
        ${rows}
      </div>`;
    }

    function calloutDiagram(nodes, extras, theme) {
      const a = (theme && theme.accent) || "#0f766e";
      const ink = (theme && theme.ink) || "#0f172a";
      const soft = (theme && theme.soft) || "rgba(15,118,110,0.08)";
      const muted = (theme && theme.muted) || "#64748b";
      const items = diagramNodesFrom(nodes);
      const ex = extras || {};
      const metric = String(ex.metric || (items[0] && items[0].label) || "").trim();
      const quote = String(ex.quote || (items[0] && items[0].note) || (items[1] && items[1].label) || "").trim();
      if (!metric && !quote) return "";
      const isMetricHeavy = metric && metric.length <= 16 && !quote;
      return `<div style="margin:0 0 18px;padding:28px 24px;border:1px solid ${a}33;background:${soft};text-align:center;">
        ${metric ? `<div style="font-size:${isMetricHeavy || metric.length <= 12 ? 72 : 40}px;line-height:1.05;font-weight:750;color:${a};letter-spacing:-0.02em;">${esc(clipUi(metric, 24))}</div>` : ""}
        ${quote ? `<div style="margin-top:${metric ? 14 : 0}px;font-size:26px;line-height:1.45;color:${ink};font-weight:600;">${esc(clipUi(quote, 48))}</div>` : ""}
        ${items[0] && items[0].note && items[0].note !== quote ? `<div style="margin-top:10px;font-size:16px;color:${muted};">${esc(clipUi(items[0].note, 24))}</div>` : ""}
      </div>`;
    }

    function compareDiagram(nodes, extras, theme) {
      const a = (theme && theme.accent) || "#0f766e";
      const ink = (theme && theme.ink) || "#0f172a";
      const soft = (theme && theme.soft) || "rgba(15,118,110,0.08)";
      const muted = (theme && theme.muted) || "#64748b";
      const panelBg = ink === "#e2e8f0" ? "rgba(255,255,255,0.06)" : "#fff";
      const items = diagramNodesFrom(nodes);
      const ex = extras || {};
      const left = (items[0] && (items[0].note ? `${items[0].label}：${items[0].note}` : items[0].label))
        || ex.left || "常见误解";
      const right = (items[1] && (items[1].note ? `${items[1].label}：${items[1].note}` : items[1].label))
        || ex.right || "正确做法";
      return `<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0 0 18px;">
        <div style="padding:22px 20px;border:1px solid ${a}33;background:${soft};">
          <div style="font-size:14px;letter-spacing:.2em;color:${muted};font-weight:700;margin-bottom:12px;">误区</div>
          <div style="font-size:24px;line-height:1.45;color:${ink};">${esc(clipUi(left, 48))}</div>
        </div>
        <div style="padding:22px 20px;border:1px solid ${a};background:${panelBg};">
          <div style="font-size:14px;letter-spacing:.2em;color:${a};font-weight:700;margin-bottom:12px;">正解</div>
          <div style="font-size:24px;line-height:1.45;color:${ink};">${esc(clipUi(right, 48))}</div>
        </div>
      </div>`;
    }

    function renderDiagram(diagram, ctx) {
      const c = ctx || {};
      const theme = c.theme || coverTheme(state.cover || {});
      const raw = diagram && typeof diagram === "object" ? diagram : {};
      let type = String(raw.type || "").toLowerCase();
      const fallbacks = Array.isArray(c.flow) ? c.flow : [];
      const nodes = diagramNodesFrom(raw.nodes, fallbacks);
      const known = { flow: 1, cycle: 1, compare: 1, stack: 1, callout: 1, bullets: 1 };
      if (!known[type]) type = nodes.length >= 2 ? "flow" : "bullets";
      const extras = {
        metric: c.metric || "",
        quote: c.quote || "",
        left: c.left || "",
        right: c.right || "",
      };
      if (type === "cycle") return cycleDiagram(nodes, theme) || flowDiagram(nodes, theme);
      if (type === "stack") return stackDiagram(nodes, theme) || bulletsDiagram(nodes, theme);
      if (type === "bullets") return bulletsDiagram(nodes, theme);
      if (type === "callout") return calloutDiagram(nodes, extras, theme) || bulletsDiagram(nodes, theme);
      if (type === "compare") return compareDiagram(nodes, extras, theme);
      return flowDiagram(nodes, theme) || bulletsDiagram(nodes, theme);
    }

    function hasGuidePromises(fm) {
      const guide = fm && fm.guide;
      return !!(guide && Array.isArray(guide.promises) && guide.promises.length);
    }

    function hasTocEntries(fm) {
      return !!(fm && Array.isArray(fm.toc) && fm.toc.length);
    }

    const DIAGRAM_KIND_DEFAULT = {
      steps: "flow",
      compare: "compare",
      data: "callout",
      quote: "callout",
      keypoints: "bullets",
      concept: "stack",
    };

    function stripPointText(raw) {
      return String(raw || "")
        .replace(/^[-•·\s]+/, "")
        .replace(/^【[^】]*】\s*/, "")
        .trim();
    }

    function looksTruncated(s) {
      const t = String(s ?? "").trim();
      return /[…⋯]$/.test(t) || /\.\.\.$/.test(t);
    }

    function clipComplete(s, n) {
      const t = String(s ?? "").replace(/\s+/g, " ").trim();
      if (t.length <= n) return t;
      let cutAt = n;
      const ch = t.slice(n, n + 1);
      if (ch && /[A-Za-z0-9_+.#-]/.test(ch)) {
        const re = /[A-Za-z][A-Za-z0-9_+.#-]*/g;
        let m;
        while ((m = re.exec(t))) {
          if (m.index < n && n <= m.index + m[0].length) {
            cutAt = (m[0].length - (n - m.index) <= 12) ? m.index + m[0].length : m.index;
            break;
          }
        }
      }
      const cut = t.slice(0, Math.max(cutAt, 1)).replace(/[，。、；;,.\s]+$/g, "");
      return cut || t.slice(0, n);
    }

    function shortStep(text, n) {
      const limit = n || 16;
      let s = stripPointText(text);
      if (!s) return "";
      if (looksTruncated(s)) s = s.replace(/[…⋯.]+$/g, "").trim();
      const head = (s.split(/[，。；;：:、]/)[0] || s).trim();
      const ident = head.match(/^([\u4e00-\u9fff]{1,8}[A-Za-z][A-Za-z0-9_+.#-]*)/);
      if (ident && ident[1].length >= 4) return ident[1];
      const en = head.match(/^([A-Za-z][A-Za-z0-9_+.#-]{2,})/);
      if (en) return en[1];
      return head.length <= limit ? head : clipComplete(head, limit);
    }

    function coercePoints(raw) {
      let items = [];
      if (Array.isArray(raw)) {
        items = raw.map((x) => String(x));
      } else {
        const s = String(raw || "").replace(/\r/g, "\n").trim();
        if (!s) return [];
        const looksLikeList = s.trimStart().startsWith("[") || s.includes("', '") || s.includes('", "');
        if (looksLikeList) {
          const frags = [];
          const re = /['"]([^'"]+?)['"]/g;
          let m;
          while ((m = re.exec(s))) frags.push(m[1]);
          items = frags.filter((f) => f.replace(/[-\s…⋯]/g, "") !== "");
        } else {
          items = s.split(/\n+/);
        }
      }
      return items
        .map((it) => String(it || "").replace(/^[-•·\s]+/, "").replace(/[…⋯]+$/, "").trim())
        .filter(Boolean);
    }

    function cardPoints(k) {
      if (k && Array.isArray(k.realPoints) && k.realPoints.length) {
        const pts = k.realPoints.map((p) => String(p || "").trim()).filter(Boolean);
        if (pts.length > 1 || !/^\[|', '|", "/.test(pts[0] || "")) return pts;
      }
      return coercePoints((k && k.keyPoint) || (k && k.realPoints));
    }

    function repairCardCopy(k) {
      if (!k || typeof k !== "object") return k;
      const pts = cardPoints(k);
      const flow = Array.isArray(k.flow) ? k.flow.map((x) => String(x || "").trim()).filter(Boolean) : [];
      if (!flow.length || flow.some(looksTruncated)) {
        const rebuilt = pts.slice(0, 5).map((p) => shortStep(p)).filter(Boolean);
        if (rebuilt.length) k.flow = rebuilt;
      }
      if (k.diagram && Array.isArray(k.diagram.nodes)
          && k.diagram.nodes.some((n) => looksTruncated((n && n.label) || n))) {
        k.diagram = { type: k.diagram.type, nodes: [] };
      }
      return k;
    }

    function nodesFromPoints(points) {
      const out = [];
      for (const p of points || []) {
        if (out.length >= 5) break;
        const text = stripPointText(p);
        if (!text) continue;
        const label = shortStep(text, 16);
        if (!label) continue;
        const rest = text.length > label.length
          ? text.slice(label.length).replace(/^[，。；;：:、\s]+/, "").slice(0, 40)
          : "";
        out.push({ label, note: rest });
      }
      return out;
    }

    /** Ensure every card has a usable diagram (for older history without diagram field). */
    function enrichCardDiagram(k) {
      if (!k || typeof k !== "object") return k;
      repairCardCopy(k);
      const kind = String(k.card_kind || "keypoints").toLowerCase();
      const existing = k.diagram && typeof k.diagram === "object" ? k.diagram : null;
      const hasNodes = existing && Array.isArray(existing.nodes) && existing.nodes.length >= 1
        && !existing.nodes.some((n) => looksTruncated((n && n.label) || n));
      if (hasNodes && existing.type) return k;
      const type = (existing && existing.type)
        || DIAGRAM_KIND_DEFAULT[kind]
        || "bullets";
      let nodes = hasNodes ? existing.nodes.slice() : [];
      const flowOk = Array.isArray(k.flow) && k.flow.length && !k.flow.some(looksTruncated);
      if (!nodes.length && flowOk) {
        nodes = k.flow.filter(Boolean).slice(0, 5).map((s) => ({ label: shortStep(s) || String(s), note: "" }));
      }
      if (!nodes.length) {
        nodes = nodesFromPoints(cardPoints(k));
      }
      if (type === "compare" && nodes.length < 2) {
        nodes = [
          { label: String(k.compare_left || "误区").slice(0, 14), note: "" },
          { label: String(k.compare_right || "正解").slice(0, 14), note: "" },
        ];
      }
      if (type === "callout" && !nodes.length) {
        nodes = [{ label: String(k.metric || (k.quote || "要点").slice(0, 14)).slice(0, 14), note: String(k.metric_note || "").slice(0, 40) }];
      }
      if (nodes.length < 2 && (type === "flow" || type === "cycle" || type === "stack" || type === "bullets")) {
        while (nodes.length < 3) nodes.push({ label: `要点${nodes.length + 1}`, note: "" });
      }
      k.diagram = { type, nodes: nodes.slice(0, 5) };
      return k;
    }

    /** Synthesize guide/toc when history predates frontMatter. */
    function enrichFrontMatter(fm, knowledge, cover) {
      const ks = Array.isArray(knowledge) ? knowledge : [];
      if (ks.length < 3) return fm && typeof fm === "object" ? fm : null;
      const base = (fm && typeof fm === "object" && !Array.isArray(fm)) ? { ...fm } : {};
      const guide = (base.guide && typeof base.guide === "object") ? { ...base.guide } : {};
      let promises = Array.isArray(guide.promises) ? guide.promises.filter((p) => String(p || "").trim()) : [];
      if (promises.length < 3) {
        promises = ks.slice(0, 3).map((k, i) => {
          const t = String((k && k.topicTitle) || `要点${i + 1}`);
          return `掌握${t}`.slice(0, 28);
        });
        while (promises.length < 3) promises.push(`带走要点${promises.length + 1}`);
      }
      guide.headline = guide.headline || "本期导读";
      guide.promises = promises.slice(0, 3);
      guide.meta = guide.meta || `${ks.length} 张知识卡 · ${(cover && cover.edition) || ""}`.trim();
      const toc = ks.map((k, i) => ({
        index: i + 1,
        title: String((k && k.topicTitle) || `卡片${i + 1}`),
        kind: String((k && k.card_kind) || "concept"),
        diagram: String((k && k.diagram && k.diagram.type) || DIAGRAM_KIND_DEFAULT[String((k && k.card_kind) || "").toLowerCase()] || "bullets"),
      }));
      return { guide, toc };
    }

    function pagesBeforeKnowledge() {
      let n = 1;
      const fm = state.frontMatter;
      if (hasGuidePromises(fm)) n += 1;
      if (hasTocEntries(fm)) n += 1;
      return n;
    }

    function renderGuideHtml(frontMatter, cover, themeIn) {
      const c = cover || state.cover || defaultCover;
      const theme = themeIn || coverTheme(c);
      const a = theme.accent;
      const guide = (frontMatter && frontMatter.guide) || {};
      const promises = (Array.isArray(guide.promises) ? guide.promises : [])
        .map((p) => String(p || "").trim()).filter(Boolean).slice(0, 3);
      if (!promises.length) return "";
      const headline = guide.headline || "本期导读";
      const meta = clipUi(guide.meta || "", 56);
      const bg = `linear-gradient(165deg,${theme.paper} 0%,${theme.paper2} 55%,${theme.paper3} 100%)`;
      const wash = `radial-gradient(60% 45% at 92% 6%, ${theme.soft}, transparent 62%), radial-gradient(45% 35% at 6% 94%, rgba(148,163,184,0.10), transparent 70%)`;
      const before = 1; // after cover
      const totalPages = pagesBeforeKnowledge() + (state.knowledge || []).length;
      const page = String(before + 1).padStart(2, "0");
      const list = promises.map((p, i) =>
        `<div style="display:grid;grid-template-columns:72px 1fr;gap:20px;align-items:start;padding:28px 0;border-top:1px solid ${a}33;">
          <div style="font-size:48px;line-height:1;font-weight:300;color:${a}55;font-variant-numeric:tabular-nums;">${String(i + 1).padStart(2, "0")}</div>
          <div style="font-size:36px;line-height:1.4;font-weight:650;color:${theme.ink};padding-top:6px;">${esc(clipUi(p, 28))}</div>
        </div>`
      ).join("");
      return `<div class="kc-canvas" data-export="guide" style="background:${bg};overflow:hidden;">
        <div style="position:absolute;inset:0;pointer-events:none;background:${wash};"></div>
        <div style="position:absolute;left:0;top:0;bottom:0;width:8px;background:${a};"></div>
        <div style="position:relative;z-index:2;height:100%;display:flex;flex-direction:column;padding:64px 72px 52px;box-sizing:border-box;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:36px;flex-shrink:0;">
            <span style="font-size:18px;letter-spacing:.28em;font-weight:700;color:${a};">${esc(c.seriesEn || "SERIES")}</span>
            <span style="width:1px;height:16px;background:rgba(100,116,139,0.45);"></span>
            <span style="font-size:20px;color:${theme.muted};">${esc(c.seriesCn || "知识卡片")}</span>
            <span style="margin-left:auto;font-size:14px;letter-spacing:.16em;color:${a};font-weight:700;padding:6px 10px;border:1px solid ${a}44;">导读</span>
          </div>
          <div style="font-size:15px;letter-spacing:.24em;color:${theme.muted};font-weight:600;margin-bottom:12px;">READER PROMISE</div>
          <h2 style="font-size:56px;line-height:1.15;font-weight:780;color:${theme.ink};margin:0 0 28px;letter-spacing:-0.02em;">${esc(headline)}</h2>
          <div style="width:72px;height:5px;background:${a};margin-bottom:12px;"></div>
          <div style="flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;">${list}</div>
          ${meta ? `<div style="margin-top:24px;padding:16px 18px;border-left:4px solid ${a};background:${theme.soft};font-size:20px;line-height:1.5;color:${theme.muted};">${esc(meta)}</div>` : ""}
          <div style="display:flex;justify-content:space-between;align-items:center;padding-top:18px;margin-top:20px;border-top:1px solid ${a}29;font-size:18px;color:${theme.muted};">
            <span>${esc(state.footerLabel || "知识卡片")} · 导读</span>
            <span style="letter-spacing:.2em;font-variant-numeric:tabular-nums;">${page} / ${String(totalPages).padStart(2, "0")}</span>
          </div>
        </div>
      </div>`;
    }

    function renderTocHtml(frontMatter, themeIn) {
      const c = state.cover || defaultCover;
      const theme = themeIn || coverTheme(c);
      const a = theme.accent;
      const toc = (frontMatter && Array.isArray(frontMatter.toc) ? frontMatter.toc : [])
        .filter((row) => row && (row.title || row.index));
      if (!toc.length) return "";
      const bg = `linear-gradient(165deg,${theme.paper} 0%,${theme.paper2} 55%,${theme.paper3} 100%)`;
      const wash = `radial-gradient(60% 45% at 92% 6%, ${theme.soft}, transparent 62%), radial-gradient(45% 35% at 6% 94%, rgba(148,163,184,0.10), transparent 70%)`;
      const before = pagesBeforeKnowledge();
      const pageNum = hasGuidePromises(frontMatter) ? 3 : 2;
      const totalPages = before + (state.knowledge || []).length;
      const kindLabel = (id) => ((CARD_KINDS.find((x) => x.id === id) || {}).label || id || "要点");
      const compact = toc.length > 6;
      const rows = toc.map((row, i) => {
        const idx = String(row.index != null ? row.index : i + 1).padStart(2, "0");
        const kind = String(row.kind || "keypoints").toLowerCase();
        const diagram = String(row.diagram || "").toLowerCase();
        return `<div style="display:grid;grid-template-columns:72px 1fr auto;gap:16px;align-items:center;padding:${compact ? "10px" : "18px"} 0;border-top:1px solid ${a}29;">
          <div style="font-size:${compact ? 32 : 40}px;font-weight:300;color:${a}50;font-variant-numeric:tabular-nums;line-height:1;">${esc(idx)}</div>
          <div style="min-width:0;">
            <div style="font-size:${compact ? 22 : 26}px;font-weight:700;color:${theme.ink};line-height:1.35;word-break:break-word;">${esc(row.title || `知识点 ${idx}`)}</div>
            ${diagram ? `<div style="margin-top:6px;font-size:14px;letter-spacing:.12em;color:${theme.muted};">图示 · ${esc(diagram)}</div>` : ""}
          </div>
          <span style="font-size:14px;letter-spacing:.1em;font-weight:700;color:${a};padding:8px 12px;border:1px solid ${a}44;white-space:nowrap;">${esc(kindLabel(kind))}</span>
        </div>`;
      }).join("");
      return `<div class="kc-canvas" data-export="toc" style="background:${bg};overflow:hidden;">
        <div style="position:absolute;inset:0;pointer-events:none;background:${wash};"></div>
        <div style="position:absolute;left:0;top:0;bottom:0;width:8px;background:${a};"></div>
        <div style="position:relative;z-index:2;height:100%;display:flex;flex-direction:column;padding:64px 72px 52px;box-sizing:border-box;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:36px;flex-shrink:0;">
            <span style="font-size:18px;letter-spacing:.28em;font-weight:700;color:${a};">${esc(c.seriesEn || "SERIES")}</span>
            <span style="width:1px;height:16px;background:rgba(100,116,139,0.45);"></span>
            <span style="font-size:20px;color:${theme.muted};">${esc(c.seriesCn || "知识卡片")}</span>
            <span style="margin-left:auto;font-size:14px;letter-spacing:.16em;color:${a};font-weight:700;padding:6px 10px;border:1px solid ${a}44;">目录</span>
          </div>
          <div style="font-size:15px;letter-spacing:.24em;color:${theme.muted};font-weight:600;margin-bottom:12px;">CONTENTS</div>
          <h2 style="font-size:52px;line-height:1.15;font-weight:780;color:${theme.ink};margin:0 0 8px;letter-spacing:-0.02em;">本期目录</h2>
          <div style="width:72px;height:5px;background:${a};margin:18px 0 8px;"></div>
          <div style="flex:1;min-height:0;overflow:hidden;">${rows}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;padding-top:18px;margin-top:12px;border-top:1px solid ${a}29;font-size:18px;color:${theme.muted};">
            <span>${toc.length} 张知识点</span>
            <span style="letter-spacing:.2em;font-variant-numeric:tabular-nums;">${String(pageNum).padStart(2, "0")} / ${String(totalPages).padStart(2, "0")}</span>
          </div>
        </div>
      </div>`;
    }

    function knowSectionLabels(layout) {
      if (layout === "product") {
        return {
          concept: ["核心能力", "CAPABILITY"],
          points: ["使用要点", "HOW TO USE"],
          example: ["上手路径", "PATH"],
          labels: ["能力", "边界", "检验"],
          colors: ["#0369a1", "#b45309", "#0f766e"],
          badge: "PRODUCT CARD",
        };
      }
      if (layout === "roadmap") {
        return {
          concept: ["阶段心智", "MINDSET"],
          points: ["里程碑", "MILESTONES"],
          example: ["最小项目", "PROJECT"],
          labels: ["必学", "练习", "过关"],
          colors: ["#3f6212", "#0369a1", "#9a3412"],
          badge: "ROADMAP STAGE",
        };
      }
      if (layout === "brief") {
        return {
          concept: ["趋势判断", "THESIS"],
          points: ["关键变量", "VARIABLES"],
          example: ["本周动作", "ACTION"],
          labels: ["信号", "风险", "指标"],
          colors: ["#1e3a5f", "#b45309", "#0369a1"],
          badge: "INDUSTRY BRIEF",
        };
      }
      return {
        concept: ["核心概念", "CONCEPT"],
        points: ["掌握要点", "TAKEAWAYS"],
        example: ["落地案例", "CASE"],
        labels: ["机制", "易错", "检验"],
        colors: ["#0f766e", "#b45309", "#0369a1"],
        badge: "LEARNING CARD",
      };
    }

    function renderKnowHtml(k, index, total) {
      enrichCardDiagram(k);
      const theme = coverTheme(state.cover || {});
      const layout = theme.knowLayout || "talent";
      const labels = knowSectionLabels(layout);
      const a = theme.accent;
      const kind = (k.card_kind || "keypoints").toLowerCase();
      const content = {
        concept: String(k.concept || ""),
        example: String(k.example || ""),
        quote: String(k.quote || k.concept || ""),
        source: clipUi(k.source || (state.cover && state.cover.source) || "", 40),
        metric: clipUi(k.metric || "", 24),
        metricNote: String(k.metric_note || ""),
        left: String(k.compare_left || ""),
        right: String(k.compare_right || ""),
      };
      const before = pagesBeforeKnowledge();
      const page = String(index + before + 1).padStart(2, "0");
      const totalStr = String(total + before).padStart(2, "0");
      const points = cardPoints(k).slice(0, 6);
      const flow = (k.flow && k.flow.length && !k.flow.some(looksTruncated)) ? k.flow : [];
      const diagramHtml = renderDiagram(k.diagram, {
        theme,
        flow,
        metric: content.metric,
        quote: content.quote,
        left: content.left,
        right: content.right,
      });
      const kindLabel = (CARD_KINDS.find((x) => x.id === kind) || {}).label || "要点";
      const inkBody = theme.ink === "#e2e8f0" ? "#e2e8f0" : "#1e293b";
      // Prefer slightly smaller type so full copy fits — no webkit-line-clamp on body text
      const conceptStyle = `font-size:26px;line-height:1.55;margin:0;color:${inkBody};`;
      const exampleStyle = `font-size:24px;line-height:1.55;margin:0;color:${inkBody};`;

      let bodyHtml = "";
      if (kind === "quote") {
        bodyHtml = `<section style="flex:1;display:flex;flex-direction:column;min-height:0;gap:18px;">
          ${diagramHtml || ""}
          <div style="flex:1;display:flex;flex-direction:column;justify-content:center;">
            <div style="font-size:100px;line-height:0.7;color:${a}40;font-weight:300;margin-bottom:8px;">“</div>
            <p style="font-size:36px;line-height:1.45;margin:0;color:${theme.ink};font-weight:650;">${esc(content.quote)}</p>
            ${content.source ? `<div style="margin-top:22px;font-size:20px;color:${theme.muted};letter-spacing:.06em;">—— ${esc(content.source)}</div>` : ""}
            ${content.concept && content.concept !== content.quote ? `<p style="margin-top:20px;${conceptStyle}">${esc(content.concept)}</p>` : ""}
          </div>
        </section>`;
      } else if (kind === "compare") {
        const compareBlock = compareDiagram(
          (k.diagram && k.diagram.nodes) || [],
          { left: content.left || (points[0] || "常见误解"), right: content.right || (points[1] || "正确做法") },
          theme
        );
        bodyHtml = `<section style="flex:1;min-height:0;display:flex;flex-direction:column;gap:18px;padding-top:4px;">
          ${compareBlock}
          ${points.length ? `<ul style="list-style:none;padding:0;margin:0;flex:1;">${points.slice(0, 4).map((p) => `<li style="padding:12px 0;border-top:1px solid ${a}29;font-size:24px;line-height:1.45;color:${inkBody};">${esc(p)}</li>`).join("")}</ul>` : ""}
          ${content.concept ? `<p style="${conceptStyle}">${esc(content.concept)}</p>` : ""}
        </section>`;
      } else if (kind === "data") {
        bodyHtml = `<section style="flex:1;display:flex;flex-direction:column;min-height:0;gap:16px;">
          ${diagramHtml || `<div style="padding:28px;border:1px solid ${a}33;background:${theme.soft};text-align:center;">
            <div style="font-size:88px;line-height:1;font-weight:750;color:${a};">${esc(content.metric || "—")}</div>
            <div style="margin-top:14px;font-size:26px;line-height:1.45;color:${theme.ink};">${esc(content.metricNote || "")}</div>
          </div>`}
          ${content.concept ? `<p style="${conceptStyle}">${esc(content.concept)}</p>` : ""}
          ${points.length ? `<ul style="list-style:none;padding:0;margin:0;flex:1;">${points.map((p) => `<li style="padding:12px 0;border-top:1px solid ${a}29;font-size:24px;line-height:1.45;color:${inkBody};">${esc(p)}</li>`).join("")}</ul>` : ""}
        </section>`;
      } else if (kind === "steps") {
        const steps = (points.length ? points : flow).slice(0, 6);
        bodyHtml = `<section style="flex:1;min-height:0;display:flex;flex-direction:column;padding-top:4px;gap:8px;">
          ${diagramHtml}
          <div style="flex:1;">${steps.map((p, pi) => {
            const parsed = splitPointLabel(p);
            const label = parsed.label || labels.labels[pi] || `步骤 ${pi + 1}`;
            const color = labels.colors[pi % labels.colors.length];
            return `<div style="display:grid;grid-template-columns:56px 1fr;gap:14px;padding:12px 0;border-top:1px dashed ${a}33;">
              <div style="width:48px;height:48px;border-radius:50%;background:${color};color:#fff;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:750;">${String(pi + 1).padStart(2, "0")}</div>
              <div>
                <div style="font-size:18px;font-weight:750;color:${color};letter-spacing:.06em;margin-bottom:4px;">${esc(label)}</div>
                <div style="font-size:24px;line-height:1.45;color:${inkBody};">${esc(parsed.text || p)}</div>
              </div>
            </div>`;
          }).join("")}</div>
          ${content.concept ? `<p style="${conceptStyle}margin-top:8px;padding-top:12px;border-top:1px solid ${a}29;">${esc(content.concept)}</p>` : ""}
        </section>`;
      } else if (kind === "concept") {
        bodyHtml = `<section style="flex:1;min-height:0;display:flex;flex-direction:column;gap:10px;">
          ${diagramHtml}
          ${content.concept ? `<div style="padding:14px 0;border-top:1px solid ${a}29;">
            <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px;">
              <span style="font-size:16px;letter-spacing:.18em;color:${a};font-weight:700;">01</span>
              <span style="font-size:24px;font-weight:700;color:${theme.ink};">${esc(labels.concept[0])}</span>
            </div>
            <p style="${conceptStyle}">${esc(content.concept)}</p>
          </div>` : ""}
          ${points.length ? `<div style="padding:10px 0;border-top:1px solid ${a}29;flex:1;">
            <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:8px;">
              <span style="font-size:16px;letter-spacing:.18em;color:${a};font-weight:700;">02</span>
              <span style="font-size:24px;font-weight:700;color:${theme.ink};">${esc(labels.points[0])}</span>
            </div>
            <ul style="list-style:none;padding:0;margin:0;">${points.map((p, pi) => {
              const parsed = splitPointLabel(p);
              const color = labels.colors[pi % labels.colors.length];
              return `<li style="display:grid;grid-template-columns:36px 1fr;gap:12px;padding:10px 0;border-top:1px solid ${a}18;">
                <span style="font-size:18px;font-weight:750;color:${color};">${String(pi + 1).padStart(2, "0")}</span>
                <span style="font-size:24px;line-height:1.45;color:${inkBody};">${esc(parsed.text || p)}</span>
              </li>`;
            }).join("")}</ul>
          </div>` : ""}
          ${content.example ? `<div style="padding:12px 0 0;border-top:1px solid ${a}29;">
            <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:8px;">
              <span style="font-size:16px;letter-spacing:.18em;color:${a};font-weight:700;">03</span>
              <span style="font-size:24px;font-weight:700;color:${theme.ink};">${esc(labels.example[0])}</span>
            </div>
            <div style="padding:16px 18px;border-left:4px solid ${a};background:${theme.soft};">
              <p style="${exampleStyle}">${esc(content.example)}</p>
            </div>
          </div>` : ""}
        </section>`;
      } else {
        // keypoints (default)
        const conceptBlock = content.concept
          ? `<section style="padding:12px 0;border-top:1px solid ${a}29;flex-shrink:0;">
              <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:8px;">
                <span style="font-size:16px;letter-spacing:.18em;color:${a};font-weight:700;">01</span>
                <span style="font-size:24px;font-weight:700;color:${theme.ink};">${esc(labels.concept[0])}</span>
              </div>
              <p style="${conceptStyle}">${esc(content.concept)}</p>
            </section>` : "";
        let pointsBlock = "";
        if (points.length || diagramHtml) {
          const lis = points.slice(0, 6).map((p, pi) => {
            const parsed = splitPointLabel(p);
            const label = parsed.label || labels.labels[pi] || "要点";
            const color = labels.colors[pi % labels.colors.length];
            return `<li style="display:grid;grid-template-columns:40px 72px 1fr;gap:12px;align-items:start;margin:0 0 12px;">
              <div style="padding-top:2px;">${pointIcon(label, color)}</div>
              <span style="font-size:18px;font-weight:750;letter-spacing:.06em;color:${color};padding-top:4px;">${esc(label)}</span>
              <span style="font-size:24px;line-height:1.45;color:${inkBody};min-width:0;">${esc(parsed.text || p)}</span>
            </li>`;
          }).join("");
          pointsBlock = `<section style="padding:12px 0;border-top:1px solid ${a}29;flex:1;min-height:0;">
            <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px;">
              <span style="font-size:16px;letter-spacing:.18em;color:${a};font-weight:700;">02</span>
              <span style="font-size:24px;font-weight:700;color:${theme.ink};">${esc(labels.points[0])}</span>
            </div>
            ${diagramHtml}
            <ul style="list-style:none;padding:0;margin:8px 0 0;">${lis}</ul>
          </section>`;
        }
        const exampleBlock = content.example
          ? `<section style="padding:12px 0 0;border-top:1px solid ${a}29;flex-shrink:0;">
              <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:8px;">
                <span style="font-size:16px;letter-spacing:.18em;color:${a};font-weight:700;">03</span>
                <span style="font-size:24px;font-weight:700;color:${theme.ink};">${esc(labels.example[0])}</span>
              </div>
              <div style="padding:16px 18px;border-left:4px solid ${a};background:${theme.soft};">
                <p style="${exampleStyle}">${esc(content.example)}</p>
              </div>
            </section>` : "";
        bodyHtml = conceptBlock + pointsBlock + exampleBlock;
      }

      const bg = `linear-gradient(165deg,${theme.paper} 0%,${theme.paper2} 55%,${theme.paper3} 100%)`;
      const wash = `radial-gradient(60% 45% at 92% 6%, ${theme.soft}, transparent 62%), radial-gradient(45% 35% at 6% 94%, rgba(148,163,184,0.10), transparent 70%)`;
      const previewBadge = state.isTemplatePreview
        ? `<div style="position:absolute;right:48px;top:36px;z-index:3;padding:8px 14px;background:${a};color:#fff;font-size:14px;font-weight:700;letter-spacing:.12em;">模版预览</div>`
        : "";
      const sig = clipUi((state.cover && state.cover.brand_signature) || "", 24);
      const footLeft = [
        k.seriesCn || "知识卡片",
        state.footerLabel,
        content.source,
        sig,
      ].filter(Boolean).join(" · ");

      return `<div class="kc-canvas" data-export="k${index}" style="background:${bg};overflow:hidden;">
        <div style="position:absolute;inset:0;pointer-events:none;background:${wash};"></div>
        <div style="position:absolute;left:0;top:0;bottom:0;width:8px;background:${a};"></div>
        ${previewBadge}
        <div style="position:relative;z-index:2;height:100%;display:flex;flex-direction:column;padding:64px 64px 52px;box-sizing:border-box;overflow:hidden;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:22px;flex-shrink:0;">
            <span style="font-size:18px;letter-spacing:.28em;font-weight:700;color:${a};">${esc(k.seriesEn || theme.templateLabel || "SERIES")}</span>
            <span style="width:1px;height:16px;background:rgba(100,116,139,0.45);"></span>
            <span style="font-size:20px;color:${theme.muted};">${esc(k.seriesCn || "知识卡片")}</span>
            <span style="margin-left:auto;display:flex;gap:6px;align-items:center;">
              ${k.paddedFromTheme ? `<span style="font-size:12px;letter-spacing:.08em;color:#b45309;font-weight:700;padding:5px 8px;border:1px solid #f59e0b55;background:#fffbeb;">模板补全</span>` : ""}
              <span style="font-size:14px;letter-spacing:.16em;color:${a};font-weight:700;padding:6px 10px;border:1px solid ${a}44;">${esc(kindLabel)}</span>
            </span>
          </div>
          <div style="display:grid;grid-template-columns:100px 1fr;gap:18px;align-items:end;margin-bottom:10px;flex-shrink:0;">
            <div style="font-size:88px;line-height:0.9;font-weight:300;color:${a}38;font-variant-numeric:tabular-nums;letter-spacing:-0.04em;">${page}</div>
            <div style="min-width:0;padding-bottom:4px;">
              <div style="font-size:15px;letter-spacing:.24em;margin-bottom:8px;color:${theme.muted};font-weight:600;">${esc(labels.badge)}</div>
              <h2 style="font-size:40px;line-height:1.25;font-weight:750;color:${theme.ink};margin:0;letter-spacing:-0.01em;word-break:break-word;">${esc(k.topicTitle || "")}</h2>
            </div>
          </div>
          <div style="flex:1;min-height:0;display:flex;flex-direction:column;overflow:hidden;">${bodyHtml}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;padding-top:14px;margin-top:4px;border-top:1px solid ${a}29;font-size:18px;color:${theme.muted};flex-shrink:0;">
            <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:75%;">${esc(footLeft)}</span>
            <span style="letter-spacing:.2em;font-variant-numeric:tabular-nums;">${page} / ${totalStr}</span>
          </div>
        </div>
      </div>`;
    }

    function mountScaled(html) {
      const wrap = document.createElement("div");
      wrap.className = "scaled-wrap";
      const inner = document.createElement("div");
      inner.innerHTML = html;
      const canvas = inner.firstElementChild;
      wrap.appendChild(canvas);
      const scale = () => {
        const parent = wrap.parentElement;
        if (!parent) return;
        const avail = Math.min(parent.clientWidth - 48, 1080);
        const s = Math.max(Math.min(avail / 1080, 0.92), 0.22);
        wrap.style.width = `${1080 * s}px`;
        wrap.style.height = `${1440 * s}px`;
        canvas.style.transform = `scale(${s})`;
        canvas.style.transformOrigin = "top left";
      };
      requestAnimationFrame(scale);
      if (global.ResizeObserver) new ResizeObserver(scale).observe($("kcPreviewStack"));
      return wrap;
    }

    function renderPreview() {
      const stack = $("kcPreviewStack");
      if (!stack) return;
      stack.innerHTML = "";
      if (!state.knowledge.length) {
        stack.innerHTML = `<div class="kc-empty-preview">
          <p>尚未生成卡片</p>
          <p class="meta">填写左侧主题后，点击「深采」再「成刊」，或直接「快扫」</p>
        </div>`;
        return;
      }
      const c = state.cover || defaultCover;
      const ks = state.knowledge;
      const fm = state.frontMatter;
      const theme = coverTheme(c);
      stack.appendChild(mountScaled(renderCoverHtml(c)));
      if (hasGuidePromises(fm)) {
        const guideHtml = renderGuideHtml(fm, c, theme);
        if (guideHtml) stack.appendChild(mountScaled(guideHtml));
      }
      if (hasTocEntries(fm)) {
        const tocHtml = renderTocHtml(fm, theme);
        if (tocHtml) stack.appendChild(mountScaled(tocHtml));
      }
      ks.forEach((k, i) => stack.appendChild(mountScaled(renderKnowHtml(k, i, ks.length))));
    }

    function renderTabs() {
      const box = $("kcEditTabs");
      if (!box) return;
      const ks = state.knowledge;
      const fm = state.frontMatter;
      const hasGuide = hasGuidePromises(fm);
      const hasToc = hasTocEntries(fm);
      let page = 1;
      const parts = [
        `<button type="button" data-tab="cover" class="${state.activeTab === "cover" ? "active" : ""}">${String(page).padStart(2, "0")} 封面</button>`,
      ];
      page += 1;
      if (hasGuide) {
        parts.push(`<button type="button" data-tab="guide" class="${state.activeTab === "guide" ? "active" : ""}">${String(page).padStart(2, "0")} 导读</button>`);
        page += 1;
      }
      if (hasToc) {
        parts.push(`<button type="button" data-tab="toc" class="${state.activeTab === "toc" ? "active" : ""}">${String(page).padStart(2, "0")} 目录</button>`);
        page += 1;
      }
      ks.forEach((k, i) => {
        const label = String((k && k.topicTitle) || `卡片 ${i + 1}`).trim() || `卡片 ${i + 1}`;
        const n = String(page + i).padStart(2, "0");
        parts.push(`<button type="button" data-tab="${i}" class="${state.activeTab === i ? "active" : ""}" title="${esc(label)}">${n} ${esc(label)}</button>`);
      });
      box.innerHTML = parts.join("");
      box.querySelectorAll("button").forEach((b) => {
        b.onclick = () => {
          const t = b.dataset.tab;
          state.activeTab = (t === "cover" || t === "guide" || t === "toc") ? t : Number(t);
          renderEditor();
          renderTabs();
        };
      });
    }

    function field(label, value, onInput, rows) {
      const id = "kcf_" + Math.random().toString(36).slice(2, 8);
      setTimeout(() => {
        const el = document.getElementById(id);
        if (el) el.oninput = () => onInput(el.value);
      }, 0);
      if (rows) {
        return `<label>${esc(label)}</label><textarea id="${id}" class="field" rows="${rows}">${esc(value)}</textarea>`;
      }
      return `<label>${esc(label)}</label><input id="${id}" class="field" value="${esc(value)}" />`;
    }

    function selectField(label, value, options, onChange) {
      const id = "kcf_" + Math.random().toString(36).slice(2, 8);
      setTimeout(() => {
        const el = document.getElementById(id);
        if (el) el.onchange = () => onChange(el.value);
      }, 0);
      const opts = options.map((o) =>
        `<option value="${esc(o.id)}"${o.id === value ? " selected" : ""}>${esc(o.label)}</option>`
      ).join("");
      return `<label>${esc(label)}</label><select id="${id}" class="field">${opts}</select>`;
    }

    function syncTocFromKnowledge() {
      if (!state.frontMatter || typeof state.frontMatter !== "object") {
        state.frontMatter = { guide: { promises: [] }, toc: [] };
      }
      const ks = state.knowledge || [];
      const prev = Array.isArray(state.frontMatter.toc) ? state.frontMatter.toc : [];
      state.frontMatter.toc = ks.map((card, i) => {
        const row = prev[i] && typeof prev[i] === "object" ? prev[i] : {};
        const dtype = card && card.diagram && card.diagram.type;
        return {
          index: i + 1,
          title: String((card && card.topicTitle) || row.title || `卡片${i + 1}`),
          kind: String((card && card.card_kind) || row.kind || "concept"),
          diagram: String(dtype || row.diagram || "bullets"),
        };
      });
    }

    function ensureCardDiagram(k) {
      if (!k.diagram || typeof k.diagram !== "object") {
        k.diagram = { type: "bullets", nodes: [] };
      }
      if (!Array.isArray(k.diagram.nodes)) k.diagram.nodes = [];
      return k.diagram;
    }

    function setDiagramNodeLabel(k, nodeIdx, label) {
      const d = ensureCardDiagram(k);
      while (d.nodes.length <= nodeIdx) d.nodes.push({ label: "", note: "" });
      const cur = d.nodes[nodeIdx];
      if (cur && typeof cur === "object") {
        cur.label = label;
      } else {
        d.nodes[nodeIdx] = { label, note: "" };
      }
    }

    function renderGuideEditorHtml() {
      const fm = state.frontMatter;
      const guide = fm && fm.guide;
      if (!guide || typeof guide !== "object") return "";
      const promises = Array.isArray(guide.promises) ? guide.promises.slice(0, 3) : [];
      while (promises.length < 3) promises.push("");
      const setPromise = (i, v) => {
        if (!state.frontMatter) state.frontMatter = { guide: { promises: ["", "", ""] } };
        if (!state.frontMatter.guide || typeof state.frontMatter.guide !== "object") {
          state.frontMatter.guide = { promises: ["", "", ""] };
        }
        const g = state.frontMatter.guide;
        if (!Array.isArray(g.promises)) g.promises = ["", "", ""];
        while (g.promises.length < 3) g.promises.push("");
        g.promises[i] = v;
        renderPreview();
      };
      return (
        `<div class="kc-fm-block"><div class="meta" style="margin:14px 0 6px;font-weight:650;">导读 · 读者承诺</div>` +
        field("导读标题", guide.headline || "本期导读", (v) => {
          if (!state.frontMatter) state.frontMatter = { guide: {} };
          if (!state.frontMatter.guide) state.frontMatter.guide = {};
          state.frontMatter.guide.headline = v;
          renderPreview();
        }) +
        field("承诺 1（≤28 字）", promises[0] || "", (v) => setPromise(0, v)) +
        field("承诺 2（≤28 字）", promises[1] || "", (v) => setPromise(1, v)) +
        field("承诺 3（≤28 字）", promises[2] || "", (v) => setPromise(2, v)) +
        field("导读附注 meta", guide.meta || "", (v) => {
          if (!state.frontMatter) state.frontMatter = { guide: {} };
          if (!state.frontMatter.guide) state.frontMatter.guide = {};
          state.frontMatter.guide.meta = v;
          renderPreview();
        }, 2) +
        `</div>`
      );
    }

    function renderDiagramEditorHtml(k) {
      const d = ensureCardDiagram(k);
      const type = String(d.type || "bullets").toLowerCase();
      const known = DIAGRAM_TYPES.some((t) => t.id === type) ? type : "bullets";
      const nodes = Array.isArray(d.nodes) ? d.nodes : [];
      const labels = [0, 1, 2, 3].map((i) => {
        const n = nodes[i];
        if (n && typeof n === "object") return String(n.label || "");
        if (typeof n === "string") return n;
        return "";
      });
      return (
        `<div class="kc-diagram-block"><div class="meta" style="margin:14px 0 6px;font-weight:650;">图示 diagram</div>` +
        selectField("图示类型", known, DIAGRAM_TYPES, (v) => {
          ensureCardDiagram(k).type = v;
          syncTocFromKnowledge();
          renderPreview();
        }) +
        [0, 1, 2, 3].map((i) =>
          field(`节点 ${i + 1} 标签`, labels[i], (v) => {
            setDiagramNodeLabel(k, i, v);
            renderPreview();
          })
        ).join("") +
        `</div>`
      );
    }

    function renderEditor() {
      const c = state.cover || defaultCover;
      const coverBox = $("kcEditorCover");
      const knowBox = $("kcEditorKnow");
      if (!coverBox || !knowBox) return;
      if (state.activeTab === "cover") {
        coverBox.hidden = false;
        knowBox.hidden = true;
        const styleVal = c.visual_style || CAT_DEFAULT_STYLE[state.category] || "academic";
        coverBox.innerHTML =
          selectField("视觉风格", styleVal, Object.values(VISUAL_STYLES).map((s) => ({ id: s.id, label: s.label })), (v) => {
            c.visual_style = v; state.cover = c; state.visual_style = v; renderPreview();
          }) +
          field("系列英文名", c.seriesEn, (v) => { c.seriesEn = v; state.cover = c; renderPreview(); }) +
          field("系列中文名", c.seriesCn, (v) => { c.seriesCn = v; state.cover = c; renderPreview(); }) +
          field("主标题", c.title, (v) => { c.title = v; state.cover = c; renderPreview(); }) +
          field("期数（如 12 或 第 12 期）", c.edition || "", (v) => { c.edition = v; state.cover = c; renderPreview(); }) +
          field("导语", c.description, (v) => { c.description = v; state.cover = c; renderPreview(); }, 3) +
          field("标签（· 或 , 分隔，最多 5 个 · 决定 Hook 与装饰主题）", (c.tags || []).join(" · "), (v) => {
            c.tags = v.split(/[·,，]/).map((s) => s.trim()).filter(Boolean).slice(0, 5);
            state.cover = c; renderPreview();
          }) +
          field("出处 / 来源", c.source || "", (v) => { c.source = v; state.cover = c; renderPreview(); }) +
          field("品牌签名", c.brand_signature || "", (v) => { c.brand_signature = v; state.cover = c; renderPreview(); }) +
          `<label>右侧装饰图</label><input type="file" accept="image/*" id="kcDecorFile" class="field" />` +
          (c.imageUrl ? `<button type="button" class="ghost" id="kcClearDecor" style="margin-top:8px;">移除图片</button>` : "");
        const file = $("kcDecorFile");
        if (file) file.onchange = () => {
          const f = file.files && file.files[0];
          if (!f) return;
          const r = new FileReader();
          r.onload = () => { c.imageUrl = r.result; state.cover = c; renderPreview(); renderEditor(); };
          r.readAsDataURL(f);
        };
        const clr = $("kcClearDecor");
        if (clr) clr.onclick = () => { c.imageUrl = ""; state.cover = c; renderPreview(); renderEditor(); };
        return;
      }
      if (state.activeTab === "guide") {
        coverBox.hidden = false;
        knowBox.hidden = true;
        coverBox.innerHTML = renderGuideEditorHtml() || `<p class="meta">本期无导读。重新成刊后会生成。</p>`;
        return;
      }
      if (state.activeTab === "toc") {
        coverBox.hidden = false;
        knowBox.hidden = true;
        const toc = (state.frontMatter && Array.isArray(state.frontMatter.toc)) ? state.frontMatter.toc : [];
        const ks = state.knowledge || [];
        if (!toc.length) {
          coverBox.innerHTML = `<p class="meta">本期无目录。重新成刊后会生成。</p>`;
          return;
        }
        coverBox.innerHTML = `<div class="meta" style="margin-bottom:8px;font-weight:650;">目录（改标题会同步到对应知识卡）</div>` +
          toc.map((row, i) => field(
            `第 ${row.index || i + 1} 条 · ${(row.kind || "")}`,
            row.title || (ks[i] && ks[i].topicTitle) || "",
            (v) => {
              row.title = v;
              if (ks[i]) ks[i].topicTitle = v;
              renderPreview();
            }
          )).join("");
        return;
      }
      coverBox.hidden = true;
      knowBox.hidden = false;
      const idx = Number(state.activeTab);
      const k = state.knowledge[idx];
      if (!k) return;
      const kind = k.card_kind || "keypoints";
      knowBox.innerHTML =
        selectField("卡片类型", kind, CARD_KINDS, (v) => {
          k.card_kind = v;
          syncTocFromKnowledge();
          renderPreview();
          renderEditor();
        }) +
        field("知识点标题", k.topicTitle, (v) => {
          k.topicTitle = v;
          syncTocFromKnowledge();
          renderPreview();
        }) +
        field("概念（是什么 / 为何重要 / 常见误解）", k.concept, (v) => { k.concept = v; renderPreview(); }, 4) +
        field("掌握要点（每行一条）", k.keyPoint, (v) => { k.keyPoint = v; k.realPoints = []; renderPreview(); }, 5) +
        field("落地案例", k.example || "", (v) => { k.example = v; renderPreview(); }, 3) +
        (kind === "quote" ? field("金句", k.quote || "", (v) => { k.quote = v; renderPreview(); }, 2) : "") +
        (kind === "compare"
          ? field("对比 · 误区侧", k.compare_left || "", (v) => { k.compare_left = v; renderPreview(); }, 2)
            + field("对比 · 正解侧", k.compare_right || "", (v) => { k.compare_right = v; renderPreview(); }, 2)
          : "") +
        (kind === "data"
          ? field("数据短值", k.metric || "", (v) => { k.metric = v; renderPreview(); })
            + field("数据说明", k.metric_note || "", (v) => { k.metric_note = v; renderPreview(); }, 2)
          : "") +
        renderDiagramEditorHtml(k) +
        field("出处", k.source || "", (v) => { k.source = v; renderPreview(); }) +
        renderEvidenceChips(k) +
        `<div class="actions" style="display:flex;gap:8px;margin-top:10px;">
          <button type="button" class="ghost" id="kcAddCard">+ 添加卡片</button>
          ${state.knowledge.length > 2 ? `<button type="button" class="ghost" id="kcDelCard">删除当前</button>` : ""}
        </div>`;
      bindEvidenceChips(knowBox);
      $("kcAddCard").onclick = () => {
        if (state.knowledge.length >= 8) return;
        state.knowledge.push({
          ...defaultKnowledge[0],
          topicTitle: `新知识点 ${state.knowledge.length + 1}`,
          realPoints: [],
          card_kind: "keypoints",
          diagram: { type: "bullets", nodes: [] },
        });
        state.activeTab = state.knowledge.length - 1;
        syncTocFromKnowledge();
        renderTabs(); renderEditor(); renderPreview();
      };
      const del = $("kcDelCard");
      if (del) del.onclick = () => {
        state.knowledge.splice(idx, 1);
        syncTocFromKnowledge();
        state.activeTab = Math.max(0, idx - 1);
        renderTabs(); renderEditor(); renderPreview();
      };
    }

    function historyModeBadge(mode) {
      const m = String(mode || "").toLowerCase();
      if (m === "research") return { label: "深采", color: "#0f766e" };
      if (m === "journal" || m === "ai") return { label: "成刊", color: "#7c3aed" };
      if (m === "live") return { label: "快扫", color: "#0369a1" };
      if (m === "cached") return { label: "降级", color: "#b45309" };
      return { label: "草稿", color: "#78716c" };
    }

    async function refreshHistory() {
      const list = await api("/api/cards/history");
      const box = $("kcHistList");
      const countEl = $("kcHistCount");
      if (countEl) countEl.textContent = list.length ? `${list.length} 条` : "";
      if (!box) return;
      if (!list.length) {
        box.innerHTML = `<p class="meta">暂无记录，先深采或快扫生成第一版。</p>`;
        suggestNextEdition(0);
        return;
      }
      suggestNextEdition(list.length);
      box.innerHTML = list.map((h) => {
        const badge = historyModeBadge(h.mode);
        const modeColor = badge.color;
        const catLabel = (state.categories.find((c) => c.id === h.category) || {}).short
          || (state.categories.find((c) => c.id === h.category) || {}).label
          || "";
        const pubs = Array.isArray(h.publish) ? h.publish : [];
        const pubPills = pubs.map((p) => {
          const plat = p.platform === "weixin" ? "微信"
            : p.platform === "toutiao" ? "头条"
            : p.platform === "xiaohongshu" ? "小红书"
            : p.platform === "douyin" ? "抖音"
            : (p.platform || "");
          const st = p.status === "draft" ? "草稿" : p.status === "published" ? "已发" : p.status === "skipped" ? "跳过" : (p.status || "");
          return `<span class="pill" style="color:#0f766e;background:#ecfdf5;">${esc(plat + st)}</span>`;
        }).join("");
        return `<div class="hist-item ${state.activeHistoryId === h.id ? "active" : ""}" data-id="${esc(h.id)}">
          <button type="button" class="hist-del row-del" data-del="${esc(h.id)}" title="删除">×</button>
          <div class="t" style="display:flex;justify-content:space-between;padding-right:22px;gap:6px;">
            <span>${esc(h.dateLabel || h.title || "")}</span>
            <span style="display:flex;gap:4px;flex-shrink:0;flex-wrap:wrap;justify-content:flex-end;">
              ${catLabel ? `<span class="pill" style="color:#57534e;background:#f5f5f4;">${esc(catLabel)}</span>` : ""}
              <span class="pill" style="color:${modeColor};background:color-mix(in srgb, ${modeColor} 12%, white);">${esc(badge.label)}</span>
              ${pubPills}
            </span>
          </div>
          <div class="s">${esc((h.topics || []).join(" · "))}</div>
        </div>`;
      }).join("");
      box.querySelectorAll(".hist-item").forEach((row) => {
        row.onclick = (e) => {
          if (e.target && e.target.closest && e.target.closest("[data-del]")) return;
          loadHistory(row.dataset.id);
        };
      });
      box.querySelectorAll("[data-del]").forEach((btn) => {
        btn.onclick = (e) => {
          e.stopPropagation();
          deleteHistory(btn.getAttribute("data-del"));
        };
      });
    }

    async function deleteHistory(id) {
      if (!id) return;
      if (!confirm("删除这条历史记录？")) return;
      try {
        await api(`/api/cards/history/${encodeURIComponent(id)}`, { method: "DELETE" });
        if (state.activeHistoryId === id) state.activeHistoryId = "";
        $("kcScanNote").textContent = "已删除历史记录";
        $("kcScanNote").className = "status ok";
        await refreshHistory();
      } catch (e) {
        $("kcScanNote").textContent = "删除失败：" + (e.message || e);
        $("kcScanNote").className = "status err";
      }
    }

    async function loadHistory(id) {
      const rec = await api(`/api/cards/history?id=${encodeURIComponent(id)}`);
      if (rec.category) state.category = rec.category;
      applyCategoryUI();
      applyPayload(rec, { note: `已载入历史（${(rec.cover && rec.cover.gradientPart) || ""}）` });
      state.activeHistoryId = id;
      await refreshHistory();
    }

    function parseRolesInput(rolesOverride) {
      const roles = rolesOverride
        || ($("kcRolesInput") ? $("kcRolesInput").value.split(/[、,，]/).map((s) => s.trim()).filter(Boolean) : []);
      if (rolesOverride && $("kcRolesInput")) {
        $("kcRolesInput").value = roles.join("、");
      }
      return roles;
    }

    function editionInputValue() {
      return ($("kcEditionInput") && String($("kcEditionInput").value || "").trim()) || "";
    }

    function selectedEvidenceCount() {
      return (state.evidencePack.evidences || []).filter((e) => e && e.selected !== false).length;
    }

    function syncEvidenceSelectionFromDom() {
      const list = $("kcEvidenceList");
      if (!list) return;
      list.querySelectorAll("input[data-eid]").forEach((cb) => {
        const eid = cb.getAttribute("data-eid");
        const row = (state.evidencePack.evidences || []).find((e) => e && String(e.id) === String(eid));
        if (row) row.selected = !!cb.checked;
      });
      state.evidencePack.count = (state.evidencePack.evidences || []).length;
    }

    function renderEvidenceList() {
      const list = $("kcEvidenceList");
      const countEl = $("kcEvidenceCount");
      const composeBtn = $("kcComposeBtn");
      const panel = $("kcEvidencePanel");
      const evidences = (state.evidencePack && state.evidencePack.evidences) || [];
      const n = evidences.filter((e) => e && e.selected !== false).length;
      if (countEl) countEl.textContent = String(n);
      if (composeBtn && !state.composing) composeBtn.disabled = n < 5;
      if (panel && evidences.length) panel.open = true;
      if (!list) return;
      if (!evidences.length) {
        list.innerHTML = `<p class="meta" style="margin:0;">暂无素材，先点「深采」或「快扫」。</p>`;
        return;
      }
      list.innerHTML = evidences.map((e) => {
        const id = esc(e.id || "");
        const score = esc(e.score != null ? e.score : "");
        const title = String(e.title || "").trim();
        const url = String(e.url || "").trim();
        const text = esc(String(e.text || "").slice(0, 100));
        const checked = e.selected === false ? "" : "checked";
        const titleHtml = title
          ? `<span class="kc-ev-title">${esc(title.slice(0, 40))}</span>`
          : "";
        const linkHtml = url
          ? `<a class="kc-ev-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">原文</a>`
          : "";
        return `<label class="kc-ev-row">
          <input type="checkbox" data-eid="${id}" ${checked} />
          <span class="kc-ev-score">${score}</span>
          <span class="kc-ev-text">${titleHtml}${text}${linkHtml}</span>
        </label>`;
      }).join("");
      list.querySelectorAll("input[data-eid]").forEach((cb) => {
        cb.onchange = () => {
          const eid = cb.getAttribute("data-eid");
          const row = (state.evidencePack.evidences || []).find((e) => e && String(e.id) === String(eid));
          if (row) row.selected = !!cb.checked;
          const sel = selectedEvidenceCount();
          if (countEl) countEl.textContent = String(sel);
          if (composeBtn && !state.composing) composeBtn.disabled = sel < 5;
        };
      });
    }

    function evidenceById(eid) {
      return ((state.evidencePack && state.evidencePack.evidences) || [])
        .find((e) => e && String(e.id) === String(eid)) || null;
    }

    function evidenceTextById(eid) {
      const row = evidenceById(eid);
      return row ? String(row.text || "") : "";
    }

    function renderEvidenceChips(k) {
      const ids = Array.isArray(k.evidenceIds) ? k.evidenceIds : [];
      if (!ids.length) return "";
      const chips = ids.map((id) =>
        `<button type="button" class="kc-ev-chip" data-eid="${esc(id)}" title="查看证据">${esc(id)}</button>`
      ).join("");
      return `<label style="margin-top:8px;">引用证据</label><div class="kc-ev-chips">${chips}</div>`;
    }

    function bindEvidenceChips(root) {
      if (!root) return;
      root.querySelectorAll(".kc-ev-chip[data-eid]").forEach((btn) => {
        btn.onclick = () => {
          const eid = btn.getAttribute("data-eid");
          const row = evidenceById(eid);
          if (!row) {
            window.alert(`未找到证据 ${eid}（可先深采或载入带素材的历史）`);
            return;
          }
          const title = String(row.title || "").trim();
          const url = String(row.url || "").trim();
          const text = String(row.text || "");
          const lines = [eid];
          if (title) lines.push(title);
          if (url) lines.push(url);
          if (text) lines.push("", text);
          window.alert(lines.join("\n"));
        };
      });
    }

    function showSources() {
      const box = $("kcSourcesBox");
      const list = $("kcSourcesList");
      if (!box || !list) return;
      if (!state.sources.length) { box.hidden = true; return; }
      box.hidden = false;
      list.innerHTML = state.sources.map((s) => `<p>${esc(s)}</p>`).join("");
    }

    function editionFromCover(cover) {
      const ed = String((cover && cover.edition) || "").trim();
      const m = ed.match(/(\d+)/);
      return m ? m[1] : "";
    }

    function syncEditionInput(fromCover) {
      const el = $("kcEditionInput");
      if (!el) return;
      if (fromCover) {
        const n = editionFromCover(fromCover);
        if (n) el.value = n;
      }
    }

    function suggestNextEdition(historyLen) {
      const el = $("kcEditionInput");
      if (!el || el.value) return;
      el.placeholder = String(Math.max(1, Number(historyLen || 0) + 1));
    }

    function applyPayload(data, { note } = {}) {
      state.isTemplatePreview = false;
      state.qualityWarning = degradedComposeMessage(data);
      state.qualityGatePass = data.quality_gate_pass !== false && !state.qualityWarning;
      if (data.depth && data.depth.ok === false) state.qualityGatePass = false;
      state.cover = data.cover || state.cover;
      state.knowledge = (data.knowledge || []).map((k) => enrichCardDiagram({ ...k }));
      let fm = (data.frontMatter && typeof data.frontMatter === "object" && !Array.isArray(data.frontMatter))
        ? data.frontMatter
        : null;
      fm = enrichFrontMatter(fm, state.knowledge, state.cover);
      state.frontMatter = fm;
      state.sources = data.sources || [];
      const pack = data.evidencePack;
      const packEvidences = pack && typeof pack === "object" && Array.isArray(pack.evidences)
        ? pack.evidences
        : null;
      if (packEvidences && packEvidences.length) {
        state.evidencePack = {
          evidences: packEvidences,
          count: Number(pack.count || packEvidences.length || 0),
        };
        state.packId = data.packId || data.id || state.packId || "";
      } else {
        state.evidencePack = { evidences: [], count: 0 };
        state.packId = data.id || "";
      }
      state.lastDepth = data.depth || null;
      renderQualityPanelFromState(data);
      if (data.roles != null && $("kcRolesInput")) {
        $("kcRolesInput").value = Array.isArray(data.roles)
          ? data.roles.join("、")
          : String(data.roles || "");
      }
      state.visual_style = (data.visual_style
        || (state.cover && state.cover.visual_style)
        || CAT_DEFAULT_STYLE[state.category]
        || "academic");
      if (state.cover && !state.cover.visual_style) {
        state.cover.visual_style = state.visual_style;
      }
      if (data.id) state.activeHistoryId = data.id;
      state.activeTab = "cover";
      if (note) {
        $("kcScanNote").textContent = state.qualityWarning || note;
        $("kcScanNote").className = state.qualityWarning ? "status err" : "status ok";
      }
      applyCategoryUI();
      syncEditionInput(state.cover);
      showSources();
      renderEvidenceList();
      renderTabs(); renderEditor(); renderPreview();
      syncPublishBtn();
    }

    function syncPublishBtn() {
      const btn = $("kcPublishBtn");
      if (!btn) return;
      btn.disabled = !state.activeHistoryId || state.publishing;
    }

    function resolveTitleFromCover(cover) {
      const c = cover || {};
      const tags = Array.isArray(c.tags) ? c.tags.map((t) => String(t).trim()).filter(Boolean) : [];
      if (tags.length) return tags.join(" · ");
      return String(c.title || "").trim() || "知识卡片";
    }

    function openPlatformSettings(platform) {
      const dlg = $("globalPlatDlg");
      if (!dlg) return;
      loadPlatConfig(platform || "weixin").catch(() => {});
      refreshAuthStatus().catch(() => {});
      if (typeof dlg.showModal === "function") dlg.showModal();
      else dlg.setAttribute("open", "open");
    }

    function closePlatformSettings() {
      const dlg = $("globalPlatDlg");
      if (!dlg) return;
      if (typeof dlg.close === "function") dlg.close();
      else dlg.removeAttribute("open");
    }

    function updateGlobalPlatBtn(wx, tt, xhs) {
      const btn = $("globalPlatBtn");
      if (!btn) return;
      const wxOk = !!(wx && (wx.authorized || wx.ready || wx.configured));
      const ttOk = !!(tt && (tt.authorized || tt.ready || tt.configured));
      const xhsOk = !!(xhs && (xhs.authorized || xhs.ready || xhs.half_auto));
      const anyReady = wxOk || ttOk || xhsOk;
      const anyConfigured = !!(
        (wx && (wx.configured || wx.ready || wx.authorized))
        || (tt && (tt.configured || tt.ready || tt.authorized))
        || xhsOk
      );
      btn.classList.toggle("ok", anyReady);
      btn.classList.toggle("warn", !anyConfigured);
      const parts = [];
      if (wx) parts.push(wx.authorized ? "微信已就绪" : (wx.ready || wx.configured ? "微信已配置" : "微信未配"));
      if (tt) parts.push(tt.authorized ? "头条已就绪" : (tt.ready || tt.configured ? "头条已配置" : "头条未配"));
      parts.push(xhsOk ? "小红书半自动" : "小红书");
      btn.title = parts.join(" · ") || "发布平台凭证";
    }

    async function refreshAuthStatus() {
      const setLabel = (elId, st) => {
        const el = $(elId);
        if (!el) return;
        if (!st) { el.textContent = ""; return; }
        if (st.half_auto) el.textContent = st.account ? `半自动 · ${st.account}` : "半自动就绪";
        else if (st.authorized) el.textContent = st.account ? `已就绪 · ${st.account}` : "已就绪";
        else if (st.ready) el.textContent = "已配置 · 待确认";
        else el.textContent = st.message || "未配置";
      };
      let wx = null;
      let tt = null;
      try {
        let dy = null;
        let xhs = null;
        [wx, tt, dy, xhs] = await Promise.all([
          api("/api/oauth/weixin/status"),
          api("/api/oauth/toutiao/status"),
          api("/api/oauth/douyin/status").catch(() => null),
          api("/api/oauth/xiaohongshu/status").catch(() => null),
        ]);
        setLabel("kcAuthWx", wx);
        setLabel("kcAuthTt", tt);
        setLabel("kcAuthXhs", xhs || { half_auto: true, account: "半自动" });
        updateGlobalPlatBtn(wx, tt, xhs);
        const live = $("platLiveStatus");
        if (live) {
          const p = ($("kcCfgPlatform") && $("kcCfgPlatform").value) || "weixin";
          const st = p === "toutiao" ? tt : (p === "douyin" ? dy : (p === "xiaohongshu" ? xhs : wx));
          if (!st) live.innerHTML = '<span class="warn">状态未知</span>';
          else if (st.half_auto) live.innerHTML = `<span class="ok">半自动就绪${st.account ? " · " + escapeHtmlSafe(st.account) : ""}</span>`;
          else if (st.authorized) live.innerHTML = `<span class="ok">账号已就绪${st.account ? " · " + escapeHtmlSafe(st.account) : ""}</span>`;
          else if (st.ready) live.innerHTML = '<span class="ok">凭证已配置，点右侧确认账号</span>';
          else live.innerHTML = `<span class="warn">${escapeHtmlSafe(st.message || "尚未配置凭证")}</span>`;
        }
        const sec = (wx && wx.secrets) || (tt && tt.secrets);
        ["kcSecretsHint", "kcSecretsHintGlobal"].forEach((id) => {
          const hint = $(id);
          if (hint && sec) {
            hint.textContent = sec.message || "";
            hint.style.color = sec.insforge_ok === false ? "#b45309" : "";
          }
        });
      } catch {
        setLabel("kcAuthWx", null);
        setLabel("kcAuthTt", null);
        setLabel("kcAuthXhs", { half_auto: true });
        updateGlobalPlatBtn(null, null, { half_auto: true });
      }
    }

    function escapeHtmlSafe(s) {
      return String(s || "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
      }[c]));
    }

    async function loadPlatConfig(platform) {
      const p = platform || ($("kcCfgPlatform") && $("kcCfgPlatform").value) || "weixin";
      if ($("kcCfgPlatform")) $("kcCfgPlatform").value = p;
      const authorWrap = $("kcCfgAuthorWrap");
      if (authorWrap) authorWrap.style.display = p === "weixin" ? "block" : "none";
      if ($("kcCfgTabWx")) $("kcCfgTabWx").classList.toggle("active", p === "weixin");
      if ($("kcCfgTabTt")) $("kcCfgTabTt").classList.toggle("active", p === "toutiao");
      if ($("kcCfgTabDy")) $("kcCfgTabDy").classList.toggle("active", p === "douyin");
      if ($("kcCfgTabXhs")) $("kcCfgTabXhs").classList.toggle("active", p === "xiaohongshu");
      const half = p === "xiaohongshu";
      if ($("kcCfgCredFields")) $("kcCfgCredFields").hidden = half;
      if ($("kcCfgHalfAutoHint")) $("kcCfgHalfAutoHint").hidden = !half;
      if ($("kcCfgSaveBtn")) $("kcCfgSaveBtn").style.display = half ? "none" : "";
      if ($("kcCfgAuthBtn")) $("kcCfgAuthBtn").style.display = half ? "none" : "";
      try {
        const cfg = await api(`/api/oauth/${p}/config`);
        if (half) {
          if ($("kcCfgXhsCreator")) {
            $("kcCfgXhsCreator").textContent = cfg.creator_url || "https://creator.xiaohongshu.com/publish/publish";
          }
          if ($("kcCfgStatus")) {
            $("kcCfgStatus").textContent = cfg.message || "半自动就绪";
            $("kcCfgStatus").className = "status ok";
          }
          await refreshAuthStatus();
          return;
        }
        if ($("kcCfgAppId")) $("kcCfgAppId").value = cfg.app_id || "";
        if ($("kcCfgAppSecret")) {
          $("kcCfgAppSecret").value = "";
          $("kcCfgAppSecret").placeholder = cfg.has_secret
            ? `已保存 ${cfg.app_secret_masked || "••••"}，留空不改`
            : "粘贴 AppSecret";
        }
        if ($("kcCfgAuthor")) $("kcCfgAuthor").value = cfg.author || "";
        if ($("kcCfgStatus")) {
          $("kcCfgStatus").textContent = cfg.configured ? "已有凭证，可点「确认账号」" : "尚未配置";
          $("kcCfgStatus").className = "status" + (cfg.configured ? " ok" : "");
        }
        ["kcSecretsHint", "kcSecretsHintGlobal"].forEach((id) => {
          const hint = $(id);
          if (hint && cfg.secrets) {
            hint.textContent = cfg.secrets.message || "";
            hint.style.color = cfg.secrets.insforge_ok === false ? "#b45309" : "";
          }
        });
        await refreshAuthStatus();
      } catch (e) {
        if ($("kcCfgStatus")) {
          $("kcCfgStatus").textContent = "读取配置失败：" + (e.message || e);
          $("kcCfgStatus").className = "status err";
        }
      }
    }

    async function savePlatConfig() {
      const p = ($("kcCfgPlatform") && $("kcCfgPlatform").value) || "weixin";
      const body = {
        app_id: ($("kcCfgAppId") && $("kcCfgAppId").value || "").trim(),
        app_secret: ($("kcCfgAppSecret") && $("kcCfgAppSecret").value || "").trim(),
        author: ($("kcCfgAuthor") && $("kcCfgAuthor").value || "").trim(),
      };
      if ($("kcCfgStatus")) {
        $("kcCfgStatus").textContent = "保存中…";
        $("kcCfgStatus").className = "status";
      }
      try {
        const out = await api(`/api/oauth/${p}/config`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        if ($("kcCfgStatus")) {
          $("kcCfgStatus").textContent = out.message || "已保存";
          $("kcCfgStatus").className = "status ok";
        }
        if ($("kcCfgAppSecret")) $("kcCfgAppSecret").value = "";
        await loadPlatConfig(p);
      } catch (e) {
        if ($("kcCfgStatus")) {
          $("kcCfgStatus").textContent = "保存失败：" + (e.message || e);
          $("kcCfgStatus").className = "status err";
        }
      }
    }

    async function openAuth(platform) {
      const statusEl = $("kcPublishStatus") || $("kcCfgStatus");
      if (statusEl) {
        statusEl.textContent = "确认中…";
        statusEl.className = "status";
      }
      try {
        const data = await api(`/api/oauth/${platform}/authorize`);
        if (data.needs_config) {
          if (statusEl) {
            statusEl.textContent = data.message || "请先填写并保存凭证";
            statusEl.className = "status err";
          }
          openPlatformSettings(platform);
          return;
        }
        if (data.inline || data.ok) {
          if (statusEl) {
            statusEl.textContent = data.message || "已确认";
            statusEl.className = data.ok === false ? "status err" : "status ok";
          }
          await refreshAuthStatus();
          return;
        }
        if (data.auth_url) {
          const w = window.open(data.auth_url, "_blank", "noopener,width=520,height=640");
          if (!w && statusEl) {
            statusEl.textContent = "弹窗被拦截，请允许后重试";
            statusEl.className = "status err";
          }
          setTimeout(() => refreshAuthStatus().catch(() => {}), 1200);
        }
      } catch (e) {
        const msg = e.message || String(e);
        if (statusEl) {
          statusEl.textContent = msg;
          statusEl.className = "status err";
        }
        if (/配置|AppID|AppSecret|needs_config/i.test(msg)) {
          openPlatformSettings(platform);
        }
      }
    }

    async function exportPngBlobs() {
      if (!global.htmlToImage) throw new Error("导出库未加载，请检查网络后刷新");
      if (state.isTemplatePreview) throw new Error("当前是模版预览，请先深采成刊或快扫");
      if (!state.knowledge.length) throw new Error("请先深采成刊或快扫生成卡片");
      const host = document.createElement("div");
      host.style.cssText = "position:fixed;left:-10000px;top:0;width:1080px;";
      document.body.appendChild(host);
      const c = state.cover || defaultCover;
      const ks = state.knowledge;
      const fm = state.frontMatter;
      const theme = coverTheme(c);
      const parts = [renderCoverHtml(c)];
      const names = ["cover.png"];
      if (hasGuidePromises(fm)) {
        const guideHtml = renderGuideHtml(fm, c, theme);
        if (guideHtml) {
          parts.push(guideHtml);
          names.push("guide.png");
        }
      }
      if (hasTocEntries(fm)) {
        const tocHtml = renderTocHtml(fm, theme);
        if (tocHtml) {
          parts.push(tocHtml);
          names.push("toc.png");
        }
      }
      ks.forEach((k, i) => {
        parts.push(renderKnowHtml(k, i, ks.length));
        names.push(`knowledge_${i + 1}.png`);
      });
      host.innerHTML = parts.join("");
      const nodes = [...host.querySelectorAll(".kc-canvas")];
      // Wait for QR / cover images so html-to-image does not export blank squares
      await Promise.all(
        [...host.querySelectorAll("img")].map(
          (img) =>
            img.complete
              ? Promise.resolve()
              : new Promise((resolve) => {
                  img.onload = resolve;
                  img.onerror = resolve;
                })
        )
      );
      const blobs = [];
      try {
        for (let i = 0; i < nodes.length; i++) {
          const dataUrl = await global.htmlToImage.toPng(nodes[i], {
            cacheBust: true, pixelRatio: 2, backgroundColor: "#fbfaf7", width: 1080, height: 1440,
          });
          const res = await fetch(dataUrl);
          const blob = await res.blob();
          blobs.push({ name: names[i], blob });
        }
      } finally {
        host.remove();
      }
      return blobs;
    }

    async function uploadExportImages() {
      if (!state.activeHistoryId) throw new Error("请先扫描生成并保存历史");
      const blobs = await exportPngBlobs();
      const fd = new FormData();
      fd.append("history_id", state.activeHistoryId);
      blobs.forEach((b) => fd.append("files", b.blob, b.name));
      const token = (opts.getToken && opts.getToken()) || "";
      const res = await fetch("/api/cards/export-images", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || res.statusText || "上传失败");
      return data;
    }

    async function openPublishDialog() {
      if (!state.activeHistoryId) {
        $("kcScanNote").textContent = "请先扫描生成后再发布";
        $("kcScanNote").className = "status err";
        return;
      }
      const dlg = $("kcPublishDlg");
      if (!dlg) return;
      $("kcPublishTitle").value = resolveTitleFromCover(state.cover);
      $("kcPublishDirect").checked = false;
      $("kcPublishStatus").textContent = "";
      $("kcPublishStatus").className = "status";
      if ($("kcXhsHalfAuto")) $("kcXhsHalfAuto").hidden = true;
      if ($("kcXhsCaption")) $("kcXhsCaption").value = "";
      if ($("kcXhsHalfNote")) $("kcXhsHalfNote").textContent = "";
      await refreshAuthStatus();
      await loadPlatConfig("weixin");
      if (typeof dlg.showModal === "function") dlg.showModal();
      else dlg.setAttribute("open", "open");
    }

    async function showXhsHalfAuto(result) {
      const box = $("kcXhsHalfAuto");
      if (!box) return;
      box.hidden = false;
      const cap = result.caption || "";
      if ($("kcXhsCaption")) $("kcXhsCaption").value = cap;
      if ($("kcXhsHalfNote")) {
        $("kcXhsHalfNote").textContent = result.message
          || `已准备 ${result.image_count || 0} 张图。复制文案后打开创作者中心上传。`;
      }
      state._xhsCreatorUrl = result.creator_url || result.url || "https://creator.xiaohongshu.com/publish/publish";
    }

    async function confirmPublish(ev) {
      if (ev && ev.submitter && ev.submitter.value === "cancel") return;
      if (ev) ev.preventDefault();
      if (state.publishing) return;
      const dlg = $("kcPublishDlg");
      const form = $("kcPublishForm");
      const plats = [...form.querySelectorAll('input[name="plat"]:checked')].map((el) => el.value);
      if (!plats.length) {
        $("kcPublishStatus").textContent = "请至少选择一个平台";
        $("kcPublishStatus").className = "status err";
        return;
      }
      state.publishing = true;
      syncPublishBtn();
      $("kcPublishConfirm").disabled = true;
      $("kcPublishStatus").textContent = "正在导出并上传图片…";
      $("kcPublishStatus").className = "status";
      try {
        await uploadExportImages();
        $("kcPublishStatus").textContent = "正在发布…";
        const out = await api("/api/cards/publish", {
          method: "POST",
          body: JSON.stringify({
            history_id: state.activeHistoryId,
            platforms: plats,
            direct: !!$("kcPublishDirect").checked,
            title: ($("kcPublishTitle").value || "").trim(),
          }),
        });
        const msgs = (out.results || []).map((r) => `${r.platform}: ${r.message || r.status}`).join("；");
        $("kcPublishStatus").textContent = msgs || "完成";
        $("kcPublishStatus").className = "status ok";
        $("kcScanNote").textContent = `发布完成 · ${out.title || ""}`;
        $("kcScanNote").className = "status ok";
        const xhs = (out.results || []).find((r) => r.platform === "xiaohongshu" && (r.half_auto || r.caption));
        if (xhs) {
          await showXhsHalfAuto(xhs);
        } else {
          await refreshHistory();
          setTimeout(() => {
            if (dlg && dlg.open) dlg.close();
          }, 900);
        }
        await refreshHistory();
      } catch (e) {
        $("kcPublishStatus").textContent = "发布失败：" + (e.message || e);
        $("kcPublishStatus").className = "status err";
      } finally {
        state.publishing = false;
        $("kcPublishConfirm").disabled = false;
        syncPublishBtn();
      }
    }

    async function researchDeep() {
      if (state.researching || state.scanning || state.composing) return null;
      state.researching = true;
      state.isTemplatePreview = false;
      const researchBtn = $("kcResearchBtn");
      const composeBtn = $("kcComposeBtn");
      const scanBtn = $("kcScanBtn");
      if (researchBtn) { researchBtn.disabled = true; researchBtn.textContent = "采编中…"; }
      if (composeBtn) composeBtn.disabled = true;
      if (scanBtn) scanBtn.disabled = true;
      $("kcScanNote").textContent = "采编中…";
      $("kcScanNote").className = "status";
      try {
        const roles = parseRolesInput();
        const body = {
          roles,
          category: state.category,
          use_workbench_llm: true,
          edition: editionInputValue(),
        };
        if (state.packId) body.appendPackId = state.packId;
        // First research after an Agent/hotspot handoff: pass fetched notes
        // so the pack starts from on-topic seed evidence (top-up only if thin).
        if (state.handoff && !state.packId) {
          if (state.handoff.research_notes) body.research_notes = state.handoff.research_notes;
          if (state.handoff.search_terms) body.search_terms = state.handoff.search_terms;
          if (state.handoff.source) body.source = state.handoff.source;
          if (state.handoff.url) body.url = state.handoff.url;
          state.handoff = null;
        }
        if (state.contentProjectId) body.content_project_id = state.contentProjectId;
        const data = await api("/api/cards/research", {
          method: "POST",
          body: JSON.stringify(body),
        });
        if (data.content_project_id) state.contentProjectId = data.content_project_id;
        if (data.error && !data.evidencePack) {
          $("kcScanNote").textContent = data.error;
          $("kcScanNote").className = "status err";
          return data;
        }
        if (data.category) state.category = data.category;
        state.evidencePack = data.evidencePack || { evidences: [], count: 0 };
        if (!Array.isArray(state.evidencePack.evidences)) state.evidencePack.evidences = [];
        state.evidencePack.count = Number(state.evidencePack.count || state.evidencePack.evidences.length || 0);
        state.packId = data.packId || data.id || state.packId || "";
        if (data.sources) state.sources = data.sources;
        applyCategoryUI();
        showSources();
        renderEvidenceList();
        const n = state.evidencePack.count || state.evidencePack.evidences.length || 0;
        const note = n
          ? `素材就绪（${n} 条）`
          : (data.error || "无可用证据");
        $("kcScanNote").textContent = note;
        $("kcScanNote").className = n ? "status ok" : "status err";
        await refreshHistory().catch(() => {});
        onLlmRefresh();
        return data;
      } catch (e) {
        $("kcScanNote").textContent = "深采失败：" + (e.message || e);
        $("kcScanNote").className = "status err";
        throw e;
      } finally {
        state.researching = false;
        if (researchBtn) { researchBtn.disabled = false; researchBtn.textContent = "深采"; }
        if (scanBtn) scanBtn.disabled = false;
        renderEvidenceList();
        applyCategoryUI();
      }
    }

    async function composeJournal() {
      if (state.composing || state.scanning || state.researching) return null;
      syncEvidenceSelectionFromDom();
      if (selectedEvidenceCount() < 5) {
        $("kcScanNote").textContent = "请至少勾选 5 条素材后再成刊";
        $("kcScanNote").className = "status err";
        renderEvidenceList();
        return null;
      }
      state.composing = true;
      state.isTemplatePreview = false;
      const researchBtn = $("kcResearchBtn");
      const composeBtn = $("kcComposeBtn");
      const scanBtn = $("kcScanBtn");
      if (composeBtn) { composeBtn.disabled = true; composeBtn.textContent = "成刊中…"; }
      if (researchBtn) researchBtn.disabled = true;
      if (scanBtn) scanBtn.disabled = true;
      $("kcScanNote").textContent = "成刊中…";
      $("kcScanNote").className = "status";
      try {
        const roles = parseRolesInput();
        const data = await api("/api/cards/compose", {
          method: "POST",
          body: JSON.stringify({
            packId: state.packId || undefined,
            evidences: state.evidencePack.evidences,
            roles,
            category: state.category,
            use_workbench_llm: true,
            edition: editionInputValue(),
            content_project_id: state.contentProjectId || undefined,
          }),
        });
        if (data.export_ready && data.automation_hint) {
          $("kcScanNote").textContent = (data.automation_hint || "") + " · 成刊完成";
          $("kcScanNote").className = "status ok";
        }
        if (data.category) state.category = data.category;
        applyCategoryUI();
        if (data.evidencePack) {
          state.evidencePack = data.evidencePack;
          if (!Array.isArray(state.evidencePack.evidences)) state.evidencePack.evidences = [];
        }
        if (data.packId || data.id) state.packId = data.packId || data.id;
        const ed = data.edition || (data.cover && data.cover.edition) || editionInputValue() || "";
        const edNum = String(ed).match(/(\d+)/);
        const note = `第 ${edNum ? edNum[1] : (ed || "—")} 期已生成`;
        applyPayload(data, { note });
        await refreshHistory();
        onLlmRefresh();
        return data;
      } catch (e) {
        $("kcScanNote").textContent = "成刊失败 · 见下方处理建议";
        $("kcScanNote").className = "status err";
        if (global.QualityPanel) {
          global.QualityPanel.renderError($("kcActionError"), e.message || e, {
            onAction: (id) => {
              if (id === "switch_model" && global.openLlmSettings) global.openLlmSettings();
              else if (id === "retry") composeJournal().catch(() => {});
            },
          });
        }
        throw e;
      } finally {
        state.composing = false;
        if (composeBtn) composeBtn.textContent = "成刊";
        if (researchBtn) researchBtn.disabled = false;
        if (scanBtn) scanBtn.disabled = false;
        renderEvidenceList();
        applyCategoryUI();
      }
    }

    async function scan(rolesOverride) {
      if (state.scanning || state.researching || state.composing) return null;
      state.scanning = true;
      state.isTemplatePreview = false;
      $("kcScanBtn").disabled = true;
      $("kcScanBtn").textContent = "快扫中…";
      const researchBtn = $("kcResearchBtn");
      const composeBtn = $("kcComposeBtn");
      if (researchBtn) researchBtn.disabled = true;
      if (composeBtn) composeBtn.disabled = true;
      $("kcScanNote").textContent = "快扫中…";
      $("kcScanNote").className = "status";
      try {
        const roles = parseRolesInput(rolesOverride);
        const edRaw = editionInputValue();
        const data = await api("/api/cards/scan", {
          method: "POST",
          body: JSON.stringify({
            roles,
            category: state.category,
            use_workbench_llm: true,
            edition: edRaw,
          }),
        });
        if (data.category) state.category = data.category;
        applyCategoryUI();
        const first = ((data.knowledge || [])[0] || {}).topicTitle || "";
        let note = "";
        if (data.mode === "ai" || data.mode === "journal") {
          note = `快扫完成${data.edition ? " · " + data.edition : ""}${first ? " · 首卡：" + first : ""}`;
        } else if (data.llmError) note = `AI 失败（${data.llmError}），已退回扫描/内置`;
        else if (data.mode === "live") note = `实时扫描完成（${data.edition || ""}）`;
        else note = `已用内置教材生成（${data.edition || ""}）`;
        if (data.persisted === "insforge") note += " · 已写入 InsForge";
        else if (data.persisted === "local") note += " · 已存本地";
        applyPayload(data, { note });
        await refreshHistory();
        onLlmRefresh();
        return data;
      } catch (e) {
        $("kcScanNote").textContent = "快扫失败：" + (e.message || e);
        $("kcScanNote").className = "status err";
        throw e;
      } finally {
        state.scanning = false;
        $("kcScanBtn").disabled = false;
        if (researchBtn) researchBtn.disabled = false;
        renderEvidenceList();
        applyCategoryUI();
      }
    }

    async function exportAll(opts) {
      if (state.exporting) return;
      const force = !!(opts && opts.force);
      if (!force && (!state.qualityGatePass || state.qualityWarning)) {
        const blockers =
          (state.lastDepth && state.lastDepth.failed && state.lastDepth.failed.length)
            ? state.lastDepth.failed.slice(0, 4).join("、")
            : "";
        const msg =
          (state.qualityWarning || "成刊质检未通过") +
          (blockers ? `\n未过项：${blockers}` : "") +
          "\n\n未达标成刊不建议导出。仍要强制导出 PNG？";
        if (!confirm(msg)) return;
      }
      if (!global.htmlToImage) {
        $("kcScanNote").textContent = "导出库未加载，请检查网络后刷新";
        $("kcScanNote").className = "status err";
        return;
      }
      state.exporting = true;
      $("kcExportBtn").disabled = true;
      $("kcExportBtn").textContent = "导出中…";
      try {
        const blobs = await exportPngBlobs();
        for (const b of blobs) {
          const a = document.createElement("a");
          a.download = b.name;
          a.href = URL.createObjectURL(b.blob);
          a.click();
          URL.revokeObjectURL(a.href);
          await new Promise((r) => setTimeout(r, 350));
        }
        if ($("kcScanNote")) {
          $("kcScanNote").textContent = `已导出 ${blobs.length} 张 PNG`;
          $("kcScanNote").className = "status ok";
        }
      } catch (e) {
        $("kcScanNote").textContent = "导出失败 · 见下方处理建议";
        $("kcScanNote").className = "status err";
        if (global.QualityPanel) {
          global.QualityPanel.renderError($("kcActionError"), e.message || e, {
            onAction: (id) => {
              if (id === "retry") exportAll({ force: true }).catch(() => {});
            },
          });
        }
      } finally {
        state.exporting = false;
        $("kcExportBtn").disabled = false;
        $("kcExportBtn").textContent = "导出全部 PNG";
      }
    }

    function init() {
      if (state.inited) return;
      state.inited = true;
      state.cover = {
        ...defaultCover,
        title: "",
        description: "",
        tags: [],
        edition: "",
        marketNote: "",
        imageUrl: "",
      };
      state.knowledge = [];
      if ($("kcResearchBtn")) $("kcResearchBtn").onclick = () => researchDeep().catch(() => {});
      if ($("kcComposeBtn")) $("kcComposeBtn").onclick = () => composeJournal().catch(() => {});
      $("kcScanBtn").onclick = () => scan().catch(() => {});
      $("kcHistRefresh").onclick = () => refreshHistory().catch(() => {});
      $("kcExportBtn").onclick = () => exportAll();
      if ($("kcPublishBtn")) $("kcPublishBtn").onclick = () => openPublishDialog().catch(() => {});
      if ($("kcPublishAuthWx")) $("kcPublishAuthWx").onclick = () => openAuth("weixin").catch(() => {});
      if ($("kcPublishAuthTt")) $("kcPublishAuthTt").onclick = () => openAuth("toutiao").catch(() => {});
      if ($("kcOpenPlatSettings")) {
        $("kcOpenPlatSettings").onclick = () => openPlatformSettings(
          ($("kcCfgPlatform") && $("kcCfgPlatform").value) || "weixin"
        );
      }
      if ($("kcCfgTabWx")) $("kcCfgTabWx").onclick = () => loadPlatConfig("weixin").catch(() => {});
      if ($("kcCfgTabTt")) $("kcCfgTabTt").onclick = () => loadPlatConfig("toutiao").catch(() => {});
      if ($("kcCfgTabDy")) $("kcCfgTabDy").onclick = () => loadPlatConfig("douyin").catch(() => {});
      if ($("kcCfgTabXhs")) $("kcCfgTabXhs").onclick = () => loadPlatConfig("xiaohongshu").catch(() => {});
      if ($("kcCfgSaveBtn")) $("kcCfgSaveBtn").onclick = () => savePlatConfig().catch(() => {});
      if ($("kcCfgAuthBtn")) {
        $("kcCfgAuthBtn").onclick = () => {
          const p = ($("kcCfgPlatform") && $("kcCfgPlatform").value) || "weixin";
          openAuth(p).catch(() => {});
        };
      }
      if ($("kcXhsCopyCaption")) {
        $("kcXhsCopyCaption").onclick = async () => {
          const text = ($("kcXhsCaption") && $("kcXhsCaption").value) || "";
          try {
            await navigator.clipboard.writeText(text);
            if ($("kcXhsHalfNote")) $("kcXhsHalfNote").textContent = "文案已复制";
          } catch {
            if ($("kcXhsCaption")) { $("kcXhsCaption").select(); document.execCommand("copy"); }
            if ($("kcXhsHalfNote")) $("kcXhsHalfNote").textContent = "已尝试复制（若失败请手动选中）";
          }
        };
      }
      if ($("kcXhsOpenCreator")) {
        $("kcXhsOpenCreator").onclick = () => {
          const url = state._xhsCreatorUrl || "https://creator.xiaohongshu.com/publish/publish";
          window.open(url, "_blank", "noopener");
        };
      }
      if ($("kcXhsDownload")) {
        $("kcXhsDownload").onclick = () => exportAll();
      }
      if ($("globalPlatBtn")) $("globalPlatBtn").onclick = () => openPlatformSettings("weixin");
      if ($("globalPlatClose")) $("globalPlatClose").onclick = () => closePlatformSettings();
      if ($("kcPublishForm")) {
        $("kcPublishForm").addEventListener("submit", (ev) => {
          if (ev.submitter && ev.submitter.value === "ok") {
            confirmPublish(ev).catch(() => {});
          }
        });
      }
      // OAuth return hint
      try {
        const q = new URLSearchParams(location.search);
        if (q.get("oauth") === "ok") {
          if ($("kcScanNote")) {
            $("kcScanNote").textContent = `平台授权成功（${q.get("platform") || ""}）`;
            $("kcScanNote").className = "status ok";
          }
          refreshAuthStatus().catch(() => {});
        } else if (q.get("oauth") === "err") {
          if ($("kcScanNote")) {
            $("kcScanNote").textContent = `授权失败：${q.get("msg") || ""}`;
            $("kcScanNote").className = "status err";
          }
        }
      } catch { /* ignore */ }
      if ($("kcScanNote") && !$("kcScanNote").textContent) {
        $("kcScanNote").textContent = "准备就绪 · 点击「深采」或「快扫」开始";
        $("kcScanNote").className = "status";
      }
      renderEvidenceList();
      renderTabs(); renderEditor(); renderPreview();
      syncPublishBtn();
      refreshAuthStatus().catch(() => {});
    }

    async function ensureReady() {
      init();
      try {
        const data = await api("/api/cards/categories");
        state.categories = data.categories || [];
        renderCategories();
      } catch {
        state.categories = [
          { id: "hiring_insight", label: "招聘洞察", short: "招聘", description: "", topic_label: "岗位", action_label: "深采并成刊", default_topics: [], cover_layout: "classic", know_layout: "talent", palette: "teal", decor: "rings", template_label: "能力图谱", preview: {} },
        ];
        renderCategories();
      }
      await refreshHistory().catch(() => {});
      if (!state.activeHistoryId) showTemplatePreview();
      onLlmRefresh();
    }

    return {
      init,
      ensureReady,
      scan,
      researchDeep,
      composeJournal,
      loadHistory,
      deleteHistory,
      applyPayload,
      openPlatformSettings,
      closePlatformSettings,
      refreshAuthStatus,
      getActiveId: () => state.activeHistoryId,
      getCategory: () => state.category,
      setCategory: (id) => {
        state.category = id || "hiring_insight";
        applyCategoryUI();
      },
      setRoles: (roles) => {
        if ($("kcRolesInput")) {
          $("kcRolesInput").value = Array.isArray(roles) ? roles.join("、") : String(roles || "");
        }
      },
      setHandoff: (h) => {
        state.handoff = h && (h.research_notes || h.search_terms || h.url) ? {
          research_notes: String(h.research_notes || ""),
          search_terms: Array.isArray(h.search_terms) ? h.search_terms : [],
          source: String(h.source || ""),
          url: String(h.url || ""),
        } : null;
        if (h && h.content_project_id) {
          state.contentProjectId = String(h.content_project_id);
        }
      },
      setContentProjectId: (id) => {
        state.contentProjectId = String(id || "");
      },
      getContentProjectId: () => state.contentProjectId || "",
    };
  }

  global.CardsWorkshop = { create: createWorkshop };
})(window);
