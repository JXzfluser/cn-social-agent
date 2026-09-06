/* ============================================================================
 * Nexus 工作台前端 —— 对标 OpenWorkBuddy（聊天优先 + 四模式 + 能力广场 + 自动化）
 * 零框架原生实现。后端契约见 /api/* 路由。
 * ========================================================================== */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const el = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const L = {}; // i18n
  function t(k, d) { return (L[k] != null ? L[k] : (d != null ? d : k)); }
  const enc = (s) => encodeURIComponent(s);

  const state = {
    token: localStorage.getItem("nexus_token") || "",
    user: null,
    locale: localStorage.getItem("nexus_locale") || "zh-CN",
    theme: localStorage.getItem("nexus_theme") || "light",
    sessions: [],
    currentSessionId: null,
    messages: [],
    chatMode: localStorage.getItem("nexus_mode") || "craft", // ask|plan|goal|craft
    model: "",          // 当前会话模型（空=跟随默认）
    perm: localStorage.getItem("nexus_perm") || "auto", // ask|auto|full
    defaultExpert: localStorage.getItem("nexus_expert") || "",
    customTemplates: [],
    defaultModel: "",
    experts: [],
    skills: [],
    connectors: [],
    automations: [],
    streaming: false,
    abort: null,
    pendingAttachment: null,
    sideView: "chat",
    pins: JSON.parse(localStorage.getItem("nexus_pins") || "[]"),
  };

  /* ---------- API ---------- */
  async function api(method, path, body, opt) {
    opt = opt || {};
    const headers = { "Content-Type": "application/json" };
    if (state.token) headers["Authorization"] = "Bearer " + state.token;
    const init = { method, headers };
    if (body) init.body = JSON.stringify(body);
    let res;
    try {
      res = await fetch(path, init);
    } catch (e) {
      onOffline();
      throw new Error("网络不可达");
    }
    if (res.status === 401) {
      // 自动静默重登一次（本地工作台：凭据在 localStorage）；失败才登出
      if (!opt._retried && state.token) {
        try {
          const saved = JSON.parse(localStorage.getItem("nexus_auth") || "null");
          if (saved && saved.email && saved.password) {
            const lr = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(saved) });
            if (lr.ok) {
              const ld = await lr.json();
              if (ld.accessToken) {
                state.token = ld.accessToken;
                localStorage.setItem("nexus_token", state.token);
                return api(method, path, body, { ...opt, _retried: true });
              }
            }
          }
        } catch (e) { /* 落到 logout */ }
      }
      logout(); throw new Error("登录已失效，请重新登录");
    }
    if (res.status === 204) return null;
    let data = null;
    try { data = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) throw new Error((data && data.error) ? data.error : ("请求失败 (" + res.status + ")"));
    onOnline();
    return data;
  }
  // 成片预览：download?inline=1 需要 JWT，<video> 标签无法附带 Authorization，
  // 故用 fetch 带 token 取 blob 再喂给 <video>（data-pv-src 标记待绑定元素）。
  function bindPreviewVideos(root) {
    if (!root) return;
    root.querySelectorAll("video[data-pv-src]").forEach((v) => {
      const url = v.getAttribute("data-pv-src");
      v.removeAttribute("data-pv-src");
      fetch(url, { headers: { Authorization: "Bearer " + state.token } })
        .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.blob(); })
        .then((b) => { v.src = URL.createObjectURL(b); })
        .catch((e) => {
          const msg = (e.message === "HTTP 404")
            ? "本镜暂未生成（渲染中）"
            : "预览暂不可用（" + esc(e.message) + "）";
          v.outerHTML = '<div class="muted" style="font-size:12px;padding:8px">' + msg + "</div>";
        });
    });
  }
  // 逐镜预览网格：只给已就绪的 scene_N_agnes.mp4 渲染播放器，未就绪显示"渲染中"
  function perSceneGrid(pid, scenes, readyFiles) {
    if (!scenes.length) return "";
    const cells = scenes.map((s) => {
      const n = s.scene_num;
      const fname = "scene_" + n + "_agnes.mp4";
      const ready = (readyFiles || []).indexOf(fname) >= 0;
      const cap = esc(String(s.content || "").slice(0, 28));
      return `<div style="border:1px solid var(--wb-line,#e5e7eb);border-radius:12px;overflow:hidden;background:#0f172a">
        ${ready
          ? `<video controls preload="metadata" data-pv-src="/api/video/projects/${esc(pid)}/scenes/${esc(fname)}" style="width:100%;display:block;aspect-ratio:9/16;object-fit:cover;background:#000"></video>`
          : `<div style="width:100%;aspect-ratio:9/16;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:12px">本镜渲染中…</div>`}
        <div style="padding:6px 8px;font-size:12px;color:#cbd5e1"><b>镜 ${n}</b>${cap ? " · " + cap : ""}</div>
      </div>`;
    }).join("");
    return `<div class="out-hd" style="margin-top:14px">逐镜预览（AGNES 实拍 · ${(readyFiles || []).filter((f) => f.indexOf("_agnes") > 0).length}/${scenes.length} 就绪）</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:8px">${cells}</div>`;
  }
  function streamChat(body, onDelta, onDone, onErr) {
    const headers = { "Content-Type": "application/json", "Accept": "text/event-stream" };
    if (state.token) headers["Authorization"] = "Bearer " + state.token;
    const ctrl = new AbortController();
    state.abort = ctrl;
    fetch("/api/chat", { method: "POST", headers, body: JSON.stringify(body), signal: ctrl.signal })
      .then((res) => {
        if (res.status === 401) { logout(); throw new Error("登录已失效"); }
        if (!res.ok) throw new Error("聊天请求失败 (" + res.status + ")");
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buf = "";
        const pump = () => reader.read().then(({ value, done }) => {
          if (done) return;
          buf += dec.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const raw = buf.slice(0, idx); buf = buf.slice(idx + 2);
            const line = raw.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue;
            let ev; try { ev = JSON.parse(line.slice(6)); } catch (e) { continue; }
            if (ev.type === "delta") onDelta(ev.content || "");
            else if (ev.type === "done") onDone(ev);
          }
          return pump();
        });
        return pump();
      })
      .catch((e) => { if (e.name !== "AbortError") onErr(e); });
  }

  /* ---------- 断线自愈 ---------- */
  let offlineTimer = null;
  function onOffline() {
    const b = el("offline"); if (b) b.classList.remove("hidden");
    if (!offlineTimer) offlineTimer = setInterval(checkAlive, 5000);
  }
  function onOnline() {
    const b = el("offline"); if (b) b.classList.add("hidden");
    if (offlineTimer) { clearInterval(offlineTimer); offlineTimer = null; }
  }
  async function checkAlive() {
    try { await api("GET", "/api/nexus/health"); onOnline(); }
    catch (e) { /* still offline */ }
  }

  /* ---------- toast ---------- */
  let toastTimer = null;
  function toast(msg) {
    const t2 = el("toast"); t2.textContent = msg; t2.classList.remove("hidden");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t2.classList.add("hidden"), 2600);
  }

  /* ---------- markdown（轻量） ---------- */
  function md(src) {
    let s = esc(src);
    s = s.replace(/```(\w*)\n([\s\S]*?)```/g, (m, lang, code) =>
      `<pre><code>${code.replace(/\n$/, "")}</code></pre>`);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/^######\s+(.*)$/gm, "<h4>$1</h4>")
         .replace(/^#####\s+(.*)$/gm, "<h4>$1</h4>")
         .replace(/^####\s+(.*)$/gm, "<h4>$1</h4>")
         .replace(/^###\s+(.*)$/gm, "<h3>$1</h3>")
         .replace(/^##\s+(.*)$/gm, "<h2>$1</h2>")
         .replace(/^#\s+(.*)$/gm, "<h1>$1</h1>");
    s = s.replace(/^\s*[-*]\s+(.*)$/gm, "<li>$1</li>");
    s = s.replace(/(<li>[\s\S]*?<\/li>)/g, "<ul>$1</ul>");
    s = s.replace(/<\/ul>\s*<ul>/g, "");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
    return "<p>" + s + "</p>";
  }

  /* ============================ 认证 ============================ */
  function showLogin() { el("login").classList.remove("hidden"); el("main").classList.add("hidden"); }
  function showMain() { el("login").classList.add("hidden"); el("main").classList.remove("hidden"); }
  function logout() {
    state.token = ""; state.user = null; localStorage.removeItem("nexus_token");
    showLogin();
  }
  async function doLogin(mode) {
    const email = el("login-email").value.trim();
    const password = el("login-password").value;
    const name = el("login-name").value.trim();
    const err = el("login-error"); err.hidden = true;
    try {
      const data = await api("POST", "/api/auth/" + (mode === "register" ? "register" : "login"),
        mode === "register" ? { email, password, name } : { email, password });
      state.token = data.accessToken; localStorage.setItem("nexus_token", state.token);
      // 记住凭据：token 过期时自动静默重登（本地/内网工作台场景）
      localStorage.setItem("nexus_auth", JSON.stringify({ email, password }));
      state.user = data.user;
      await enter();
    } catch (e) { err.textContent = e.message; err.hidden = false; }
  }

  /* ============================ 会话 ============================ */
  async function loadSessions() {
    const data = await api("GET", "/api/sessions");
    state.sessions = (data && data.sessions) || data || [];
    renderHistory();
  }
  function renderHistory() {
    const list = el("history");
    const kw = (el("conv-search").value || "").trim().toLowerCase();
    const pinned = new Set(state.pins);
    let arr = state.sessions.slice().sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
    arr = arr.filter((s) => !kw || (s.title || "").toLowerCase().includes(kw));
    arr.sort((a, b) => (pinned.has(b.id) ? 1 : 0) - (pinned.has(a.id) ? 1 : 0));
    if (!arr.length) { list.innerHTML = `<div class="side-label">${kw ? "无匹配对话" : "还没有对话"}</div>`; return; }
    list.innerHTML = arr.map((s) => `
      <div class="hist-item ${s.id === state.currentSessionId ? "active" : ""}" data-id="${esc(s.id)}" title="${esc(s.title)}">
        ${pinned.has(s.id) ? '<span title="置顶">📌</span>' : ""}
        <span class="ht">${esc(s.title || "新对话")}</span>
        <span class="hx" data-ren="${esc(s.id)}" title="重命名">✎</span>
        <span class="hx" data-del="${esc(s.id)}" title="删除">✕</span>
      </div>`).join("");
    list.querySelectorAll(".hist-item").forEach((it) => {
      it.onclick = (ev) => {
        if (ev.target.dataset.del || ev.target.dataset.ren) return;
        selectSession(it.dataset.id);
      };
      const del = it.querySelector("[data-del]");
      if (del) del.onclick = async (ev) => {
        ev.stopPropagation();
        if (!confirm("删除这个对话？")) return;
        try { await api("DELETE", "/api/sessions/" + del.dataset.del); state.sessions = state.sessions.filter((x) => x.id !== del.dataset.del);
          if (state.currentSessionId === del.dataset.del) { state.currentSessionId = null; state.messages = []; renderEmpty(); }
          renderHistory();
        } catch (e) { toast(e.message); }
      };
      const ren = it.querySelector("[data-ren]");
      if (ren) ren.onclick = (ev) => {
        ev.stopPropagation();
        const ht = it.querySelector(".ht");
        const cur = (state.sessions.find((x) => x.id === it.dataset.id) || {}).title || "";
        const inp = document.createElement("input");
        inp.className = "ui-input"; inp.value = cur; inp.style.cssText = "flex:1;height:26px;font-size:12px;padding:2px 8px";
        ht.replaceWith(inp);
        inp.focus(); inp.select();
        const save = async () => {
          const name = inp.value.trim();
          if (!name || name === cur) { renderHistory(); return; }
          try {
            await api("PATCH", "/api/sessions/" + it.dataset.id, { title: name });
            const s = state.sessions.find((x) => x.id === it.dataset.id); if (s) s.title = name;
            renderHistory();
            if (state.currentSessionId === it.dataset.id) el("topbar-title").innerHTML = `${esc(name)} <span class="model-badge" id="topbar-model">${state.model ? esc(state.model) : ""}</span>`;
          } catch (e) { toast(e.message); renderHistory(); }
        };
        inp.onkeydown = (ke) => { if (ke.key === "Enter") { ke.preventDefault(); save(); } if (ke.key === "Escape") renderHistory(); };
        inp.onblur = save;
        inp.onclick = (ie) => ie.stopPropagation();
      };
    });
  }
  function renderEmpty() {
    el("chat-col").innerHTML = `<div class="empty"><h1>有什么可以帮你？</h1>
      <p>一句话下任务，AI 自己规划、拆解、动手，交给你能打开验收的成果文件。</p>
      <div class="scene-tip">输入框左侧可切 <b>问答 / 规划 / 目标 / 执行</b> 四种模式</div>
      <div class="empty-cards">
        <div class="ec" data-ec="/视频 "><b>🎬 口播视频</b><span>主题一句话 → AI 分镜 → 确认 → 竖屏成片</span></div>
        <div class="ec" data-ec="/讲解 "><b>📊 讲解演示</b><span>主题一句话 → AI 起草 → 确认 → 横屏 slides</span></div>
        <div class="ec" data-ec-nav="hotspots"><b>🔥 热点看板</b><span>聚合热点 → 一键转视频</span></div>
        <div class="ec" data-ec-nav="library"><b>📚 资料库</b><span>上传资料 → 对话自动引用（RAG）</span></div>
      </div>
      <div class="scene-tip" style="margin-top:14px">输入 <b>/</b> 唤起模板与制片快捷指令</div></div>`;
    el("topbar-title").innerHTML = `新对话 <span class="model-badge" id="topbar-model">${state.model ? esc(state.model) : ""}</span>`;
    el("chat-col").querySelectorAll("[data-ec]").forEach((c) => c.onclick = () => {
      const nav = c.dataset.ecNav;
      if (nav) { setSideView(nav); return; }
      const input = el("input");
      input.value = c.dataset.ec;
      autoGrow(input); input.focus();
    });
  }
  async function selectSession(id) {
    state.currentSessionId = id;
    setSideView("chat");
    renderHistory();
    const data = await api("GET", "/api/sessions/" + id);
    state.messages = (data && data.messages) || [];
    state.model = (data && data.session && data.session.model) || (data && data.model) || "";
    renderMessages();
    const s = state.sessions.find((x) => x.id === id);
    el("topbar-title").innerHTML = `${esc((s && s.title) || "对话")} <span class="model-badge">${state.model ? esc(state.model) : ""}</span>`;
    updateModelLabel();
  }
  async function newChat() {
    const data = await api("POST", "/api/sessions", { title: "新对话" });
    const s = data.session || data;
    state.sessions.unshift(s);
    await selectSession(s.id);
  }

  /* ============================ 消息渲染 ============================ */
  function renderMessages() {
    const col = el("chat-col");
    if (!state.messages.length) { renderEmpty(); return; }
    const empty = col.querySelector(".empty"); if (empty) empty.remove();
    col.innerHTML = state.messages.map(messageHtml).join("");
    bindMsgOps(col);
    col.scrollTop = col.scrollHeight;
  }
  function messageHtml(m) {
    if (m.role === "user") {
      const att = (m.attachments && m.attachments.length)
        ? `<div class="bubble-attach">${m.attachments.map((a) => `<span>${esc(a.name)}</span>`).join("")}</div>` : "";
      return `<div class="turn"><div class="u-msg"><div class="bubble">${esc(m.content)}${att}</div></div></div>`;
    }
    const acts = `<div class="turn-actions">
      <button class="ta-btn" data-copy title="复制"><svg class="i"><use href="#ic-copy"/></svg></button>
      <span class="ta-meta">${esc(m.model || "")}</span></div>`;
    return `<div class="turn"><div class="a-msg">
      <div class="avatar">N</div>
      <div class="body"><div class="a-text">${md(m.content || "")}</div>${acts}</div></div></div>`;
  }
  /* 发布到抖音：正式发布或半自动发布包（后端自动降级） */
  async function publishDouyin(pid, title, hashtags, description, box) {
    box.innerHTML = `<div class="muted" style="font-size:12px">发布中…</div>`;
    try {
      const d = await api("POST", "/api/video/projects/" + pid + "/publish", {
        title: title || "", hashtags: hashtags || [], description: description || "",
      });
      const r = d.result || {};
      const url = r.url || "";
      box.innerHTML = `<div class="out-hd" style="margin-top:6px">发布结果 · ${esc(r.platform || "douyin")}</div>
        <div class="goal-step ${r.status === "published" ? "done" : "done"}"><span class="ck">${r.status === "published" ? "✓" : "i"}</span><span class="tx">${esc(r.message || r.status || "已生成发布包")}</span></div>
        ${url ? `<div style="margin-top:4px"><a href="${esc(url)}" target="_blank" style="color:var(--wb-brand);font-size:13px">打开发布页 →</a></div>` : ""}
        ${r.status !== "published" ? `<div class="muted" style="font-size:11px;margin-top:4px">未配置抖音凭证时为半自动模式：标题/标签/简介已就绪，下载成片后手动上传即可。</div>` : ""}`;
      toast(r.status === "published" ? "🚀 已发布到抖音" : "已生成半自动发布包");
    } catch (e) { box.innerHTML = `<div class="muted" style="font-size:12px">发布失败：${esc(e.message)}</div>`; }
  }
  function bindMsgOps(col) {
    col.querySelectorAll("[data-copy]").forEach((b) => {
      b.onclick = () => {
        const txt = b.closest(".turn").querySelector(".a-text").innerText;
        navigator.clipboard && navigator.clipboard.writeText(txt);
        toast("已复制");
      };
    });
    // 重新生成：仅最后一条助手消息显示 ↻，点击重发其前的用户消息
    col.querySelectorAll(".turn").forEach((t) => { const r = t.querySelector("[data-regen]"); if (r) r.remove(); });
    const turns = [...col.querySelectorAll(".turn")];
    const lastA = turns.reverse().find((t) => t.querySelector(".a-text"));
    if (lastA && !state.streaming) {
      const ops = lastA.querySelector(".turn-actions");
      if (ops && !ops.querySelector("[data-regen]")) {
        const btn = document.createElement("button");
        btn.className = "ta-btn"; btn.dataset.regen = "1"; btn.title = "重新生成";
        btn.innerHTML = '<svg class="i"><use href="#ic-clock"/></svg>';
        btn.onclick = () => {
          if (state.streaming) return;
          let lastUser = "";
          for (let i = state.messages.length - 1; i >= 0; i--) {
            if (state.messages[i].role === "user") { lastUser = state.messages[i].content || ""; break; }
          }
          if (!lastUser) { toast("没有可重发的消息"); return; }
          el("input").value = lastUser;
          autoGrow(el("input"));
          sendMessage();
        };
        ops.prepend(btn);
      }
    }
  }
  function appendUser(content, atts) {
    state.messages.push({ role: "user", content, attachments: atts || [] });
    const col = el("chat-col");
    const empty = col.querySelector(".empty"); if (empty) empty.remove();
    col.insertAdjacentHTML("beforeend", messageHtml(state.messages[state.messages.length - 1]));
    bindMsgOps(col); col.scrollTop = col.scrollHeight;
  }
  function appendAssistant() {
    const col = el("chat-col");
    const node = document.createElement("div");
    node.className = "turn";
    node.innerHTML = `<div class="a-msg"><div class="avatar">N</div>
      <div class="body"><div class="a-text"></div><div class="turn-actions">
      <button class="ta-btn" data-copy><svg class="i"><use href="#ic-copy"/></svg></button>
      <span class="ta-meta"></span></div></div></div>`;
    col.appendChild(node);
    return node;
  }

  /* ============================ 发送 ============================ */
  function modeSystemPrompt(mode) {
    if (mode === "ask") return "你只回答用户的问题，不要调用任何工具，也不要执行任何文件操作。用简洁清晰的中文回答。";
    if (mode === "plan") return "你只输出分步执行计划（markdown 列表），不要实际执行任何操作、不要调用工具。计划要具体可验收。";
    return ""; // craft / goal 默认
  }
  async function sendMessage() {
    if (state.streaming) return;
    const input = el("input");
    const content = input.value.trim();
    if (!content && !state.pendingAttachment) return;
    if (!state.currentSessionId) await newChat();
    const atts = state.pendingAttachment ? [{ name: state.pendingAttachment.name }] : null;
    const full = state.pendingAttachment ? (content ? content + "\n\n【附件 " + state.pendingAttachment.name + "】\n" + state.pendingAttachment.content : "见附件 " + state.pendingAttachment.name) : content;
    appendUser(content || "（附件）", atts);
    input.value = ""; autoGrow(input); clearAttachment();

    if (full.startsWith("/视频")) { await startVideoFlow(full.replace(/^\/视频\s*/, "").trim() || full.slice(3).trim()); return; }
    if (full.startsWith("/讲解")) { await startPresentationFlow(full.replace(/^\/讲解\s*/, "").trim() || full.slice(3).trim()); return; }
    if (state.chatMode === "goal") { await runGoal(full); return; }

    state.streaming = true; setSendState(true);
    const node = appendAssistant();
    const textEl = node.querySelector(".a-text");
    const meta = node.querySelector(".ta-meta");
    let acc = "";
    streamChat(
      { session_id: state.currentSessionId, content: full, model: state.model || undefined, system_prompt: modeSystemPrompt(state.chatMode) || undefined },
      (d) => { acc += d; textEl.innerHTML = md(acc); el("chat-col").scrollTop = el("chat-col").scrollHeight; },
      (ev) => {
        const saved = ev.message || {};
        state.messages.push({ role: "assistant", content: saved.content || acc, model: (saved.model || ev.model || "") });
        meta.textContent = saved.model || ev.model || "";
        bindMsgOps(node); state.streaming = false; setSendState(false);
        refreshTitleFromFirst();
      },
      (e) => { textEl.innerHTML = md(acc + "\n\n⚠️ " + e.message); state.streaming = false; setSendState(false); }
    );
  }
  function refreshTitleFromFirst() {
    const first = state.messages.find((m) => m.role === "user");
    if (first && state.currentSessionId) {
      const title = (first.content || "").slice(0, 30).replace(/\n/g, " ");
      const s = state.sessions.find((x) => x.id === state.currentSessionId);
      if (s && s.title === "新对话" && title) {
        s.title = title;
        api("PATCH", "/api/sessions/" + state.currentSessionId, { title }).catch(() => {});
        renderHistory();
        el("topbar-title").innerHTML = `${esc(title)} <span class="model-badge">${state.model ? esc(state.model) : ""}</span>`;
      }
    }
  }
  function setSendState(busy) {
    const send = el("send");
    if (busy) { send.classList.add("stop"); send.innerHTML = '<svg class="i"><use href="#ic-x"/></svg>'; send.onclick = stopStreaming; }
    else { send.classList.remove("stop"); send.innerHTML = '<svg class="i"><use href="#ic-send"/></svg>'; send.onclick = sendMessage; }
  }
  function stopStreaming() { if (state.abort) state.abort.abort(); state.streaming = false; setSendState(false); toast("已停止"); }

  /* ============================ Goal 模式（派单 + 自动验收） ============================ */
  async function runGoal(brief) {
    if (!state.experts.length) { try { await loadExperts(); } catch (e) {} }
    const expert = state.experts.find((x) => x.id === state.defaultExpert) || state.experts[0];
    if (!expert) { toast("没有可用专家"); return; }
    const title = brief.slice(0, 40).replace(/\n/g, " ");
    appendUser("🎯 目标：" + (brief.slice(0, 60)), null);
    const cardNode = appendGoalCard(title, "running");
    try {
      const data = await api("POST", "/api/nexus/tasks", { expert_id: expert.id, title, brief });
      const task = data.task || data;
      toast("已派单给 " + (expert.name || "专家") + "，自动运行中");
      api("POST", "/api/nexus/tasks/" + task.id + "/run").catch((e) => toast("运行失败: " + e.message));
      pollTask(task.id, cardNode);
    } catch (e) { cardNode.querySelector(".gc-badge").textContent = "失败"; cardNode.querySelector(".gc-badge").className = "gc-badge ui-badge ui-badge--destructive"; toast(e.message); }
  }
  /* ============================ 制片流：/视频 主题 → 成片 ============================ */
  function videoCard(title, badgeText) {
    const col = el("chat-col");
    const node = document.createElement("div");
    node.className = "goal-card open";
    node.innerHTML = `<div class="gc-head"><span class="gc-badge ui-badge ui-badge--primary">${esc(badgeText)}</span>
      <span class="gc-title">${esc(title)}</span><svg class="i" style="color:var(--wb-text-3)"><use href="#ic-chevron"/></svg></div>
      <div class="gc-body"><div class="gc-steps muted">准备中…</div></div>`;
    col.appendChild(node);
    node.querySelector(".gc-head").onclick = () => node.classList.toggle("open");
    col.scrollTop = col.scrollHeight;
    return node;
  }
  function vset(card, badge, badgeCls, bodyHtml) {
    const b = card.querySelector(".gc-badge");
    b.textContent = badge;
    b.className = "gc-badge " + badgeCls;
    card.querySelector(".gc-body").innerHTML = bodyHtml;
    el("chat-col").scrollTop = el("chat-col").scrollHeight;
  }
  async function startVideoFlow(topic) {
    if (!topic) { appendAssistantText("请给出视频主题，例如：`/视频 为什么复利思维对程序员最重要`"); return; }
    const card = videoCard("🎬 " + topic, "创建项目");
    let pid = "";
    try {
      const d = await api("POST", "/api/video/projects", { topic, tone: "活泼口播", target_seconds: 30 });
      pid = (d.project || d).id;
    } catch (e) {
      vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">创建失败：${esc(e.message)}。制片需要 InsForge 存储（WORKBENCH_STORE=insforge）。</div>`);
      return;
    }
    vset(card, "生成分镜", "ui-badge ui-badge--primary", `<div class="goal-step"><span class="ck">…</span><span class="tx">AI 正在写分镜脚本（约 15-20 秒）</span></div>`);
    try { await api("POST", "/api/video/projects/" + pid + "/generate", {}); }
    catch (e) {
      vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">分镜生成失败：${esc(e.message)}</div>`);
      return;
    }
    let scenes = [];
    try {
      const d = await api("GET", "/api/video/projects/" + pid);
      scenes = (d.scenes || []).sort((a, b) => (a.scene_num || 0) - (b.scene_num || 0));
    } catch (e) { /* 忽略，空分镜也能确认 */ }
    const outline = scenes.map((s) =>
      `<div class="goal-step done"><span class="ck">${s.scene_num}</span><span class="tx">${esc(String(s.content || "").slice(0, 60))}</span></div>`).join("")
      || `<div class="muted">未取到分镜明细，可直接开拍。</div>`;
    vset(card, "待确认", "ui-badge ui-badge--secondary",
      `<div class="out-hd">分镜大纲（${scenes.length} 镜）</div>${outline}
       <div style="display:flex;gap:8px;margin-top:10px">
         <button class="ui-btn ui-btn--default ui-btn--sm" data-vid-go>✅ 确认开拍（配音+渲染约 1-2 分钟）</button>
         <button class="ui-btn ui-btn--outline ui-btn--sm" data-vid-no>取消</button>
       </div>`);
    card.querySelector("[data-vid-no]").onclick = () => vset(card, "已取消", "ui-badge ui-badge--secondary", `<div class="muted">项目 ${esc(pid.slice(0, 8))} 已保存，之后可在 /video 页继续。</div>`);
    card.querySelector("[data-vid-go]").onclick = () => confirmAndRender(card, pid, topic);
  }
  async function confirmAndRender(card, pid, topic) {
    try { await api("POST", "/api/video/projects/" + pid + "/confirm-storyboard", {}); }
    catch (e) { vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">分镜确认失败：${esc(e.message)}</div>`); return; }
    let started;
    try { started = await api("POST", "/api/video/projects/" + pid + "/render", { level: "L0" }); }
    catch (e) { vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">渲染启动失败：${esc(e.message)}</div>`); return; }
    vset(card, "渲染中", "ui-badge ui-badge--primary",
      `<div class="goal-step"><span class="ck">…</span><span class="tx" data-vid-msg>${esc(started.message || "配音与渲染中…")}</span></div>
       <div class="muted" style="margin-top:6px;font-size:12px">进度 <b data-vid-pct>0</b>% · 完成后直接在这里播放</div>`);
    const deadline = Date.now() + 6 * 60 * 1000;
    const tick = async () => {
      if (Date.now() > deadline) {
        vset(card, "仍在渲染", "ui-badge ui-badge--secondary", `<div class="muted">超过 6 分钟还没完成。项目已保存（${esc(pid.slice(0, 8))}），稍后可到 /video 页查看或重新渲染。</div>`);
        return;
      }
      let j;
      try { j = await api("GET", "/api/video/projects/" + pid + "/status"); }
      catch (e) { setTimeout(tick, 5000); return; }
      const job = j.job || {};
      const pct = card.querySelector("[data-vid-pct]");
      if (pct) pct.textContent = String(job.progress != null ? job.progress : 0);
      const msg = card.querySelector("[data-vid-msg]");
      if (msg && job.message) msg.textContent = job.message;
      if (job.status === "done") {
        vset(card, "已完成", "ui-badge ui-badge--success",
          `<video controls preload="metadata" style="width:100%;max-width:260px;border-radius:12px;margin-bottom:8px" data-pv-src="/api/video/projects/${esc(pid)}/download?inline=1"></video>
           <div style="display:flex;gap:8px;align-items:center">
             <button class="ui-btn ui-btn--default ui-btn--sm" data-vid-dl>⬇ 下载成片</button>
             <button class="ui-btn ui-btn--outline ui-btn--sm" data-vid-copy>✍️ 生成发布文案</button>
             <span class="muted" style="font-size:12px">${esc(topic)}</span>
           </div>
           <div data-vid-pack style="margin-top:8px"></div>`);
        bindPreviewVideos(card);
        card.querySelector("[data-vid-dl]").onclick = async () => {
          try {
            const res = await fetch("/api/video/projects/" + pid + "/download", { headers: { Authorization: "Bearer " + state.token } });
            if (!res.ok) throw new Error("下载失败 " + res.status);
            const blob = await res.blob();
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = (topic || "nexus视频").slice(0, 30) + ".mp4";
            a.click();
            URL.revokeObjectURL(a.href);
          } catch (e) { toast(e.message); }
        };
        card.querySelector("[data-vid-copy]").onclick = async () => {
          const box = card.querySelector("[data-vid-pack]");
          box.innerHTML = `<div class="muted" style="font-size:12px">AI 生成发布文案中…</div>`;
          try {
            const pk = await api("POST", "/api/video/projects/" + pid + "/publish-copy", {});
            box.innerHTML = `<div class="out-hd" style="margin-top:6px">发布文案（点击复制）</div>` +
              (pk.titles || []).map((t, i) => `<div class="goal-step done" style="cursor:pointer" data-pk-t="${esc(t)}"><span class="ck">${i + 1}</span><span class="tx">${esc(t)}</span></div>`).join("") +
              `<div class="goal-step done" style="cursor:pointer" data-pk-h="${esc((pk.hashtags || []).join(" "))}"><span class="ck">#</span><span class="tx">${esc((pk.hashtags || []).join(" "))}</span></div>` +
              `<div class="muted" style="font-size:12px;margin-top:4px">${esc(pk.description || "")}</div>`;
            box.querySelectorAll("[data-pk-t],[data-pk-h]").forEach((el2) => el2.onclick = () => {
              navigator.clipboard && navigator.clipboard.writeText(el2.dataset.pkT || el2.dataset.pkH || "");
              toast("已复制");
            });
            const pub = document.createElement("div");
            pub.style.marginTop = "8px";
            pub.innerHTML = `<button class="ui-btn ui-btn--default ui-btn--sm">🚀 用此文案发布到抖音</button><div data-pub-result style="margin-top:6px"></div>`;
            box.appendChild(pub);
            pub.querySelector("button").onclick = () => {
              publishDouyin(pid, pk.titles[0] || topic, pk.hashtags || [], pk.description || "", pub.querySelector("[data-pub-result]"));
            };
          } catch (e) { box.innerHTML = `<div class="muted" style="font-size:12px">生成失败：${esc(e.message)}</div>`; }
        };
        toast("🎬 成片完成");
        return;
      }
      if (job.status === "failed" || job.status === "error") {
        vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">${esc(job.message || "渲染失败")}（项目 ${esc(pid.slice(0, 8))} 已保存，可重试）</div>`);
        return;
      }
      setTimeout(tick, 4000);
    };
    setTimeout(tick, 4000);
  }
  function appendAssistantText(mdText) {
    const node = appendAssistant();
    node.querySelector(".a-text").innerHTML = md(mdText);
    bindMsgOps(node);
  }

  /* 讲解演示产线：/讲解 主题 → LLM 深度起草 → A1 确认 → 构建 → HTML slides 预览 */
  async function startPresentationFlow(topic) {
    if (!topic) { appendAssistantText("请给出讲解主题，例如：`/讲解 MCP 协议入门`"); return; }
    const card = videoCard("📊 " + topic, "创建项目");
    let pid = "";
    try {
      const d = await api("POST", "/api/video/projects", { topic, video_type: "讲解演示", target_seconds: 90 });
      pid = (d.project || d).id;
    } catch (e) {
      vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">创建失败：${esc(e.message)}</div>`);
      return;
    }
    vset(card, "AI 起草", "ui-badge ui-badge--primary", `<div class="goal-step"><span class="ck">…</span><span class="tx">AI 深度起草大纲与口播稿（约 1 分钟）</span></div>`);
    let draft;
    try { draft = await api("POST", "/api/video/projects/" + pid + "/presentation/draft", {}); }
    catch (e) {
      vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">起草失败：${esc(e.message)}</div>`);
      return;
    }
    const c = draft.content || {};
    if (!c.outline || !c.full_script) {
      vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">起草内容不完整，请重试。</div>`);
      return;
    }
    const outlineHtml = String(c.outline).split("\n").filter(Boolean).slice(0, 8).map((l) =>
      `<div class="goal-step done"><span class="ck">•</span><span class="tx">${esc(l.slice(0, 60))}</span></div>`).join("");
    vset(card, "待确认", "ui-badge ui-badge--secondary",
      `<div class="out-hd">《${esc(c.title || topic)}》大纲</div>${outlineHtml}
       <div class="muted" style="margin-top:6px;font-size:12px">口播稿 ${Math.round(String(c.full_script).length / 3)} 字 · ${esc(c.thesis || "").slice(0, 60)}</div>
       <div style="display:flex;gap:8px;margin-top:10px">
         <button class="ui-btn ui-btn--default ui-btn--sm" data-pres-go>✅ 确认，开始构建（1-3 分钟）</button>
         <button class="ui-btn ui-btn--outline ui-btn--sm" data-pres-no>取消</button>
       </div>`);
    card.querySelector("[data-pres-no]").onclick = () => vset(card, "已取消", "ui-badge ui-badge--secondary", `<div class="muted">项目 ${esc(pid.slice(0, 8))} 已保存，草稿在「制片记录」里可继续。</div>`);
    card.querySelector("[data-pres-go]").onclick = () => confirmAndBuildPres(card, pid, topic, c);
  }
  async function confirmAndBuildPres(card, pid, topic, c) {
    try {
      await api("POST", "/api/video/projects/" + pid + "/checkpoints/a1", {
        outline: c.outline, full_script: c.full_script, theme: c.theme || "talent-map", aspect: "16:9",
      });
    } catch (e) {
      vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">A1 确认失败：${esc(e.message)}</div>`);
      return;
    }
    vset(card, "构建中", "ui-badge ui-badge--primary", `<div class="goal-step"><span class="ck">…</span><span class="tx">脚手架 + npm 构建（首次 1-3 分钟，之后秒级）</span></div>`);
    let b;
    try { b = await api("POST", "/api/video/projects/" + pid + "/presentation/build", {}); }
    catch (e) {
      vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">构建失败：${esc(e.message)}（项目已保存，可重试）</div>`);
      return;
    }
    if (!b.ok) {
      vset(card, "失败", "ui-badge ui-badge--destructive", `<div class="muted">构建失败（详见服务日志），项目已保存可重试。</div>`);
      return;
    }
    const prevUrl = "/api/video/projects/" + pid + "/presentation/?token=" + encodeURIComponent(state.token);
    vset(card, "已完成", "ui-badge ui-badge--success",
      `<iframe data-pres-frame src="${esc(prevUrl)}" style="width:100%;height:260px;border:1px solid var(--wb-line,#e5e7eb);border-radius:12px;background:#0f172a"></iframe>
       <div style="display:flex;gap:8px;margin-top:8px;align-items:center">
         <button class="ui-btn ui-btn--default ui-btn--sm" data-pres-open>⧉ 全屏预览 / 录制</button>
         <span class="muted" style="font-size:12px">${esc(c.title || topic)} · ${esc(String(c.outline).split("\n").filter(Boolean).length + " 段")}</span>
       </div>
       <div class="muted" style="margin-top:4px;font-size:11px">预览 token 会过期；过期后从「制片记录」重新打开即可。</div>`);
    card.querySelector("[data-pres-open]").onclick = () => window.open(prevUrl, "_blank");
    toast("📊 讲解演示构建完成");
  }

  function appendGoalCard(title, status) {
    const col = el("chat-col");
    const node = document.createElement("div");
    node.className = "goal-card open";
    const badgeCls = status === "running" ? "ui-badge ui-badge--primary" : "ui-badge ui-badge--secondary";
    node.innerHTML = `<div class="gc-head"><span class="gc-badge ${badgeCls}">${status === "running" ? "运行中" : status}</span>
      <span class="gc-title">${esc(title)}</span><svg class="i" style="color:var(--wb-text-3)"><use href="#ic-chevron"/></svg></div>
      <div class="gc-body"><div class="gc-steps muted">等待专家反馈…</div></div>`;
    col.appendChild(node);
    node.querySelector(".gc-head").onclick = () => node.classList.toggle("open");
    col.scrollTop = col.scrollHeight;
    return node;
  }
  async function pollTask(id, cardNode) {
    let n = 0;
    const tick = async () => {
      try {
        const data = await api("GET", "/api/nexus/tasks/" + id);
        const task = data.task || data;
        const badge = cardNode.querySelector(".gc-badge");
        const body = cardNode.querySelector(".gc-body");
        badge.textContent = statusLabel(task.status);
        badge.className = "gc-badge " + (task.status === "done" || task.status === "approved" ? "ui-badge ui-badge--success"
          : task.status === "failed" || task.status === "rejected" ? "ui-badge ui-badge--destructive" : "ui-badge ui-badge--primary");
        const steps = (task.steps || []).map((s) =>
          `<div class="goal-step done"><span class="ck">✓</span><span class="tx">${esc(s.message || s.kind || "")}</span></div>`).join("");
        const arts = (task.artifacts || []);
        state._artifacts = state._artifacts || {};
        arts.forEach((a) => { state._artifacts[a.id] = a; });
        const artsHtml = arts.map((a) =>
          `<div class="out-row" data-art-id="${esc(a.id)}"><span class="nm">${esc(a.name || a.kind)}</span><span class="sz">${a.size ? Math.round(a.size / 102.4) / 10 + "KB" : ""}</span><span class="dl">打开</span><span class="dl" data-art-copy="${esc(a.id)}" title="复制全文">复制</span></div>`).join("");
        body.innerHTML = (steps || "") + (artsHtml ? `<div class="out-hd" style="margin-top:8px">本次产出 <span class="dl" data-export="${esc(id)}" style="cursor:pointer;color:var(--wb-brand)">⬇ 导出到文件</span></div>${artsHtml}` : "");
        body.querySelectorAll("[data-art-id]").forEach((r) => r.onclick = (ev) => {
          const a = (state._artifacts || {})[r.dataset.artId];
          if (!a) return;
          if (ev.target.dataset && ev.target.dataset.artCopy) {
            navigator.clipboard && navigator.clipboard.writeText(a.content || "");
            toast("已复制全文");
            return;
          }
          openArtifactContent(a.name || a.kind, a.kind, a.content || "");
        });
        const ex = body.querySelector("[data-export]");
        if (ex) ex.onclick = () => exportTask(ex.dataset.export);
        if (task.status === "reviewing" && !cardNode.dataset.reviewed) {
          cardNode.dataset.reviewed = "1";
          // Goal 模式自动验收：先验收员核对（/review），再裁决通过（/decide approve）
          api("POST", "/api/nexus/tasks/" + id + "/review")
            .catch(() => {})
            .then(() => api("POST", "/api/nexus/tasks/" + id + "/decide", { decision: "approve" }))
            .catch(() => {});
        }
        col_scroll();
        if (["approved", "done", "failed", "rejected"].includes(task.status)) return;
        if (n++ < 40) setTimeout(tick, 2500);
      } catch (e) { if (n++ < 6) setTimeout(tick, 3000); }
    };
    tick();
  }
  function openArtifactContent(name, kind, content) {
    togglePreview(true);
    el("pv-name").textContent = name || kind || "成果";
    el("pv-deploy").hidden = true;
    if (/\.html?$/i.test(name || "") || kind === "html") {
      el("pv-body").innerHTML = `<iframe srcdoc="${esc(content)}"></iframe>`;
    } else if (kind === "markdown" || /\.(md|markdown|txt)$/i.test(name || "")) {
      el("pv-body").innerHTML = `<div class="pv-list"><div class="a-text">${md(content)}</div></div>`;
    } else {
      el("pv-body").innerHTML = `<div class="pv-list"><pre style="white-space:pre-wrap;font-size:13px">${esc(content)}</pre></div>`;
    }
  }
  function col_scroll() { const c = el("chat-col"); if (c) c.scrollTop = c.scrollHeight; }
  function statusLabel(s) {
    return ({ draft: "草稿", running: "运行中", reviewing: "验收中", done: "已完成", approved: "已通过", rejected: "已驳回", failed: "失败", archived: "已归档" }[s] || s);
  }

  /* ============================ 附件 ============================ */
  function clearAttachment() {
    state.pendingAttachment = null;
    const c = el("attach-chips"); c.hidden = true; c.innerHTML = "";
  }
  async function handleFile(file) {
    if (!file) return;
    if (file.size > 200 * 1024) { toast("文件过大（>200KB），仅支持文本类附件"); return; }
    const content = await file.text();
    state.pendingAttachment = { name: file.name, content };
    const c = el("attach-chips");
    c.hidden = false;
    c.innerHTML = `<span>${esc(file.name)} <b id="attach-x">✕</b></span>`;
    el("attach-x").onclick = clearAttachment;
  }

  /* ============================ picker（模式/模型/权限） ============================ */
  function setupPickers() {
    document.querySelectorAll(".picker").forEach((p) => {
      const btn = p.querySelector(".picker-btn");
      const menu = p.querySelector(".picker-menu");
      btn.onclick = (e) => { e.stopPropagation(); document.querySelectorAll(".picker-menu").forEach((m) => { if (m !== menu) m.classList.remove("show"); }); menu.classList.toggle("show"); };
    });
    document.addEventListener("click", () => document.querySelectorAll(".picker-menu").forEach((m) => m.classList.remove("show")));

    el("mode-menu").querySelectorAll(".mi").forEach((mi) => {
      mi.onclick = () => {
        state.chatMode = mi.dataset.mode; localStorage.setItem("nexus_mode", state.chatMode);
        el("mode-menu").querySelectorAll(".mi").forEach((x) => x.classList.toggle("on", x === mi));
        el("mode-label").textContent = { ask: "问答", plan: "规划", goal: "目标", craft: "执行" }[state.chatMode];
        el("mode-menu").classList.remove("show");
      };
    });
    el("perm-menu").querySelectorAll(".mi").forEach((mi) => {
      mi.onclick = () => {
        state.perm = mi.dataset.perm; localStorage.setItem("nexus_perm", state.perm);
        el("perm-menu").querySelectorAll(".mi").forEach((x) => x.classList.toggle("on", x === mi));
        el("perm-label").textContent = { ask: "每步都问", auto: "自动", full: "全自动" }[state.perm];
        el("perm-menu").classList.remove("show");
      };
    });
    el("model-menu").addEventListener("click", (e) => {
      const mi = e.target.closest(".mi"); if (!mi) return;
      const m = mi.dataset.model;
      state.model = m;
      if (mi.dataset.provider) state.llmProvider = mi.dataset.provider;
      localStorage.setItem("nexus_model", m || "");
      el("model-label").textContent = m || "默认模型";
      el("model-menu").querySelectorAll(".mi").forEach((x) => x.classList.toggle("on", x === mi));
      el("model-menu").classList.remove("show");
      updateModelLabel();
      // 热切换：全局默认模型立即生效并持久化
      if (m) api("POST", "/api/settings/llm", { mode: mi.dataset.provider || state.llmProvider || "agnes", model: m }).catch(() => {});
      if (state.currentSessionId) api("PATCH", "/api/sessions/" + state.currentSessionId, { model: m }).catch(() => {});
    });
  }
  function updateModelLabel() {
    el("model-label").textContent = state.model
      ? state.model
      : (state.defaultModel ? "默认 · " + state.defaultModel : "默认模型");
    const mb = el("topbar-model"); if (mb) mb.textContent = state.model ? state.model : "";
  }
  async function loadModelMenu() {
    let d = null;
    try { d = await api("GET", "/api/settings/llm"); } catch (e) {}
    // 统一形状：models 可能是字符串数组或对象数组；provider 显示名 label 优先
    const normModels = (prov) => (prov.models || []).map((m) =>
      typeof m === "string" ? { id: m, name: m } : { id: m.id, name: m.name || m.id });
    const provs = (d && d.providers || []).map((p) => ({ ...p, name: p.label || p.name || p.id, _models: normModels(p) }));
    if (d && d.model && !state.model) { state.defaultModel = d.model; updateModelLabel(); }
    const menu = el("model-menu");
    let html = `<div class="mh">默认模型</div><div class="mi ${!state.model ? "on" : ""}" data-model=""><svg class="i"><use href="#ic-cpu"/></svg> 跟随默认</div>`;
    provs.forEach((prov) => {
      html += `<div class="mh">${esc(prov.name)}${prov.configured === false ? "（未配置）" : ""}</div>`;
      prov._models.forEach((m) => {
        html += `<div class="mi ${state.model === m.id ? "on" : ""}" data-model="${esc(m.id)}" data-provider="${esc(prov.id)}">${esc(m.name)}</div>`;
      });
    });
    menu.innerHTML = html;
    // 设置页 provider/model 下拉
    const provSel = el("model-provider"); const nameSel = el("model-name");
    if (provSel && nameSel) {
      provSel.innerHTML = provs.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}${p.configured === false ? "（未配置）" : ""}</option>`).join("");
      const fillModels = (pid) => {
        const p = provs.find((x) => x.id === pid);
        nameSel.innerHTML = (p ? p._models : []).map((m) => `<option value="${esc(m.id)}">${esc(m.name)}</option>`).join("");
      };
      const curProv = (d && (d.mode || d.provider)) || provs[0] && provs[0].id || "";
      provSel.value = curProv;
      fillModels(curProv);
      const curModel = (d && d.model) || state.model || "";
      if (curModel) nameSel.value = curModel;
      provSel.onchange = () => fillModels(provSel.value);
    }
  }

  /* ============================ 侧栏导航 ============================ */
  function setSideView(v) {
    state.sideView = v;
    el("chat-view").classList.toggle("hidden", v !== "chat");
    ["plaza", "auto", "library", "settings", "tasks", "hotspots", "videos"].forEach((x) => {
      const view = el(x + "-view");
      if (view) view.classList.toggle("hidden", x !== v);
    });
    document.querySelectorAll(".side-nav .item").forEach((it) => it.classList.toggle("active", it.dataset.nav === v));
    if (v === "plaza") loadPlaza("experts");
    if (v === "auto") loadAutomations();
    if (v === "settings") loadSettings();
    if (v === "library") loadLibrary();
    if (v === "tasks") loadTaskHistory();
    if (v === "hotspots") loadHotspots();
    if (v === "videos") loadVideos();
  }

  /* ============================ 热点看板 / 制片记录 ============================ */
  async function loadHotspots() {
    const list = el("hotspot-list");
    try {
      const d = await api("GET", "/api/hotspots");
      const board = d.board || [];
      if (!board.length) { list.innerHTML = `<div class="muted">暂无热点。到广场→连接器开启热点看板的来源后重试。</div>`; return; }
      list.innerHTML = board.map((h, i) => `
        <div class="auto-row">
          <div class="ar-ava" style="font-weight:500">${esc(String(h.rank || i + 1))}</div>
          <div class="ar-main"><div class="ar-title">${esc(h.full_name || h.title || "未命名")}</div>
            <div class="ar-sub">${esc(h.source_label || h.source || "")}${h.description ? " · " + esc(String(h.description).slice(0, 60)) : ""}</div></div>
          <button class="ui-btn ui-btn--outline ui-btn--sm" data-hot-angle="${i}">💡 选题</button>
          <button class="ui-btn ui-btn--default ui-btn--sm" data-hot-vid="${i}">🎬 转视频</button>
        </div>`).join("");
      list.querySelectorAll("[data-hot-vid]").forEach((b) => b.onclick = () => {
        const h = board[Number(b.dataset.hotVid)];
        setSideView("chat");
        startVideoFlow(h.full_name || h.title || h.url || "热点话题");
      });
      list.querySelectorAll("[data-hot-angle]").forEach((b) => b.onclick = async () => {
        const h = board[Number(b.dataset.hotAngle)];
        b.textContent = "…";
        try {
          const d = await api("POST", "/api/hotspots/angles", { title: h.full_name || h.title, description: h.description || "", source: h.source_label || h.source || "" });
          const row = b.closest(".auto-row");
          const box = row.nextElementSibling && row.nextElementSibling.classList.contains("hot-angles") ? row.nextElementSibling : null;
          if (box) box.remove();
          const div = document.createElement("div");
          div.className = "hot-angles";
          div.style.cssText = "grid-column:1/-1;padding:8px 14px;border-left:2px solid var(--wb-brand);margin:2px 0 6px 24px";
          div.innerHTML = (d.angles || []).map((a) => `
            <div style="font-size:13px;margin-bottom:6px"><b>${esc(a.title || "")}</b><br>
              <span class="muted" style="font-size:12px">${esc(a.angle || "")} · ${esc(a.why || "")}</span>
              <button class="ui-btn ui-btn--outline ui-btn--sm" style="margin-left:8px" data-angle-vid="${esc(a.title || "")}">🎬 按此角度转视频</button></div>`).join("");
          row.parentElement.insertBefore(div, row.nextSibling);
          div.querySelectorAll("[data-angle-vid]").forEach((btn) => btn.onclick = () => {
            setSideView("chat");
            startVideoFlow(btn.dataset.angleVid);
          });
          b.textContent = "💡 选题";
        } catch (e) { toast(e.message); b.textContent = "💡 选题"; }
      });
    } catch (e) { list.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`; }
  }
  function videoStatusBadge(st) {
    const map = { draft: ["草稿", "ui-badge--secondary"], rendering: ["渲染中", "ui-badge--primary"], done: ["已完成", "ui-badge--success"], failed: ["失败", "ui-badge--destructive"] };
    const m = map[st] || [st || "未知", "ui-badge--secondary"];
    return `<span class="gc-badge ui-badge ${m[1]}">${esc(m[0])}</span>`;
  }
  async function loadVideos() {
    const list = el("video-list");
    try {
      const d = await api("GET", "/api/video/projects");
      const rows = (d.projects || []).slice(0, 30);
      if (!rows.length) { list.innerHTML = `<div class="muted">还没有视频项目。对话里输入「/视频 主题」即可制片。</div>`; return; }
      list.innerHTML = rows.map((p) => `
        <div class="auto-row" data-vid-open="${esc(p.id)}" style="cursor:pointer">
          <div class="ar-ava"><svg class="i"><use href="#ic-play"/></svg></div>
          <div class="ar-main"><div class="ar-title">${esc(p.title || p.topic || "未命名")}</div>
            <div class="ar-sub">${esc((p.updated_at || p.created_at || "").slice(0, 16).replace("T", " "))} · ${esc(p.video_type || "口播")}</div></div>
          ${videoStatusBadge(p.status)}
        </div>`).join("");
      list.querySelectorAll("[data-vid-open]").forEach((row) => row.onclick = async () => {
        try {
          const pid = row.dataset.vidOpen;
          const pj = await api("GET", "/api/video/projects/" + pid);
          const p = pj.project || {};
          const done = p.status === "done" && (p.output_path || pj.delivery?.render_mode);
          const scenes = (pj.scenes || []).sort((a, b) => (a.scene_num || 0) - (b.scene_num || 0));
          // 已就绪的逐镜素材（后端未重启时该接口还不存在 → 退化为空，全部显示"渲染中"）
          let readyFiles = [];
          try {
            const sf = await api("GET", "/api/video/projects/" + pid + "/scenes");
            readyFiles = sf.files || [];
          } catch (e) { readyFiles = []; }
          // 讲解演示项目（wbmeta.video_type=presentation）：给预览/打开按钮而非 mp4
          const wb = /<!--wbmeta:(\{[\s\S]*?\})-->/.exec(p.script || "");
          let isPres = false;
          if (wb) { try { isPres = (JSON.parse(wb[1]).video_type) === "presentation"; } catch (e) { /* ignore */ } }
          const outline = scenes.map((s) =>
            `<div class="goal-step done"><span class="ck">${s.scene_num}</span><span class="tx">${esc(String(s.content || "").slice(0, 60))}</span></div>`).join("");
          togglePreview(true);
          el("pv-name").textContent = p.title || p.topic || "视频项目";
          el("pv-deploy").hidden = true;
          const presUrl = "/api/video/projects/" + esc(pid) + "/presentation/?token=" + encodeURIComponent(state.token);
          el("pv-body").innerHTML = `<div class="pv-list">
            <div style="margin-bottom:8px">${videoStatusBadge(p.status)} <span class="muted" style="font-size:12px;margin-left:6px">${esc((p.updated_at || "").slice(0, 16).replace("T", " "))} · ${isPres ? "讲解演示" : "口播"}</span></div>
            ${p.status === "done" && !isPres ? `<video controls preload="metadata" style="width:100%;max-width:280px;border-radius:12px;margin-bottom:10px" data-pv-src="/api/video/projects/${esc(pid)}/download?inline=1"></video>` : ""}
            ${p.status === "done" && !isPres ? `<div style="margin-bottom:10px;display:flex;gap:8px"><button class="ui-btn ui-btn--default ui-btn--sm" data-pv-dl="${esc(pid)}" data-pv-title="${esc(p.title || "nexus视频")}">⬇ 下载成片</button><button class="ui-btn ui-btn--outline ui-btn--sm" data-pv-pub="${esc(pid)}" data-pv-topic="${esc(p.title || p.topic || "")}">🚀 发布到抖音</button></div><div data-pv-pub-result style="margin-bottom:10px"></div>` : ""}
            ${isPres ? `<iframe src="${esc(presUrl)}" style="width:100%;height:240px;border:1px solid var(--wb-line,#e5e7eb);border-radius:12px;background:#0f172a;margin-bottom:10px"></iframe>
            <div style="margin-bottom:10px"><a class="primary" href="${esc(presUrl)}" target="_blank" style="color:var(--wb-brand);font-size:13px;text-decoration:none">⧉ 新窗口全屏打开</a></div>` : ""}
            <div class="out-hd">${isPres ? "大纲" : "分镜（" + scenes.length + " 镜）"}</div>${outline || '<div class="muted">未生成</div>'}
            ${isPres ? "" : perSceneGrid(pid, scenes, readyFiles)}
          </div>`;
          bindPreviewVideos(el("pv-body"));
          const dl = el("pv-body").querySelector("[data-pv-dl]");
          if (dl) dl.onclick = async () => {
            try {
              const res = await fetch("/api/video/projects/" + dl.dataset.pvDl + "/download", { headers: { Authorization: "Bearer " + state.token } });
              if (!res.ok) throw new Error("下载失败 " + res.status);
              const blob = await res.blob();
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = dl.dataset.pvTitle.slice(0, 30) + ".mp4";
              a.click();
              URL.revokeObjectURL(a.href);
            } catch (e) { toast(e.message); }
          };
          const pub = el("pv-body").querySelector("[data-pv-pub]");
          if (pub) pub.onclick = async () => {
            const box = el("pv-body").querySelector("[data-pv-pub-result]");
            box.innerHTML = `<div class="muted" style="font-size:12px">生成发布文案中…</div>`;
            try {
              let copy = {};
              try { copy = await api("POST", "/api/video/projects/" + pub.dataset.pvPub + "/publish-copy", {}); } catch (e) { /* 文案失败不影响发布 */ }
              publishDouyin(pub.dataset.pvPub, (copy.titles && copy.titles[0]) || pub.dataset.pvTopic, copy.hashtags || [], copy.description || "", box);
            } catch (e) { box.innerHTML = `<div class="muted" style="font-size:12px">${esc(e.message)}</div>`; }
          };
        } catch (e) { toast(e.message); }
      });
    } catch (e) { list.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`; }
  }

  /* ============================ 任务历史 ============================ */
  async function exportTask(taskId) {
    try {
      toast("正在导出到文件…");
      const d = await api("POST", "/api/nexus/tasks/" + taskId + "/export", {});
      const files = d.files || [];
      if (!files.length) { toast("没有可导出的产物"); return; }
      for (const f of files) {
        try {
          const res = await fetch(d.urls?.[files.indexOf(f)] || "/api/exports/" + f.path, {
            headers: { Authorization: "Bearer " + state.token },
          });
          if (!res.ok) throw new Error("下载失败 " + res.status);
          const blob = await res.blob();
          const a = document.createElement("a");
          a.href = URL.createObjectURL(blob);
          a.download = f.name;
          a.click();
          URL.revokeObjectURL(a.href);
        } catch (e) { toast(f.name + ": " + e.message); }
      }
      toast("已导出 " + files.length + " 个文件（同时落盘 " + (d.dir || "").split("/").slice(-1)[0] + "）");
    } catch (e) { toast("导出失败: " + e.message); }
  }

  async function loadTaskHistory() {
    try {
      const d = await api("GET", "/api/nexus/tasks");
      const tasks = (d && d.tasks) || [];
      const list = el("task-history-list");
      if (!tasks.length) { list.innerHTML = `<div class="muted">还没有任务。对话里切「目标」模式，或到广场给专家派单。</div>`; return; }
      list.innerHTML = tasks.map((tk) => `
        <div class="auto-row" data-task="${esc(tk.id)}" style="cursor:pointer">
          <div class="ar-ava"><svg class="i"><use href="#ic-flag"/></svg></div>
          <div class="ar-main"><div class="ar-title">${esc(tk.title)}</div>
            <div class="ar-sub">${esc((tk.updated_at || "").slice(0, 16).replace("T", " "))}</div></div>
          <span class="gc-badge ${tk.status === "approved" || tk.status === "done" ? "ui-badge ui-badge--success" : tk.status === "failed" || tk.status === "rejected" ? "ui-badge ui-badge--destructive" : "ui-badge ui-badge--primary"}">${statusLabel(tk.status)}</span>
        </div>`).join("");
      list.querySelectorAll("[data-task]").forEach((row) => row.onclick = async () => {
        try {
          const r = await api("GET", "/api/nexus/tasks/" + row.dataset.task);
          const tk = (r && r.task) || r;
          state._artifacts = state._artifacts || {};
          (tk.artifacts || []).forEach((a) => { state._artifacts[a.id] = a; });
          const stepsHtml = (tk.steps || []).slice(-6).map((s) => `<div class="goal-step done"><span class="ck">✓</span><span class="tx">${esc(s.message || s.kind || "")}</span></div>`).join("");
          const artsHtml = (tk.artifacts || []).map((a) => `<div class="out-row" data-art-id="${esc(a.id)}"><span class="nm">${esc(a.name || a.kind)}</span><span class="dl">打开</span></div>`).join("");
          togglePreview(true);
          el("pv-name").textContent = tk.title || "任务详情";
          el("pv-deploy").hidden = true;
          el("pv-body").innerHTML = `<div class="pv-list">
            <div style="margin-bottom:8px;display:flex;gap:10px;align-items:center"><span class="gc-badge ui-badge ui-badge--primary">${statusLabel(tk.status)}</span>
            ${(tk.artifacts || []).length ? `<span class="dl" data-task-export="${esc(tk.id)}" style="cursor:pointer;color:var(--wb-brand);font-size:13px">⬇ 导出到文件</span>` : ""}</div>
            <div class="out-hd">执行轨迹（最近 6 步）</div>${stepsHtml || '<div class="muted">无</div>'}
            <div class="out-hd" style="margin-top:10px">产物</div>${artsHtml || '<div class="muted">无</div>'}</div>`;
          const tex = el("pv-body").querySelector("[data-task-export]");
          if (tex) tex.onclick = () => exportTask(tex.dataset.taskExport);
          el("pv-body").querySelectorAll("[data-art-id]").forEach((art) => art.onclick = () => {
            const a = (state._artifacts || {})[art.dataset.artId];
            if (a) openArtifactContent(a.name || a.kind, a.kind, a.content || "");
          });
        } catch (e) { toast(e.message); }
      });
    } catch (e) { el("task-history-list").innerHTML = `<div class="muted">${esc(e.message)}</div>`; }
  }

  /* ============================ 产物导出（落盘 + 下载） ============================ */
  async function exportTask(id) {
    try {
      const d = await api("POST", "/api/nexus/tasks/" + id + "/export");
      const files = (d && d.files) || [];
      if (!files.length) { toast("没有可导出的产物"); return; }
      for (const f of files) {
        const res = await fetch("/api/exports/" + f.path, { headers: { Authorization: "Bearer " + state.token } });
        if (!res.ok) { toast("下载失败 (" + res.status + ")"); continue; }
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = f.name;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      }
      toast(`已导出 ${files.length} 个文件到磁盘（${(d.dir || "").split("/").pop()}）并触发下载`);
    } catch (e) { toast(e.message); }
  }

  /* ============================ 模板库 ============================ */
  const TEMPLATES = [
    { name: "周报生成", desc: "把本周做的事整理成一份结构化周报", text: "把以下工作记录整理成一份周报，分「本周成果 / 数据亮点 / 下周计划」三段，成果每条带一句价值说明：\n（粘贴你的工作记录）" },
    { name: "朋友圈文案", desc: "生活化、不 AI 腔的产品安利", text: "为（产品名）写一条朋友圈文案：生活化场景开头，不要 AI 腔（禁用「赋能/洞察/优化体验」），结尾带行动号召，80 字内。" },
    { name: "小红书种草", desc: "带 emoji 排版的种草笔记", text: "为（产品名）写一篇小红书种草笔记：标题带 emoji，正文 200 字内分 3 小段（痛点/体验/推荐理由），结尾带 5 个话题标签。" },
    { name: "竞品调研", desc: "出一份结构化竞品分析", text: "调研（行业/品类）的主要竞品：列 3-5 个产品，从「定位/核心功能/定价/短板」四维对比，最后给出我们产品的差异化机会，输出 markdown 报告。" },
    { name: "PPT 大纲", desc: "十分钟汇报的演示大纲", text: "为（主题）设计一份 10 页 PPT 大纲：每页给出标题 + 3 条要点 + 一句备注（数据需求或配图建议），按「背景→问题→方案→收益→计划」推进。" },
    { name: "会议纪要", desc: "把录音/记录整理成纪要", text: "把以下会议记录整理成纪要：「结论先行 → 决议事项（负责人+截止）→ 待办清单 → 遗留问题」，原文语意不要增删：\n（粘贴记录）" },
    { name: "知乎回答", desc: "先说结论的知乎体", text: "以知乎高赞风格回答：（问题）。要求：第一句先给结论，然后用 2-3 个论据展开（有数据/案例更好），结尾一句话收束，全文 500 字内。" },
    { name: "公众号推文", desc: "公众号图文的正文初稿", text: "为（主题/产品）写一篇公众号推文正文：标题党但不夸大的标题 + 导语 50 字 + 正文三段式（故事引入/干货主体/行动引导）+ 摘要，全文 800 字左右。" },
    { name: "招聘 JD", desc: "岗位描述一键成稿", text: "为（公司）写（岗位）的招聘 JD：一段吸引人的岗位使命 + 5 条职责 + 5 条任职要求（区分必须/加分）+ 一句团队亮点，语气真诚不堆砌。" },
    { name: "复盘模板", desc: "项目复盘四步法", text: "对（项目/事件）做复盘，按四步输出：「目标回顾（当初要什么）→ 结果对比（拿到什么）→ 原因分析（做对/做错各 2 条）→ 经验沉淀（可复用的动作）」。" },
  ];
  function allTemplates() {
    const custom = (state.customTemplates || []).map((t) => ({ name: t.title, desc: t.desc || "自定义模板", text: t.prompt, custom: true, id: t.id }));
    return [...custom, ...TEMPLATES.map((tp) => ({ ...tp, custom: false }))];
  }
  async function saveCustomTemplates() {
    try {
      const d = await api("PATCH", "/api/settings/prefs", { custom_templates: state.customTemplates || [] });
      state.customTemplates = (d.prefs && d.prefs.custom_templates) || [];
    } catch (e) { toast("保存模板失败: " + e.message); }
  }
  function templateActions(grid) {
    grid.querySelectorAll("[data-tpl]").forEach((b) => b.onclick = () => {
      const tp = allTemplates()[Number(b.dataset.tpl)];
      setSideView("chat");
      el("input").value = tp.text;
      autoGrow(el("input"));
      el("input").focus();
      toast("模板已填入，替换括号内容即可发送");
    });
    grid.querySelectorAll("[data-tpl-del]").forEach((b) => b.onclick = async () => {
      const id = b.dataset.tplDel;
      state.customTemplates = (state.customTemplates || []).filter((t) => t.id !== id);
      await saveCustomTemplates();
      loadTemplates();
      toast("模板已删除");
    });
    const nb = grid.querySelector("[data-tpl-new]");
    if (nb) nb.onclick = () => {
      const form = grid.querySelector("#tpl-form");
      form.hidden = !form.hidden;
      if (!form.hidden) form.querySelector("#tpl-f-title").focus();
    };
    const sb = grid.querySelector("[data-tpl-save]");
    if (sb) sb.onclick = async () => {
      const form = grid.querySelector("#tpl-form");
      const title = form.querySelector("#tpl-f-title").value.trim();
      const prompt = form.querySelector("#tpl-f-prompt").value.trim();
      if (!title || !prompt) { toast("标题和提示词必填"); return; }
      state.customTemplates = [...(state.customTemplates || []), {
        id: "tpl_" + Date.now().toString(36),
        title, desc: form.querySelector("#tpl-f-desc").value.trim(), prompt,
      }];
      await saveCustomTemplates();
      loadTemplates();
      toast("自定义模板已保存，随时可用");
    };
    const cb = grid.querySelector("[data-tpl-cancel]");
    if (cb) cb.onclick = () => { grid.querySelector("#tpl-form").hidden = true; };
  }
  function loadTemplates() {
    const grid = el("plaza-grid");
    const tps = allTemplates();
    grid.innerHTML = `
      <div style="grid-column:1/-1;display:flex;gap:8px;align-items:center;margin-bottom:2px">
        <button class="ui-btn ui-btn--default ui-btn--sm" data-tpl-new>＋ 新建模板</button>
        <span class="muted" style="font-size:12px">把你的常用提示词沉淀成模板，随时可用；输入框敲 <b>/</b> 也能快速唤起</span>
      </div>
      <div id="tpl-form" hidden style="grid-column:1/-1;border:1px solid var(--wb-line,#e5e7eb);border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:8px;margin-bottom:6px">
        <input id="tpl-f-title" class="ui-input" placeholder="模板标题（如：周报生成）" />
        <input id="tpl-f-desc" class="ui-input" placeholder="一句话描述（可选）" />
        <textarea id="tpl-f-prompt" class="ui-input" rows="4" placeholder="提示词内容，用【括号】标注可替换部分" style="resize:vertical"></textarea>
        <div style="display:flex;gap:8px">
          <button class="ui-btn ui-btn--default ui-btn--sm" data-tpl-save>保存</button>
          <button class="ui-btn ui-btn--outline ui-btn--sm" data-tpl-cancel>取消</button>
        </div>
      </div>` +
      tps.map((tp, i) => `
      <div class="pcard"><div class="pc-top"><div class="pc-ava"><svg class="i"><use href="#ic-edit"/></svg></div>
        <div><div class="pc-title">${esc(tp.name)}</div><div class="pc-sub">${tp.custom ? "我的模板" : "提示词模板"}</div></div></div>
        <div class="pc-desc">${esc(tp.desc)}<br><span class="muted" style="font-size:12px">${esc(tp.text.slice(0, 56))}…</span></div>
        <div class="pc-actions"><button class="ui-btn ui-btn--default ui-btn--sm" data-tpl="${i}">用这个</button>${tp.custom ? `<button class="ui-btn ui-btn--outline ui-btn--sm" data-tpl-del="${esc(tp.id)}">删除</button>` : ""}</div></div>`).join("");
    templateActions(grid);
  }
  /* `/` 快捷指令：输入框以 / 开头时弹出模板浮层 */
  function setupSlashMenu() {
    const input = el("input");
    let box = el("slash-menu");
    if (!box) {
      box = document.createElement("div");
      box.id = "slash-menu";
      box.style.cssText = "position:absolute;bottom:100%;left:0;right:0;margin-bottom:6px;background:var(--wb-card,#fff);border:1px solid var(--wb-line,#e5e7eb);border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.14);max-height:260px;overflow:auto;display:none;z-index:30";
      input.parentElement.style.position = "relative";
      input.parentElement.appendChild(box);
    }
    const render = () => {
      const tps = allTemplates();
      box.innerHTML = `
        <div class="mi" data-slash-video style="padding:8px 12px;cursor:pointer;font-size:13px;background:var(--wb-brand-weak,#f4f2ff)">
          <b>🎬 口播视频制片</b><br>
          <span class="muted" style="font-size:11px">输入「/视频 + 主题」→ AI 分镜 → 确认 → 自动配音渲染出竖屏成片</span>
        </div>
        <div class="mi" data-slash-pres style="padding:8px 12px;cursor:pointer;font-size:13px;background:var(--wb-brand-weak,#f4f2ff)">
          <b>📊 讲解演示制片</b><br>
          <span class="muted" style="font-size:11px">输入「/讲解 + 主题」→ AI 起草大纲口播稿 → 确认 → 构建横屏 HTML slides</span>
        </div>` +
        tps.map((tp, i) => `
        <div class="mi" data-slash="${i}" style="padding:8px 12px;cursor:pointer;font-size:13px">
          <b>${esc(tp.name)}</b>${tp.custom ? ' <span class="ui-badge ui-badge--secondary" style="font-size:10px">我的</span>' : ""}<br>
          <span class="muted" style="font-size:11px">${esc(tp.text.slice(0, 48))}…</span>
        </div>`).join("");
      const sv = box.querySelector("[data-slash-video]");
      if (sv) sv.onclick = () => {
        box.style.display = "none";
        input.value = "/视频 ";
        autoGrow(input); input.focus();
        toast("输入主题后直接发送，例如：/视频 为什么复利思维重要");
      };
      const sp = box.querySelector("[data-slash-pres]");
      if (sp) sp.onclick = () => {
        box.style.display = "none";
        input.value = "/讲解 ";
        autoGrow(input); input.focus();
        toast("输入主题后直接发送，例如：/讲解 MCP 协议入门");
      };
      box.querySelectorAll("[data-slash]").forEach((mi) => mi.onclick = () => {
        input.value = allTemplates()[Number(mi.dataset.slash)].text;
        box.style.display = "none";
        autoGrow(input); input.focus();
      });
    };
    input.addEventListener("input", () => {
      const show = input.value === "/";
      if (show) render();
      box.style.display = show ? "block" : "none";
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") box.style.display = "none";
    });
    document.addEventListener("click", (e) => {
      if (!box.contains(e.target) && e.target !== input) box.style.display = "none";
    });
  }

  /* ============================ 广场 ============================ */
  async function loadExperts() {
    const d = await api("GET", "/api/nexus/experts");
    state.experts = d.experts || d || [];
  }
  async function loadSkills() { const d = await api("GET", "/api/skills"); state.skills = d.skills || d || []; }
  async function loadConnectors() { const d = await api("GET", "/api/connectors"); state.connectors = d.connectors || d || []; }
  async function loadPlaza(tab) {
    document.querySelectorAll("#plaza-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    if (tab === "templates") { loadTemplates(); return; }
    const grid = el("plaza-grid"); grid.innerHTML = `<div class="muted">加载中…</div>`;
    try {
      if (tab === "experts") {
        if (!state.experts.length) await loadExperts();
        grid.innerHTML = state.experts.map((e) => `
          <div class="pcard">
            <div class="pc-top"><div class="pc-ava">${esc((e.avatar || e.name || "E").slice(0, 1))}</div>
              <div><div class="pc-title">${esc(e.name)}</div><div class="pc-sub">${esc(e.title || "")}</div></div></div>
            <div class="pc-desc">${esc(e.desc || "")}</div>
            <div class="pc-actions"><button class="ui-btn ui-btn--default ui-btn--sm" data-dispatch="${esc(e.id)}">派单</button></div>
          </div>`).join("") || `<div class="muted">暂无专家</div>`;
        grid.querySelectorAll("[data-dispatch]").forEach((b) => b.onclick = () => openDispatch(b.dataset.dispatch));
      } else if (tab === "skills") {
        if (!state.skills.length) await loadSkills();
        grid.innerHTML = state.skills.map((s) => `
          <div class="pcard"><div class="pc-top"><div class="pc-ava"><svg class="i"><use href="#ic-book"/></svg></div>
            <div><div class="pc-title">${esc(s.name)}</div><div class="pc-sub">技能 · ${s.enabled ? "已启用" : "已停用"}</div></div></div>
            <div class="pc-desc">${esc(s.description || s.desc || "")}</div>
            <div class="pc-actions"><div class="switch ${s.enabled ? "on" : ""}" data-skill="${esc(s.id)}"></div></div></div>`).join("") || `<div class="muted">暂无技能</div>`;
        grid.querySelectorAll("[data-skill]").forEach((sw) => sw.onclick = async () => {
          const id = sw.dataset.skill; const on = !sw.classList.contains("on");
          sw.classList.toggle("on", on);
          try {
            await api("PATCH", "/api/skills/" + id, { enabled: on });
            const s = state.skills.find((x) => x.id === id); if (s) s.enabled = on;
            toast(on ? "技能已启用，下一条任务即生效" : "技能已停用");
          } catch (e) { toast(e.message); sw.classList.toggle("on", !on); }
        });
      } else {
        if (!state.connectors.length) await loadConnectors();
        grid.innerHTML = state.connectors.map((c) => `
          <div class="pcard"><div class="pc-top"><div class="pc-ava"><svg class="i"><use href="#ic-plug"/></svg></div>
            <div><div class="pc-title">${esc(c.label || c.name)}</div><div class="pc-sub">${esc(c.direction === "ingest" ? "数据接入" : c.direction || "连接器")} · ${esc(c.status_label || c.status || "")}</div></div></div>
            <div class="pc-desc">${esc(c.description || c.desc || "")}</div>
            <div class="pc-tags">${(c.children || []).map((ch) => `<span class="ui-badge ${ch.enabled ? "ui-badge--success" : "ui-badge--outline"}">${esc(ch.label)}</span>`).join("")}</div>
            <div class="pc-actions"><div class="switch ${c.enabled ? "on" : ""}" data-connector="${esc(c.id)}"></div></div></div>`).join("") || `<div class="muted">暂无连接器</div>`;
        grid.querySelectorAll("[data-connector]").forEach((sw) => sw.onclick = async () => {
          const id = sw.dataset.connector; const on = !sw.classList.contains("on");
          sw.classList.toggle("on", on);
          try {
            const d = await api("PATCH", "/api/connectors", { id, enabled: on });
            state.connectors = (d && d.connectors) || state.connectors;
            toast(on ? "连接器已开启" : "连接器已关闭");
            loadPlaza("connectors");
          } catch (e) { toast(e.message); sw.classList.toggle("on", !on); }
        });
      }
    } catch (e) { grid.innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`; }
  }
  function openDispatch(expertId) {
    const e = state.experts.find((x) => x.id === expertId);
    el("dispatch-title").textContent = "派单给 " + (e ? e.name : "专家");
    el("dispatch-rubric").innerHTML = (e && e.rubric) ? (typeof e.rubric === "string" ? esc(e.rubric) : "<pre>" + esc(JSON.stringify(e.rubric, null, 2)) + "</pre>") : "无特殊验收标准";
    el("dispatch-task-title").value = "";
    el("dispatch-brief").value = "";
    el("dispatch-modal").classList.remove("hidden");
    el("dispatch-submit").onclick = async () => {
      const title = el("dispatch-task-title").value.trim() || (e ? "任务-" + e.name : "任务");
      const brief = el("dispatch-brief").value.trim();
      try {
        const data = await api("POST", "/api/nexus/tasks", { expert_id: expertId, title, brief });
        const task = data.task || data;
        el("dispatch-modal").classList.add("hidden");
        setSideView("chat");
        const card = appendGoalCard(title, "running");
        toast("已派单，自动运行中");
        api("POST", "/api/nexus/tasks/" + task.id + "/run").catch((e) => toast("运行失败: " + e.message));
        pollTask(task.id, card);
      } catch (err) { toast(err.message); }
    };
  }

  /* ============================ 自动化 ============================ */
  async function loadAutomations() {
    try {
      const d = await api("GET", "/api/automations");
      state.automations = (d && (d.recipes || d.automations)) || [];
      state.autoRuns = (d && d.runs) || [];
      el("auto-list").innerHTML = state.automations.map((a) => `
        <div class="auto-row">
          <div class="ar-ava"><svg class="i"><use href="#ic-clock"/></svg></div>
          <div class="ar-main"><div class="ar-title">${esc(a.label || a.name)}</div><div class="ar-sub">${esc(a.description || a.desc || "")} · ${esc(a.trigger || "")}</div></div>
          <div class="switch ${a.enabled ? "on" : ""}" data-toggle="${esc(a.id)}"></div>
          <button class="ui-btn ui-btn--outline ui-btn--sm" data-run="${esc(a.id)}"><svg class="i"><use href="#ic-play"/></svg> 运行</button>
        </div>`).join("") || `<div class="muted">暂无自动化任务</div>`;
      el("auto-list").querySelectorAll("[data-toggle]").forEach((s) => s.onclick = async () => {
        const id = s.dataset.toggle; const on = !s.classList.contains("on");
        s.classList.toggle("on", on);
        try { await api("PATCH", "/api/automations", { id, enabled: on }); } catch (e) { toast(e.message); s.classList.toggle("on", !on); }
      });
      el("auto-list").querySelectorAll("[data-run]").forEach((b) => b.onclick = async () => {
        try { await api("POST", "/api/automations/" + b.dataset.run + "/run"); toast("已触发运行"); loadAutomations(); }
        catch (e) { toast(e.message); }
      });
      loadRuns();
    } catch (e) { el("auto-list").innerHTML = `<div class="muted">加载失败：${esc(e.message)}</div>`; }
  }
  async function loadRuns() {
    const runs = state.autoRuns || [];
    el("auto-runs").innerHTML = runs.length ? runs.map((r) => `
      <div class="auto-row" style="padding:10px 14px">
        <div class="ar-ava"><svg class="i"><use href="#ic-${r.ok === false ? "x" : "check"}"/></svg></div>
        <div class="ar-main"><div class="ar-title">${esc(r.recipe_label || r.recipe_id || r.name || "运行")}</div>
          <div class="ar-sub">${esc(r.at || r.run_at || "")} · <span class="ui-badge ${r.ok === false ? "ui-badge--destructive" : "ui-badge--success"}">${r.ok === false ? "失败" : "成功"}</span>${r.summary ? " · " + esc(r.summary) : ""}</div></div>
      </div>`).join("") : `<div class="muted">暂无运行记录</div>`;
  }

  /* ============================ 资料库 ============================ */
  async function loadLibrary() {
    try {
      const d = await api("GET", "/api/library");
      const items = (d && d.items) || [];
      state.library = items;
      const list = el("library-list");
      if (!items.length) {
        list.innerHTML = `<div class="muted" style="padding:20px 0">还没有资料。点上方「上传资料」，任务时 AI 会用 library_list / library_read 自动取用。</div>`;
        return;
      }
      list.innerHTML = items.map((it) => `
        <div class="lib-row" data-lib="${esc(it.id)}">
          <svg class="i" style="color:var(--wb-text-3)"><use href="#ic-book"/></svg>
          <span class="ln">${esc(it.name)}</span>
          <span class="lm">${it.size ? (Math.round(it.size / 102.4) / 10) + "KB" : ""} · ${esc((it.created_at || "").slice(0, 10))}</span>
          <button class="ui-btn ui-btn--ghost ui-btn--xs" data-lib-del="${esc(it.id)}">删除</button>
        </div>`).join("");
      list.querySelectorAll("[data-lib]").forEach((row) => {
        row.onclick = async (ev) => {
          if (ev.target.dataset.libDel) return;
          try {
            const r = await api("GET", "/api/library/" + row.dataset.lib);
            const item = (r && r.item) || r;
            openArtifactContent(item.name, item.kind, item.content || "");
          } catch (e) { toast(e.message); }
        };
      });
      list.querySelectorAll("[data-lib-del]").forEach((b) => {
        b.onclick = async (ev) => {
          ev.stopPropagation();
          if (!confirm("删除这份资料？")) return;
          try { await api("DELETE", "/api/library/" + b.dataset.libDel); toast("已删除"); loadLibrary(); }
          catch (e) { toast(e.message); }
        };
      });
    } catch (e) { el("library-list").innerHTML = `<div class="muted">${esc(e.message)}</div>`; }
  }
  async function uploadLibraryFiles(files) {
    for (const f of files) {
      try {
        if (f.size > 200 * 1024) { toast(`${f.name} 过大（>200KB）`); continue; }
        const content = await f.text();
        await api("POST", "/api/library", { name: f.name, content });
        toast(`已上传 ${f.name}`);
      } catch (e) { toast(`${f.name}: ${e.message}`); }
    }
    loadLibrary();
  }

  /* ============================ 设置 ============================ */
  async function loadSettings() {
    await loadModelMenu();
    if (state.user) el("set-name").value = state.user.name || state.user.email || "";
    el("set-locale").value = state.locale;
    el("set-theme").value = state.theme;
    // 智能体区：默认专家 + 自主权限
    try {
      if (!state.experts.length) await loadExperts();
      const sel = el("set-expert");
      sel.innerHTML = state.experts.map((e) => `<option value="${esc(e.id)}">${esc(e.name || e.id)}</option>`).join("") || `<option value="">（无可用专家）</option>`;
      sel.value = state.defaultExpert && state.experts.some((e) => e.id === state.defaultExpert) ? state.defaultExpert : (state.experts[0] || {}).id || "";
    } catch (e) { /* 专家加载失败不阻塞设置页 */ }
    el("set-perm").value = state.perm;
    try {
      const h = await api("GET", "/api/nexus/health");
      el("health-box").innerHTML = `服务状态：<b style="color:var(--wb-ok)">正常</b><br>模型渠道：${esc((h.llm_mode || h.provider || "—"))}<br>存储：${esc(h.store || "memory")}`;
    } catch (e) { el("health-box").textContent = "无法获取服务状态"; }
    try {
      const u = await api("GET", "/api/usage/summary");
      const kinds = u.by_kind || {};
      const kindRows = Object.entries(kinds).map(([k, v]) => `<span class="ui-badge ui-badge--secondary" style="margin-right:6px">${esc(k)} × ${v}</span>`).join("");
      el("usage-box").innerHTML =
        `事件总数：<b>${u.event_count || 0}</b> · 预估成本：<b>¥${(u.estimated_cost_cny || 0).toFixed(2)}</b><br>` +
        `<div style="margin-top:4px">${kindRows || "暂无事件"}</div>`;
    } catch (e) { el("usage-box").textContent = "无法获取用量"; }
    try {
      const im = await api("GET", "/api/im/config");
      state.im = im;
      el("im-url").value = location.origin + im.inbound_path;
      el("im-switch").classList.toggle("on", !!im.enabled);
      el("im-state-hint").textContent = im.enabled ? "已开启 · 密钥 " + im.secret.slice(0, 10) + "…" : "已关闭";
    } catch (e) { el("im-state-hint").textContent = "无法加载 IM 配置"; }
  }
  async function saveModel() {
    const prov = el("model-provider").value; const m = el("model-name").value;
    try {
      await api("POST", "/api/settings/llm", { mode: prov, model: m });
      state.model = m; state.llmProvider = prov;
      updateModelLabel();
      await loadModelMenu();
      toast("模型已切换：" + (m || "跟随默认") + "，立即生效");
    }
    catch (e) { toast(e.message); }
  }
  async function saveAgent() {
    state.defaultExpert = el("set-expert").value || "";
    state.perm = el("set-perm").value || "auto";
    localStorage.setItem("nexus_expert", state.defaultExpert);
    localStorage.setItem("nexus_perm", state.perm);
    toast("智能体设置已保存，下一条任务立即生效");
  }
  async function saveProfile() {
    try {
      const data = await api("PUT", "/api/nexus/profile", { name: el("set-name").value.trim(), locale: el("set-locale").value });
      state.user = data.user || state.user; state.locale = el("set-locale").value; localStorage.setItem("nexus_locale", state.locale);
      applyTheme(el("set-theme").value);
      toast("已保存");
    } catch (e) { toast(e.message); }
  }
  function applyTheme(theme) {
    state.theme = theme; localStorage.setItem("nexus_theme", theme);
    document.documentElement.dataset.theme = theme;
    document.body.dataset.theme = theme;
    el("btn-theme").innerHTML = theme === "dark" ? '<svg class="i"><use href="#ic-sun"/></svg>' : '<svg class="i"><use href="#ic-moon"/></svg>';
  }

  /* ============================ 成果预览面板 ============================ */
  function togglePreview(force) {
    const p = el("preview");
    const show = force != null ? force : !p.classList.contains("show");
    p.classList.toggle("show", show);
    el("toggle-files-t").textContent = show ? "收起" : "成果";
  }
  function openArtifact(path) {
    if (!path) return;
    togglePreview(true);
    el("pv-name").textContent = path.split("/").pop();
    const isHtml = /\.html?$/.test(path);
    const isImg = /\.(png|jpe?g|gif|svg|webp)$/.test(path);
    if (isHtml) {
      el("pv-deploy").hidden = false;
      el("pv-deploy").innerHTML = `<span>本地预览</span><a class="primary" href="/api/nexus/stream/${enc(path)}" target="_blank" style="color:#fff;text-decoration:none;padding:3px 10px;border-radius:7px;background:var(--wb-brand)">新窗口打开</a>`;
      el("pv-body").innerHTML = `<iframe src="/api/nexus/stream/${enc(path)}"></iframe>`;
    } else if (isImg) {
      el("pv-deploy").hidden = true;
      el("pv-body").innerHTML = `<img src="/api/nexus/stream/${enc(path)}">`;
    } else {
      el("pv-deploy").hidden = false;
      el("pv-deploy").innerHTML = `<span>${esc(path)}</span><a class="primary" href="/api/nexus/stream/${enc(path)}" download style="color:#fff;text-decoration:none;padding:3px 10px;border-radius:7px;background:var(--wb-brand)">下载</a>`;
      el("pv-body").innerHTML = `<div class="pv-list"><div class="pv-row"><span class="nm">${esc(path)}</span><a class="dl" href="/api/nexus/stream/${enc(path)}" download>下载</a></div></div>`;
    }
  }

  /* ============================ 对话内搜索 ============================ */
  function toggleMsgSearch(force) {
    const bar = el("chat-search-bar");
    const show = force != null ? force : !bar.classList.contains("show");
    bar.classList.toggle("show", show);
    if (show) { el("msg-search-input").focus(); } else { el("msg-search-input").value = ""; applyMsgSearch(""); }
  }
  function applyMsgSearch(kw) {
    kw = kw.trim().toLowerCase();
    const col = el("chat-col");
    let count = 0;
    col.querySelectorAll(".turn").forEach((turn) => {
      const txt = turn.innerText.toLowerCase();
      const hit = !kw || txt.includes(kw);
      turn.style.display = hit ? "" : "none";
      if (hit && kw) {
        turn.querySelectorAll(".a-text").forEach((at) => { highlight(at, kw); count++; });
      } else {
        turn.querySelectorAll("mark").forEach((m) => { const p = m.parentNode; if (p) { p.replaceChild(document.createTextNode(m.textContent), m); p.normalize(); } });
      }
    });
    el("msg-search-count").textContent = kw ? (count + " 条匹配") : "";
  }
  function highlight(root, kw) {
    root.querySelectorAll("mark").forEach((m) => { const p = m.parentNode; if (p) { p.replaceChild(document.createTextNode(m.textContent), m); p.normalize(); } });
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    const targets = []; let n;
    while ((n = walker.nextNode())) { if (n.parentNode && ["CODE", "PRE", "MARK"].includes(n.parentNode.tagName)) continue; if (n.textContent.toLowerCase().includes(kw)) targets.push(n); }
    targets.forEach((node) => {
      const frag = document.createDocumentFragment(); let last = 0; const low = node.textContent.toLowerCase(); let idx;
      while ((idx = low.indexOf(kw, last)) >= 0) {
        frag.appendChild(document.createTextNode(node.textContent.slice(last, idx)));
        const mk = document.createElement("mark"); mk.textContent = node.textContent.slice(idx, idx + kw.length); frag.appendChild(mk);
        last = idx + kw.length;
      }
      frag.appendChild(document.createTextNode(node.textContent.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  /* ============================ 输入自适应 ============================ */
  function autoGrow(ta) { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 160) + "px"; }

  /* ============================ 启动 ============================ */
  async function loadI18n(locale) {
    try { const d = await api("GET", "/api/i18n/" + locale); Object.assign(L, (d && d.messages) || {}); } catch (e) {}
  }
  async function enter() {
    showMain();
    applyTheme(state.theme);
    await loadI18n(state.locale);
    setupPickers();
    setupSlashMenu();
    // 顶栏默认模型名：后端实际生效模型（用户未手动选过时）
    if (!state.model) {
      api("GET", "/api/settings/llm").then((d) => {
        if (d && d.model && !state.model) { state.defaultModel = d.model; updateModelLabel(); }
      }).catch(() => {});
    }
    try {
      const p = await api("GET", "/api/settings/prefs");
      state.customTemplates = (p.prefs && p.prefs.custom_templates) || [];
    } catch (e) { state.customTemplates = []; }
    try { await loadExperts(); } catch (e) {}
    await loadSessions();
    renderEmpty();
    const last = state.sessions.slice().sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""))[0];
    if (last) await selectSession(last.id);
    el("mode-label").textContent = { ask: "问答", plan: "规划", goal: "目标", craft: "执行" }[state.chatMode];
    el("perm-label").textContent = { ask: "每步都问", auto: "自动", full: "全自动" }[state.perm];
    updateModelLabel();
  }

  function bindStatic() {
    document.querySelectorAll(".auth-tab").forEach((b) => b.onclick = () => {
      document.querySelectorAll(".auth-tab").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      const reg = b.dataset.auth === "register";
      el("lbl-name").hidden = !reg; el("login-name").hidden = !reg;
      el("btn-login").textContent = reg ? "注册" : "登录";
    });
    el("login-form").onsubmit = (e) => { e.preventDefault(); doLogin(document.querySelector(".auth-tab.active").dataset.auth); };
    el("send").onclick = sendMessage;
    const input = el("input");
    input.addEventListener("input", () => autoGrow(input));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
      if ((e.ctrlKey || e.metaKey) && e.key === "f") { e.preventDefault(); toggleMsgSearch(); }
    });
    el("btn-attach").onclick = () => el("file-input").click();
    el("file-input").onchange = (e) => handleFile(e.target.files[0]);
    el("new-task").onclick = newChat;
    el("conv-search").oninput = renderHistory;
    el("msg-search-input").oninput = (e) => applyMsgSearch(e.target.value);
    el("msg-search-close").onclick = () => toggleMsgSearch(false);
    el("btn-msg-search").onclick = () => toggleMsgSearch();
    document.querySelectorAll(".side-nav .item[data-nav]").forEach((it) => {
      if (it.id === "nav-more") return;
      it.onclick = () => setSideView(it.dataset.nav);
    });
    el("nav-more").onclick = () => { el("more-box").classList.toggle("open"); el("nav-more").classList.toggle("open"); };
    el("nav-library").onclick = () => setSideView("library");
    el("lib-upload-btn").onclick = () => el("lib-file-input").click();
    el("lib-file-input").onchange = (e) => { if (e.target.files && e.target.files.length) uploadLibraryFiles([...e.target.files]); e.target.value = ""; };
    document.querySelectorAll("#plaza-tabs button").forEach((b) => b.onclick = () => loadPlaza(b.dataset.tab));
    el("toggle-files").onclick = () => togglePreview();
    el("pv-close").onclick = () => togglePreview(false);
    el("btn-theme").onclick = () => applyTheme(state.theme === "dark" ? "light" : "dark");
    el("btn-save-model").onclick = saveModel;
    el("btn-save-profile").onclick = saveProfile;
    el("btn-save-agent").onclick = saveAgent;
    el("im-switch").onclick = async () => {
      const on = !el("im-switch").classList.contains("on");
      try {
        const d = await api("PUT", "/api/im/config", { enabled: on });
        el("im-switch").classList.toggle("on", !!d.enabled);
        el("im-state-hint").textContent = d.enabled ? "已开启" : "已关闭";
        toast(d.enabled ? "IM 通道已开启" : "IM 通道已关闭");
      } catch (e) { toast(e.message); }
    };
    el("im-copy").onclick = () => {
      navigator.clipboard && navigator.clipboard.writeText(
        `curl -X POST ${location.origin}/api/im/inbound -H 'Content-Type: application/json' -d '{"secret": "${(state.im || {}).secret || ""}", "message": "你的任务"}'`
      );
      toast("curl 示例已复制");
    };
    el("im-reset").onclick = async () => {
      if (!confirm("重置后旧密钥立即失效，确定？")) return;
      try {
        const d = await api("PUT", "/api/im/config", { reset_secret: true });
        state.im = d;
        el("im-state-hint").textContent = "已开启 · 密钥 " + d.secret.slice(0, 10) + "…";
        toast("密钥已重置");
      } catch (e) { toast(e.message); }
    };
    el("dispatch-cancel").onclick = () => el("dispatch-modal").classList.add("hidden");
    el("dispatch-modal").onclick = (e) => { if (e.target === el("dispatch-modal")) el("dispatch-modal").classList.add("hidden"); };
    el("btn-reload").onclick = () => location.reload();
    el("chat-scroll").addEventListener("scroll", () => {
      const cs = el("chat-scroll");
      const nearBottom = cs.scrollHeight - cs.scrollTop - cs.clientHeight < 80;
      el("to-bottom").classList.toggle("show", !nearBottom);
    });
    el("to-bottom").onclick = () => { el("chat-scroll").scrollTop = el("chat-scroll").scrollHeight; };
  }

  async function boot() {
    bindStatic();
    applyTheme(state.theme);
    if (state.token) {
      try {
        const me = await api("GET", "/api/auth/me");
        state.user = me.user || me;
        await enter();
        return;
      } catch (e) { logout(); }
    }
    showLogin();
  }
  // 调试/外部探针（agent-browser eval 用）
  window.NS = { state, api, streamChat, setSideView, selectSession, newChat, sendMessage, togglePreview, openArtifact, openArtifactContent, toggleMsgSearch, applyMsgSearch, applyTheme, loadModelMenu, pollTask, loadLibrary, uploadLibraryFiles, exportTask, loadTaskHistory, loadTemplates };
  boot();
})();
