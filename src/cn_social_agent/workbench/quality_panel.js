/**
 * Shared quality panel + actionable error cards for CN Workbench.
 *
 * Usage (global):
 *   QualityPanel.render(el, report)
 *   QualityPanel.renderError(el, errOrString, { onAction })
 *   QualityPanel.fromJournalDepth(depth)
 *   QualityPanel.fromPresentation({ content, final, verification })
 *   QualityPanel.classifyError(message)
 */
(function (global) {
  "use strict";

  const JOURNAL_LABELS = {
    cards_ge_5: "卡片数达标",
    kinds_ge_3: "类型多样",
    has_front_matter: "导读/目录齐全",
    evidence_coverage_ge_half: "证据覆盖 ≥ 半",
    no_theme_pad: "无模板注水",
    flow_not_truncated: "流程未截断",
    diagrams_complete: "图示齐全",
    cover_tags_ok: "封面标签完整",
    market_note_clean: "市场注干净",
    data_has_metric: "数据卡有指标",
    compare_has_sides: "对比卡双边齐全",
    no_shallow_cliche: "无空洞套话",
    mode_not_cached: "非缓存降级",
  };

  const PRES_LABELS = {
    depth_ok: "文稿深度达标",
    stage_built: "舞台已构建",
    a1_confirmed: "已确认 A1",
    demo_verify_pass: "沙箱验证通过",
    narration_timeline_ok: "旁白时间轴 OK",
  };

  const ERROR_RULES = [
    {
      code: "edge_tts_network",
      re: /edge-tts|NoAudioReceived|语音合成失败/i,
      title: "语音合成失败",
      reason: "连不上 Microsoft TTS，或本机 edge-tts CLI 与当前 Python 环境不一致。",
      actions: [
        { id: "retry_tts_api", label: "改用内置 API 重试" },
        { id: "retry", label: "再试一次" },
      ],
    },
    {
      code: "agnes_queue",
      re: /video_queue_full|队列已满|queue is full/i,
      title: "Agnes 视频队列已满",
      reason: "云端排队过载。可稍后重试本镜，或先用本地 L0 出片。",
      actions: [
        { id: "retry", label: "稍后重试" },
        { id: "use_local_l0", label: "改用本地渲染" },
      ],
    },
    {
      code: "missing_scene",
      re: /缺少分镜片段|scene_\d+\.mp4/i,
      title: "缺少分镜片段",
      reason: "成片拼接时找不到某镜 mp4。请先完整渲染，或只重渲缺失镜。",
      actions: [
        { id: "rerender_missing", label: "重渲缺失镜" },
        { id: "rerender_all", label: "完整重渲" },
      ],
    },
    {
      code: "llm_json",
      re: /LLM JSON|Expecting value|Expecting ['"],|未返回合法 JSON|JSON 解析失败/i,
      title: "AI 返回格式损坏",
      reason: "模型输出不是合法 JSON（常被截断或夹杂说明文字）。换模型或重试通常可恢复。",
      actions: [
        { id: "retry", label: "重试" },
        { id: "switch_model", label: "切换模型" },
      ],
    },
    {
      code: "generate_failed",
      re: /generate_failed/i,
      title: "分镜生成失败",
      reason: "脚本/分镜 LLM 调用失败。可换模型后重试，或先改主题再生成。",
      actions: [
        { id: "retry", label: "重试生成" },
        { id: "switch_model", label: "切换模型" },
      ],
    },
    {
      code: "docker_unavailable",
      re: /Docker 不可用|docker.*(not|不可)|unavailable/i,
      title: "沙箱 Docker 不可用",
      reason: "本机 Docker 未启动或无权访问，demo 验证无法执行。",
      actions: [{ id: "retry_verify", label: "启动后重试验证" }],
    },
    {
      code: "agnes_no_url",
      re: /completed but no url|Agnes video completed but no url/i,
      title: "Agnes 成片无下载地址",
      reason: "任务已完成但未返回 video url，多为上游短暂故障。",
      actions: [{ id: "retry", label: "重试本镜" }],
    },
  ];

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function shortDetail(msg, n) {
    const s = String(msg || "")
      .replace(/\s+/g, " ")
      .trim();
    if (s.length <= (n || 160)) return s;
    return s.slice(0, (n || 160) - 1) + "…";
  }

  function classifyError(message, fallbackTitle) {
    if (message && typeof message === "object" && message.code && message.title) {
      return message;
    }
    const raw = String(message || "").trim();
    const detail = shortDetail(raw);
    for (const rule of ERROR_RULES) {
      if (rule.re.test(raw)) {
        let reason = rule.reason;
        if (
          rule.code === "edge_tts_network" &&
          !/(nodename|Cannot connect|gaierror|Timeout|NoAudioReceived|连不上)/i.test(raw)
        ) {
          reason = "edge-tts 命令失败。可改用内置 API，或检查 CLI 是否装在当前环境。";
        }
        return {
          code: rule.code,
          title: rule.title,
          reason,
          detail,
          actions: rule.actions.map((a) => ({ ...a })),
          raw: raw.slice(0, 400),
        };
      }
    }
    return {
      code: "generic",
      title: fallbackTitle || "操作失败",
      reason: detail || "未知错误",
      detail,
      actions: [{ id: "retry", label: "重试" }],
      raw: raw.slice(0, 400),
    };
  }

  function fromJournalDepth(depth) {
    const d = depth && typeof depth === "object" ? depth : {};
    const checks = d.checks || {};
    const stats = d.stats || {};
    const items = [];
    Object.keys(JOURNAL_LABELS).forEach((key) => {
      if (!(key in checks)) return;
      const ok = !!checks[key];
      let detail = "";
      if (key === "cards_ge_5") detail = (stats.cards || 0) + " 张";
      else if (key === "kinds_ge_3") {
        const kinds = stats.kinds || [];
        detail = kinds.length + " 种" + (kinds.length ? "（" + kinds.slice(0, 4).join(", ") + "）" : "");
      } else if (key === "evidence_coverage_ge_half") {
        detail = (stats.with_evidence || 0) + "/" + (stats.cards || 0);
      } else if (key === "flow_not_truncated" && stats.flow_broken) {
        detail = stats.flow_broken + " 处截断";
      } else if (key === "has_front_matter") {
        detail = "导读 " + (stats.promises || 0) + " · 目录 " + (stats.toc || 0);
      }
      items.push({
        id: key,
        label: JOURNAL_LABELS[key],
        status: ok ? "pass" : "fail",
        detail,
      });
    });
    const failed = items.filter((i) => i.status === "fail");
    return {
      ok: !!d.ok && failed.length === 0,
      track: "journal",
      title: "成刊质量",
      items,
      blockers: failed.map((i) => i.label + (i.detail ? "（" + i.detail + "）" : "")),
      hint: d.hint || (failed.length ? "成刊未达标" : "成刊质检通过"),
    };
  }

  function fromPresentation(opts) {
    const o = opts || {};
    const content = o.content || {};
    const finalQc = o.final || {};
    const verification = o.verification || content.verification || {};
    const checks = content.checks || {};
    const items = [];
    Object.keys(PRES_LABELS).forEach((key) => {
      if (!(key in checks)) return;
      items.push({
        id: key,
        label: PRES_LABELS[key],
        status: checks[key] ? "pass" : "fail",
        detail: "",
      });
    });
    if (verification && (verification.declared || (verification.roles_present || []).length)) {
      let st = "pending";
      let detail = "";
      if (verification.ok) {
        st = "pass";
        detail = (verification.passed || 0) + "/" + (verification.declared || 0) + " 步";
      } else if (verification.pending) {
        st = "pending";
        detail = verification.pending + " 步未跑";
      } else if (verification.unavailable) {
        st = "fail";
        detail = "Docker 不可用";
      } else if (verification.failed) {
        st = "fail";
        detail = verification.failed + " 步失败";
      } else if ((verification.missing_roles || []).length) {
        st = "fail";
        detail = "缺声明：" + verification.missing_roles.join("、");
      }
      const existing = items.find((i) => i.id === "demo_verify_pass");
      if (existing) existing.detail = detail || existing.detail;
      else items.push({ id: "sandbox_verify", label: "沙箱验证", status: st, detail });
    }
    if (finalQc && (finalQc.path !== undefined || finalQc.reasons || finalQc.ok !== undefined)) {
      if (!finalQc.path) {
        items.push({
          id: "final_imported",
          label: "成片已导入",
          status: "pending",
          detail: "尚未导入",
        });
      } else {
        items.push({
          id: "final_qc",
          label: "成片质检",
          status: finalQc.ok ? "pass" : "fail",
          detail: ((finalQc.reasons || []).slice(0, 2) || []).join("；"),
        });
      }
    }
    const blockers = items
      .filter((i) => i.status === "fail")
      .map((i) => i.label + (i.detail ? "（" + i.detail + "）" : ""));
    const pending = items.filter((i) => i.status === "pending");
    const ok = blockers.length === 0 && pending.length === 0 && items.length > 0;
    return {
      ok,
      track: "presentation",
      title: "讲解质量",
      items,
      blockers,
      hint:
        o.hint ||
        (ok
          ? "双质检通过"
          : blockers.length
            ? "未达标：" + blockers.slice(0, 3).join("、")
            : pending.length
              ? "待完成：" + pending.map((p) => p.label).slice(0, 3).join("、")
              : "尚无质检数据"),
    };
  }

  function statusDot(status) {
    if (status === "pass") return "qp-dot ok";
    if (status === "fail") return "qp-dot bad";
    if (status === "pending") return "qp-dot pending";
    return "qp-dot skip";
  }

  function render(el, report, opts) {
    if (!el) return;
    const r = report || { ok: true, items: [], blockers: [], hint: "", title: "质量" };
    const items = r.items || [];
    if (!items.length && !r.hint) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    el.hidden = false;
    const head =
      '<div class="qp-head">' +
      '<span class="qp-title">' +
      esc(r.title || "质量") +
      "</span>" +
      '<span class="qp-badge ' +
      (r.ok ? "ok" : "bad") +
      '">' +
      (r.ok ? "通过" : "未过") +
      "</span></div>";
    const list = items
      .map((it) => {
        return (
          '<div class="qp-row">' +
          '<span class="' +
          statusDot(it.status) +
          '"></span>' +
          '<span class="qp-label">' +
          esc(it.label) +
          "</span>" +
          (it.detail
            ? '<span class="qp-detail">' + esc(it.detail) + "</span>"
            : '<span class="qp-detail"></span>') +
          "</div>"
        );
      })
      .join("");
    let foot = "";
    if ((r.blockers || []).length && opts && opts.blockLabel) {
      foot =
        '<div class="qp-block">' +
        esc(opts.blockLabel) +
        "：" +
        esc(r.blockers.slice(0, 4).join("、")) +
        "</div>";
    } else if (!r.ok && r.hint) {
      foot = '<div class="qp-block">' + esc(r.hint) + "</div>";
    } else if (r.ok && r.hint) {
      foot = '<div class="qp-okhint">' + esc(r.hint) + "</div>";
    }
    el.innerHTML =
      '<div class="qp-card">' + head + '<div class="qp-list">' + list + "</div>" + foot + "</div>";
  }

  function renderError(el, errOrString, opts) {
    if (!el) return;
    const onAction = (opts && opts.onAction) || null;
    if (!errOrString) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    const err = classifyError(errOrString, (opts && opts.fallbackTitle) || "操作失败");
    el.hidden = false;
    const actions = (err.actions || [])
      .map(
        (a, idx) =>
          '<button type="button" class="qp-act' +
          (idx === 0 ? " primary" : "") +
          '" data-action="' +
          esc(a.id) +
          '">' +
          esc(a.label) +
          "</button>"
      )
      .join("");
    el.innerHTML =
      '<div class="ae-card" data-code="' +
      esc(err.code) +
      '">' +
      '<div class="ae-title">' +
      esc(err.title) +
      "</div>" +
      '<div class="ae-reason">' +
      esc(err.reason) +
      "</div>" +
      (err.detail && err.detail !== err.reason
        ? '<details class="ae-detail"><summary>技术细节</summary><code>' +
          esc(err.detail) +
          "</code></details>"
        : "") +
      '<div class="ae-actions">' +
      actions +
      "</div></div>";
    el.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (typeof onAction === "function") onAction(btn.getAttribute("data-action"), err);
      });
    });
  }

  function clear(el) {
    if (!el) return;
    el.hidden = true;
    el.innerHTML = "";
  }

  global.QualityPanel = {
    classifyError,
    fromJournalDepth,
    fromPresentation,
    render,
    renderError,
    clear,
    JOURNAL_LABELS,
    PRES_LABELS,
  };
})(typeof window !== "undefined" ? window : globalThis);
