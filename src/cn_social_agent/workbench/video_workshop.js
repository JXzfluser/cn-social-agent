/** Short-video workshop helpers — templates, funnel, usage (loaded by index.html). */
(function (global) {
  const VIDEO_TEMPLATES = [
    {
      id: "product_update",
      label: "产品更新",
      hint: "15s 停滑：这周上了什么 → 谁该关心 → 怎么试",
      content_angle: "intro",
      target_seconds: 15,
      bg_theme: "studio",
      placeholder_topic: "本周产品更新：…",
    },
    {
      id: "tech_rant",
      label: "技术吐槽",
      hint: "15s 观点：信号 → 判断 → 误区 → CTA",
      content_angle: "idea",
      target_seconds: 15,
      bg_theme: "dawn",
      placeholder_topic: "吐槽 / 观点：…",
    },
    {
      id: "tutorial",
      label: "教程口播",
      hint: "约 90s：是什么 → 三步上手 → 一个坑",
      content_angle: "intro",
      target_seconds: 90,
      bg_theme: "night",
      placeholder_topic: "教程：从零跑通 …",
    },
  ];

  function getTemplate(id) {
    return VIDEO_TEMPLATES.find((t) => t.id === id) || VIDEO_TEMPLATES[0];
  }

  function applyVideoTemplate(id, $) {
    const t = getTemplate(id);
    if ($("videoTemplateSel")) $("videoTemplateSel").value = t.id;
    document.querySelectorAll("[data-video-template]").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-video-template") === t.id);
    });
    if ($("contentAngleSel")) {
      const opt = Array.from($("contentAngleSel").options || []).find((o) => o.value === t.content_angle);
      if (opt) $("contentAngleSel").value = t.content_angle;
      else if (t.content_angle === "idea") {
        // ensure idea option exists for tech_rant
        $("contentAngleSel").value = "intro";
      }
    }
    if ($("secondsSel")) $("secondsSel").value = String(t.target_seconds);
    if ($("bgThemeSel")) $("bgThemeSel").value = t.bg_theme;
    if ($("durationHint")) $("durationHint").textContent = t.hint;
    if ($("topicInput") && !$("topicInput").value.trim()) {
      $("topicInput").placeholder = t.placeholder_topic || "例如：Redis 缓存穿透怎么防";
    }
    return t;
  }

  function resolveBriefFromTemplate($, prefs, extra) {
    prefs = prefs || {};
    extra = extra || {};
    const tmplId =
      ($("videoTemplateSel") && $("videoTemplateSel").value) ||
      extra.template_id ||
      "product_update";
    const t = getTemplate(tmplId);
    let angle =
      ($("contentAngleSel") && $("contentAngleSel").value) ||
      prefs.default_content_angle ||
      t.content_angle ||
      "intro";
    if (angle === "general") angle = "intro";
    let seconds = parseInt(($("secondsSel") && $("secondsSel").value) || t.target_seconds || 15, 10);
    if (!Number.isFinite(seconds)) seconds = t.target_seconds;
    // Prefer explicit seconds from template/UI over legacy angle→120 mapping
    if (!$("secondsSel") || !$("secondsSel").value) {
      seconds = t.target_seconds;
    }
    let bg = ($("bgThemeSel") && $("bgThemeSel").value) || t.bg_theme || "night";
    if (angle === "deep_analysis") {
      seconds = 180;
      bg = "desk";
      if ($("secondsSel")) $("secondsSel").value = "180";
      if ($("bgThemeSel")) $("bgThemeSel").value = "desk";
    } else {
      if ($("secondsSel")) $("secondsSel").value = String(seconds);
      if ($("bgThemeSel")) $("bgThemeSel").value = bg;
    }
    const audience =
      ($("audienceInput") && $("audienceInput").value.trim()) ||
      prefs.default_audience ||
      "";
    const platform =
      ($("platformSel") && $("platformSel").value) ||
      prefs.default_platform ||
      "抖音";
    return {
      template_id: t.id,
      tone: ($("toneInput") && $("toneInput").value) || "硬核但不装",
      target_seconds: seconds,
      voice:
        ($("voiceSel") && $("voiceSel").value) ||
        prefs.default_voice ||
        "zh-CN-XiaoxiaoNeural",
      audience,
      scene_setting: $("sceneInput") ? $("sceneInput").value.trim() : "",
      platform,
      cta: $("ctaInput") ? $("ctaInput").value.trim() : "",
      bg_theme: bg,
      motion: "kenburns",
      content_angle: angle,
      render_mode: "local",
      threejs_transitions: $("threejsTransitions") ? $("threejsTransitions").checked : false,
      threejs_cards: $("threejsCards") ? $("threejsCards").checked : false,
      ...extra,
    };
  }

  function formatFunnelTs(raw) {
    if (!raw) return "—";
    try {
      const d = new Date(raw);
      if (Number.isNaN(d.getTime())) return String(raw).slice(0, 19);
      return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    } catch {
      return "—";
    }
  }

  function renderFunnelPanel(funnel, el) {
    if (!el) return;
    const f = funnel || {};
    const steps = [
      { key: "t_created", label: "创建" },
      { key: "t_script_ready", label: "分镜" },
      { key: "t_l0_ready", label: "L0 草稿" },
      { key: "t_l1_ready", label: "L1 成片" },
      { key: "t_downloaded", label: "下载" },
    ];
    el.innerHTML = steps
      .map((s) => {
        const done = !!f[s.key];
        return `<span class="funnel-step${done ? " done" : ""}" title="${s.key}">${s.label}<small>${formatFunnelTs(f[s.key])}</small></span>`;
      })
      .join("");
  }

  async function refreshUsageSummary(api, el) {
    if (!el || !api) return;
    try {
      const data = await api("/api/usage/summary?days=7");
      const l1 = data.l1_scene_units || 0;
      const l0 = data.l0_scene_units || 0;
      const cost = data.estimated_cost_cny != null ? data.estimated_cost_cny : "—";
      el.textContent = `本周 L0 ${l0} 镜 · L1 ${l1} 镜 · 估 ¥${cost}`;
      el.hidden = false;
    } catch {
      el.textContent = "";
      el.hidden = true;
    }
  }

  function wireTemplatePicker($, onChange) {
    document.querySelectorAll("[data-video-template]").forEach((btn) => {
      btn.onclick = () => {
        const id = btn.getAttribute("data-video-template");
        applyVideoTemplate(id, $);
        if (typeof onChange === "function") onChange(id);
      };
    });
    if ($("videoTemplateSel")) {
      $("videoTemplateSel").onchange = () => {
        applyVideoTemplate($("videoTemplateSel").value, $);
        if (typeof onChange === "function") onChange($("videoTemplateSel").value);
      };
    }
  }

  global.VideoWorkshop = {
    VIDEO_TEMPLATES,
    getTemplate,
    applyVideoTemplate,
    resolveBriefFromTemplate,
    renderFunnelPanel,
    refreshUsageSummary,
    wireTemplatePicker,
    formatFunnelTs,
  };
})(typeof window !== "undefined" ? window : globalThis);
