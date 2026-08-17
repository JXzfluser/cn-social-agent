/** Project board enhancements — filters, progress markers, drag helpers, drawer.
 * Loaded by index.html as /static/project_board.js
 */
(function (global) {
  "use strict";

  const ARTIFACT_LABELS = {
    evidence: "证据",
    canvas: "画布",
    journal: "卡片",
    presentation: "演示",
    video: "视频",
    export_ready: "可导出",
  };

  function progressMarkers(card) {
    const progress = (card && card.progress) || {};
    const markers = progress.markers || {};
    return [
      { id: "evidence", on: !!markers.evidence, label: ARTIFACT_LABELS.evidence },
      { id: "canvas", on: !!markers.canvas, label: ARTIFACT_LABELS.canvas },
      { id: "journal", on: !!markers.journal, label: ARTIFACT_LABELS.journal },
      { id: "presentation", on: !!markers.presentation, label: ARTIFACT_LABELS.presentation },
      { id: "video", on: !!markers.video, label: ARTIFACT_LABELS.video },
    ];
  }

  function progressHtml(card, escapeHtml) {
    const esc = typeof escapeHtml === "function" ? escapeHtml : (s) => String(s || "");
    return `<div class="bc-progress" aria-label="产物进度">${progressMarkers(card)
      .map(
        (m) =>
          `<span class="bc-mark${m.on ? " on" : ""}" title="${esc(m.label)}">${esc(
            m.label.slice(0, 1)
          )}</span>`
      )
      .join("")}</div>`;
  }

  function buildBoardQuery(state) {
    const s = state || {};
    const params = new URLSearchParams();
    if (s.q) params.set("q", s.q);
    if (s.category) params.set("category", s.category);
    if (s.artifact) params.set("artifact", s.artifact);
    if (s.sort) params.set("sort", s.sort);
    return params.toString();
  }

  function drawerHtml(project, escapeHtml) {
    const esc = typeof escapeHtml === "function" ? escapeHtml : (s) => String(s || "");
    const p = project || {};
    const pack = p.evidence_pack || {};
    const evidences = Array.isArray(pack.evidences) ? pack.evidences : [];
    const arts = p.artifacts || {};
    const q = p.quality || {};
    const canvas = p.canvas || {};
    const nodes = Array.isArray(canvas.nodes) ? canvas.nodes : [];
    const title = p.short_topic || p.topic || p.id || "项目";
    const evidenceList = evidences
      .slice(0, 8)
      .map((e) => {
        const t = e.title || e.name || e.url || "证据";
        return `<li>${esc(t)}</li>`;
      })
      .join("");
    return `
      <div class="board-drawer-head">
        <div>
          <div class="label">项目详情</div>
          <h3>${esc(title)}</h3>
          <p class="meta">${esc(p.category || "未分类")} · ${esc(p.status || "")}</p>
        </div>
        <button type="button" class="ghost" data-drawer-close>关闭</button>
      </div>
      <div class="board-drawer-body">
        <section>
          <h4>进度</h4>
          ${progressHtml(
            {
              progress: {
                markers: {
                  evidence: evidences.length > 0,
                  canvas: nodes.length > 0,
                  journal: !!arts.journal_id,
                  presentation: !!arts.presentation_id,
                  video: !!arts.video_id,
                },
              },
            },
            esc
          )}
          <p class="meta">证据 ${evidences.length} · 画布节点 ${nodes.length}</p>
        </section>
        <section>
          <h4>为何值得做</h4>
          <p>${esc(p.why || "—")}</p>
        </section>
        <section>
          <h4>研究笔记</h4>
          <pre class="board-notes">${esc((p.research_notes || "").slice(0, 1200) || "—")}</pre>
        </section>
        <section>
          <h4>证据</h4>
          ${evidenceList ? `<ul>${evidenceList}</ul>` : "<p class=\"meta\">暂无证据</p>"}
        </section>
        <section>
          <h4>质检</h4>
          <p class="meta">${
            q.rejected
              ? `已打回：${esc(q.reject_reason || "")}`
              : q.export_ready
                ? esc(q.hint || "可导出")
                : esc(q.hint || "尚未质检")
          }</p>
        </section>
      </div>
      <div class="board-drawer-actions">
        <button type="button" class="primary" data-drawer-act="canvas" data-id="${esc(p.id)}">打开画布</button>
        <button type="button" class="ghost" data-drawer-act="cards" data-id="${esc(p.id)}">做卡片</button>
      </div>`;
  }

  function wireLaneDropZones(root, onDrop) {
    if (!root) return;
    root.querySelectorAll(".board-col-body[data-lane], .board-col[data-lane] .board-col-body").forEach((lane) => {
      const laneId = lane.dataset.lane || (lane.parentElement && lane.parentElement.dataset.lane) || "";
      if (!laneId || laneId === "rejected") return;
      lane.addEventListener("dragover", (ev) => {
        ev.preventDefault();
        lane.classList.add("drop-target");
      });
      lane.addEventListener("dragleave", () => lane.classList.remove("drop-target"));
      lane.addEventListener("drop", (ev) => {
        ev.preventDefault();
        lane.classList.remove("drop-target");
        const id = ev.dataTransfer.getData("text/project-id") || ev.dataTransfer.getData("text/plain");
        if (id && typeof onDrop === "function") onDrop(id, laneId);
      });
    });
  }

  function makeCardDraggable(cardEl, projectId) {
    if (!cardEl) return;
    cardEl.draggable = true;
    cardEl.addEventListener("dragstart", (ev) => {
      ev.dataTransfer.setData("text/project-id", projectId);
      ev.dataTransfer.setData("text/plain", projectId);
      ev.dataTransfer.effectAllowed = "move";
      cardEl.classList.add("dragging");
    });
    cardEl.addEventListener("dragend", () => cardEl.classList.remove("dragging"));
  }

  global.ProjectBoard = {
    ARTIFACT_LABELS,
    progressMarkers,
    progressHtml,
    buildBoardQuery,
    drawerHtml,
    wireLaneDropZones,
    makeCardDraggable,
  };
})(typeof window !== "undefined" ? window : globalThis);
