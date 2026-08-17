/** Canvas UI enhancements — dialog, edge geometry, viewport math, minimap, fit, context menu.
 * Loaded by index.html as /static/canvas_enhancements.js
 *
 * Edge geometry mirrors `canvas_geometry.py`. The only intentional delta is
 * `ARROW_INSET` (default 10px) so the SVG marker tip sits just outside the
 * target card; pass inset=0 for parity with the Python helper.
 */
(function (global) {
  "use strict";

  const ARROW_INSET = 10;

  /* ---------- Pure viewport helpers (DOM-free, unit-tested) ---------- */

  function scrollExtent(scrollSize, clientSize) {
    return Math.max(0, (Number(scrollSize) || 0) - (Number(clientSize) || 0));
  }

  function clampScroll(scrollLeft, scrollTop, maxLeft, maxTop) {
    return {
      scrollLeft: Math.max(0, Math.min(Number(maxLeft) || 0, Number(scrollLeft) || 0)),
      scrollTop: Math.max(0, Math.min(Number(maxTop) || 0, Number(scrollTop) || 0)),
    };
  }

  function centerScrollFor(worldX, worldY, zoom, viewW, viewH) {
    const z = Number(zoom) || 1;
    return {
      scrollLeft: (Number(worldX) || 0) * z - (Number(viewW) || 0) / 2,
      scrollTop: (Number(worldY) || 0) * z - (Number(viewH) || 0) / 2,
    };
  }

  function contentBounds(nodes, padding) {
    const pad = padding != null ? Number(padding) : 48;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    (nodes || []).forEach((n) => {
      const x = Number(n.x) || 0;
      const y = Number(n.y) || 0;
      const w = Math.max(1, Number(n.w) || 240);
      const h = Math.max(1, Number(n.h) || 150);
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + w);
      maxY = Math.max(maxY, y + h);
    });
    if (!Number.isFinite(minX)) {
      return { minX: 0, minY: 0, maxX: 0, maxY: 0, pad };
    }
    return { minX, minY, maxX, maxY, pad };
  }

  function computeFit(opts) {
    const o = opts || {};
    const nodes = o.nodes || [];
    const viewW = Number(o.viewWidth) || 800;
    const viewH = Number(o.viewHeight) || 600;
    const worldW = Number(o.worldWidth) || 2400;
    const worldH = Number(o.worldHeight) || 1600;
    const minZoom = o.minZoom != null ? Number(o.minZoom) : 0.5;
    const maxZoom = o.maxZoom != null ? Number(o.maxZoom) : 1.6;
    if (!nodes.length) {
      return { zoom: 1, scrollLeft: 0, scrollTop: 0, bounds: { minX: 0, minY: 0, maxX: 0, maxY: 0 } };
    }
    const b = contentBounds(nodes, o.padding);
    const contentW = Math.max(1, b.maxX - b.minX + b.pad * 2);
    const contentH = Math.max(1, b.maxY - b.minY + b.pad * 2);
    let zoom = Math.min(viewW / contentW, viewH / contentH, maxZoom);
    // Floor to two decimals so contentW * zoom never overflows the viewport.
    zoom = Math.max(minZoom, Math.floor(zoom * 100) / 100);
    const centerX = (b.minX + b.maxX) / 2;
    const centerY = (b.minY + b.maxY) / 2;
    const raw = centerScrollFor(centerX, centerY, zoom, viewW, viewH);
    const scrollW = o.scrollWidth != null ? Number(o.scrollWidth) : worldW * zoom;
    const scrollH = o.scrollHeight != null ? Number(o.scrollHeight) : worldH * zoom;
    const clamped = clampScroll(
      raw.scrollLeft,
      raw.scrollTop,
      scrollExtent(scrollW, viewW),
      scrollExtent(scrollH, viewH)
    );
    return {
      zoom,
      scrollLeft: clamped.scrollLeft,
      scrollTop: clamped.scrollTop,
      bounds: { minX: b.minX, minY: b.minY, maxX: b.maxX, maxY: b.maxY },
    };
  }

  function minimapProjection(opts) {
    const o = opts || {};
    const canvasWidth = Number(o.canvasWidth) || 168;
    const canvasHeight = Number(o.canvasHeight) || 112;
    const worldWidth = Number(o.worldWidth) || 2400;
    const worldHeight = Number(o.worldHeight) || 1600;
    const scale = Math.min(canvasWidth / worldWidth, canvasHeight / worldHeight);
    return {
      scale,
      offsetX: (canvasWidth - worldWidth * scale) / 2,
      offsetY: (canvasHeight - worldHeight * scale) / 2,
      canvasWidth,
      canvasHeight,
      worldWidth,
      worldHeight,
    };
  }

  function minimapWorldToPoint(worldX, worldY, projection) {
    const p = projection || {};
    return {
      x: (Number(worldX) || 0) * p.scale + p.offsetX,
      y: (Number(worldY) || 0) * p.scale + p.offsetY,
    };
  }

  function minimapPointToWorld(px, py, projection) {
    const p = projection || {};
    const scale = p.scale || 1;
    return {
      worldX: ((Number(px) || 0) - (p.offsetX || 0)) / scale,
      worldY: ((Number(py) || 0) - (p.offsetY || 0)) / scale,
    };
  }

  function minimapViewportRect(opts) {
    const o = opts || {};
    const p = o.projection || {};
    const zoom = Number(o.zoom) || 1;
    const scrollLeft = Number(o.scrollLeft) || 0;
    const scrollTop = Number(o.scrollTop) || 0;
    const clientWidth = Number(o.clientWidth) || 800;
    const clientHeight = Number(o.clientHeight) || 600;
    return {
      x: (scrollLeft / zoom) * p.scale + p.offsetX,
      y: (scrollTop / zoom) * p.scale + p.offsetY,
      width: (clientWidth / zoom) * p.scale,
      height: (clientHeight / zoom) * p.scale,
    };
  }

  function panStep(opts) {
    const o = opts || {};
    const zoom = Math.max(0.01, Number(o.zoom) || 1);
    const clientWidth = Number(o.clientWidth) || 800;
    const clientHeight = Number(o.clientHeight) || 600;
    return {
      x: (clientWidth * 0.2) / zoom,
      y: (clientHeight * 0.2) / zoom,
    };
  }

  const viewport = {
    scrollExtent,
    clampScroll,
    centerScrollFor,
    computeFit,
    contentBounds,
    minimapProjection,
    minimapWorldToPoint,
    minimapPointToWorld,
    minimapViewportRect,
    panStep,
  };

  /* ---------- URL sanitization ---------- */

  function sanitizeUrl(raw) {
    if (raw == null) return "";
    const text = String(raw).trim();
    if (!text) return "";
    // Strip whitespace / control chars that can smuggle schemes like "java\nscript:"
    const compact = text.replace(/[\u0000-\u001f\u007f\s]+/g, "");
    let parsed;
    try {
      parsed = new URL(compact);
    } catch (_) {
      return "";
    }
    const protocol = String(parsed.protocol || "").toLowerCase();
    if (protocol !== "http:" && protocol !== "https:") return "";
    return parsed.href;
  }

  /* ---------- Edge geometry (mirrors canvas_geometry.py) ---------- */

  function nodeCenter(node) {
    const x = Number(node.x) || 0;
    const y = Number(node.y) || 0;
    const w = Math.max(1, Number(node.w) || 240);
    const h = Math.max(1, Number(node.h) || 150);
    return { x: x + w / 2, y: y + h / 2, w, h, left: x, top: y, right: x + w, bottom: y + h };
  }

  function rayRectExit(cx, cy, dx, dy, node) {
    const b = nodeCenter(node);
    const { left, top, right, bottom } = b;
    if (Math.abs(dx) < 1e-9 && Math.abs(dy) < 1e-9) {
      return { x: right, y: cy };
    }
    const candidates = [];
    if (Math.abs(dx) > 1e-9) {
      for (const edgeX of [left, right]) {
        const t = (edgeX - cx) / dx;
        if (t > 1e-9) {
          const py = cy + t * dy;
          if (top - 1e-6 <= py && py <= bottom + 1e-6) {
            candidates.push({ t, x: edgeX, y: Math.max(top, Math.min(bottom, py)) });
          }
        }
      }
    }
    if (Math.abs(dy) > 1e-9) {
      for (const edgeY of [top, bottom]) {
        const t = (edgeY - cy) / dy;
        if (t > 1e-9) {
          const px = cx + t * dx;
          if (left - 1e-6 <= px && px <= right + 1e-6) {
            candidates.push({ t, x: Math.max(left, Math.min(right, px)), y: edgeY });
          }
        }
      }
    }
    if (!candidates.length) {
      if (Math.abs(dx) >= Math.abs(dy)) {
        return { x: dx >= 0 ? right : left, y: cy };
      }
      return { x: cx, y: dy >= 0 ? bottom : top };
    }
    candidates.sort((a, b) => a.t - b.t);
    return { x: candidates[0].x, y: candidates[0].y };
  }

  function edgeEndpoints(source, target, inset) {
    const pad = inset == null ? ARROW_INSET : inset;
    const s = nodeCenter(source);
    const t = nodeCenter(target);
    const dx = t.x - s.x;
    const dy = t.y - s.y;
    let p1 = rayRectExit(s.x, s.y, dx, dy, source);
    let p2 = rayRectExit(t.x, t.y, -dx, -dy, target);
    const vx = p1.x - p2.x;
    const vy = p1.y - p2.y;
    const len = Math.hypot(vx, vy) || 1;
    p2 = {
      x: p2.x + (vx / len) * pad,
      y: p2.y + (vy / len) * pad,
    };
    return { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y };
  }

  function curvePath(source, target, inset) {
    const { x1, y1, x2, y2 } = edgeEndpoints(source, target, inset);
    const dx = x2 - x1;
    const dy = y2 - y1;
    let ox = -dy * 0.18;
    let oy = dx * 0.18;
    const dist = Math.hypot(dx, dy);
    if (dist < 1e-6) {
      ox = 24;
      oy = 0;
    }
    const c1x = x1 + dx * 0.35 + ox;
    const c1y = y1 + dy * 0.35 + oy;
    const c2x = x2 - dx * 0.35 + ox;
    const c2y = y2 - dy * 0.35 + oy;
    const f = (n) => (Math.round(n * 100) / 100).toFixed(2);
    return `M ${f(x1)} ${f(y1)} C ${f(c1x)} ${f(c1y)} ${f(c2x)} ${f(c2y)} ${f(x2)} ${f(y2)}`;
  }

  const edgeGeometry = {
    ARROW_INSET,
    edgeEndpoints,
    curvePath,
    nodeCenter,
  };

  /* ---------- Accessible in-app dialog ---------- */

  let activeDialog = null;

  function ensureDialog() {
    let dlg = document.getElementById("wbDialog");
    if (dlg) return dlg;
    dlg = document.createElement("dialog");
    dlg.id = "wbDialog";
    dlg.className = "wb-dialog";
    dlg.setAttribute("aria-labelledby", "wbDialogTitle");
    dlg.setAttribute("aria-describedby", "wbDialogMessage");
    dlg.innerHTML = `
      <form method="dialog" class="wb-dialog-form" id="wbDialogForm">
        <h3 id="wbDialogTitle"></h3>
        <p class="wb-dialog-msg" id="wbDialogMessage"></p>
        <div class="wb-dialog-field" id="wbDialogInputWrap" hidden>
          <label for="wbDialogInput" id="wbDialogInputLabel">输入</label>
          <input type="text" id="wbDialogInput" autocomplete="off" />
        </div>
        <div class="wb-dialog-field" id="wbDialogSelectWrap" hidden>
          <label for="wbDialogSelect" id="wbDialogSelectLabel">选择</label>
          <select id="wbDialogSelect"></select>
        </div>
        <div class="wb-dialog-actions">
          <button type="button" class="ghost" id="wbDialogCancel">取消</button>
          <button type="button" class="danger" id="wbDialogDestructive" hidden>删除</button>
          <button type="submit" class="primary" id="wbDialogConfirm">确认</button>
        </div>
      </form>`;
    document.body.appendChild(dlg);
    return dlg;
  }

  function openDialog(opts) {
    if (activeDialog && typeof activeDialog.cancel === "function") {
      // Settle the previous dialog as cancel before opening a new one.
      activeDialog.cancel();
    }
    const options = opts || {};
    const dlg = ensureDialog();
    dlg.setAttribute("aria-describedby", "wbDialogMessage");
    const titleEl = document.getElementById("wbDialogTitle");
    const msgEl = document.getElementById("wbDialogMessage");
    const inputWrap = document.getElementById("wbDialogInputWrap");
    const inputEl = document.getElementById("wbDialogInput");
    const inputLabel = document.getElementById("wbDialogInputLabel");
    const selectWrap = document.getElementById("wbDialogSelectWrap");
    const selectEl = document.getElementById("wbDialogSelect");
    const selectLabel = document.getElementById("wbDialogSelectLabel");
    const cancelBtn = document.getElementById("wbDialogCancel");
    const confirmBtn = document.getElementById("wbDialogConfirm");
    const destBtn = document.getElementById("wbDialogDestructive");
    const form = document.getElementById("wbDialogForm");

    const prevFocus = document.activeElement;
    titleEl.textContent = options.title || "";
    msgEl.textContent = options.message || "";
    msgEl.hidden = !options.message;

    const hasInput = !!options.input;
    inputWrap.hidden = !hasInput;
    if (hasInput) {
      inputLabel.textContent = options.input.label || "输入";
      inputEl.value = options.input.value != null ? String(options.input.value) : "";
      inputEl.placeholder = options.input.placeholder || "";
    }

    const hasSelect = !!options.select;
    selectWrap.hidden = !hasSelect;
    if (hasSelect) {
      selectLabel.textContent = options.select.label || "选择";
      selectEl.innerHTML = "";
      (options.select.options || []).forEach((opt) => {
        const o = document.createElement("option");
        o.value = opt.value;
        o.textContent = opt.label || opt.value;
        selectEl.appendChild(o);
      });
      if (options.select.value != null) selectEl.value = String(options.select.value);
    }

    confirmBtn.textContent = options.confirmLabel || "确认";
    cancelBtn.textContent = options.cancelLabel || "取消";
    const hideConfirm = options.confirmHidden === true;
    confirmBtn.hidden = hideConfirm;
    const showDest = !!options.destructiveLabel;
    destBtn.hidden = !showDest;
    if (showDest) destBtn.textContent = options.destructiveLabel;

    return new Promise((resolve) => {
      let settled = false;
      const controller = new AbortController();
      const { signal } = controller;

      const finish = (action) => {
        if (settled) return;
        settled = true;
        if (activeDialog && activeDialog.promise === promise) activeDialog = null;
        controller.abort();
        if (dlg.open) {
          try {
            dlg.close();
          } catch (_) {
            dlg.removeAttribute("open");
          }
        }
        const result = { action };
        if (action === "confirm") {
          result.value = hasInput ? String(inputEl.value || "") : undefined;
          result.selectValue = hasSelect ? String(selectEl.value || "") : undefined;
        }
        if (prevFocus && prevFocus.isConnected && typeof prevFocus.focus === "function") {
          try {
            prevFocus.focus();
          } catch (_) {}
        }
        resolve(result);
      };

      const promise = {
        cancel: () => finish("cancel"),
      };

      cancelBtn.addEventListener("click", () => finish("cancel"), { signal });
      destBtn.addEventListener("click", () => finish("destructive"), { signal });
      form.addEventListener(
        "submit",
        (ev) => {
          ev.preventDefault();
          if (hideConfirm && showDest) finish("destructive");
          else if (!hideConfirm) finish("confirm");
        },
        { signal }
      );
      dlg.addEventListener(
        "cancel",
        (ev) => {
          ev.preventDefault();
          finish("cancel");
        },
        { signal }
      );
      dlg.addEventListener(
        "keydown",
        (ev) => {
          if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            finish("cancel");
          } else if (ev.key === "Enter" && ev.target === inputEl) {
            ev.preventDefault();
            if (hideConfirm && showDest) finish("destructive");
            else if (!hideConfirm) finish("confirm");
          }
        },
        { signal }
      );

      activeDialog = { promise, cancel: promise.cancel };
      try {
        if (typeof dlg.showModal === "function") {
          if (dlg.open) dlg.close();
          dlg.showModal();
        } else {
          dlg.setAttribute("open", "");
        }
      } catch (_) {
        dlg.setAttribute("open", "");
      }

      requestAnimationFrame(() => {
        if (hasInput) {
          inputEl.focus();
          inputEl.select();
        } else if (hasSelect) {
          selectEl.focus();
        } else if (!destBtn.hidden && (options.destructiveFocus || hideConfirm)) {
          destBtn.focus();
        } else if (!confirmBtn.hidden) {
          confirmBtn.focus();
        } else {
          cancelBtn.focus();
        }
      });
    });
  }

  /* ---------- Fit content ---------- */

  function fitContent(opts) {
    const o = opts || {};
    const board = o.board;
    const worldW = o.worldWidth || 2400;
    const worldH = o.worldHeight || 1600;
    if (!board) {
      return { zoom: 1, scrollLeft: 0, scrollTop: 0 };
    }
    const syncSizer =
      typeof o.syncSizer === "function"
        ? o.syncSizer
        : (zoom) => {
            const sizer = document.getElementById("canvasSizer");
            if (sizer) {
              sizer.style.width = `${worldW * zoom}px`;
              sizer.style.height = `${worldH * zoom}px`;
            }
          };
    // First pass: compute zoom against world extents.
    const first = computeFit({
      nodes: o.nodes || [],
      viewWidth: board.clientWidth || 800,
      viewHeight: board.clientHeight || 600,
      worldWidth: worldW,
      worldHeight: worldH,
      padding: o.padding,
      minZoom: o.minZoom,
      maxZoom: o.maxZoom,
    });
    if (typeof o.setZoom === "function") o.setZoom(first.zoom);
    syncSizer(first.zoom);
    // Second pass: clamp against the real scrollable size after the sizer grows.
    const second = computeFit({
      nodes: o.nodes || [],
      viewWidth: board.clientWidth || 800,
      viewHeight: board.clientHeight || 600,
      worldWidth: worldW,
      worldHeight: worldH,
      padding: o.padding,
      minZoom: o.minZoom,
      maxZoom: o.maxZoom,
      scrollWidth: board.scrollWidth || worldW * first.zoom,
      scrollHeight: board.scrollHeight || worldH * first.zoom,
    });
    board.scrollLeft = second.scrollLeft;
    board.scrollTop = second.scrollTop;
    return second;
  }

  /* ---------- Minimap ---------- */

  function renderMinimap(opts) {
    const o = opts || {};
    const container = o.container;
    if (!container) return null;
    let canvas = container.querySelector("canvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.width = 168;
      canvas.height = 112;
      canvas.setAttribute("aria-hidden", "true");
      container.appendChild(canvas);
    }
    const ctx = canvas.getContext("2d");
    const projection = minimapProjection({
      canvasWidth: canvas.width,
      canvasHeight: canvas.height,
      worldWidth: o.worldWidth || 2400,
      worldHeight: o.worldHeight || 1600,
    });
    const { scale, offsetX: ox, offsetY: oy } = projection;
    const worldW = projection.worldWidth;
    const worldH = projection.worldHeight;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f3efe7";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(28,25,23,.12)";
    ctx.strokeRect(ox + 0.5, oy + 0.5, worldW * scale - 1, worldH * scale - 1);

    (o.nodes || []).forEach((n) => {
      const pt = minimapWorldToPoint(Number(n.x) || 0, Number(n.y) || 0, projection);
      const w = Math.max(2, (Number(n.w) || 240) * scale);
      const h = Math.max(2, (Number(n.h) || 150) * scale);
      ctx.fillStyle = n.done ? "rgba(120,113,108,.45)" : "rgba(15,118,110,.55)";
      ctx.fillRect(pt.x, pt.y, w, h);
    });

    const rect = minimapViewportRect({
      projection,
      zoom: o.zoom || 1,
      scrollLeft: o.scrollLeft || 0,
      scrollTop: o.scrollTop || 0,
      clientWidth: o.clientWidth || 800,
      clientHeight: o.clientHeight || 600,
    });
    ctx.strokeStyle = "rgba(15,118,110,.9)";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(rect.x, rect.y, rect.width, rect.height);
    ctx.fillStyle = "rgba(15,118,110,.12)";
    ctx.fillRect(rect.x, rect.y, rect.width, rect.height);

    container._cvMiniMapMeta = { ...projection, canvas, zoom: o.zoom || 1 };
    return container._cvMiniMapMeta;
  }

  function bindMinimapNavigation(container, getState, onNavigate) {
    if (!container || container._cvMiniNav) return;
    container._cvMiniNav = true;
    if (!container.hasAttribute("tabindex")) container.setAttribute("tabindex", "0");
    if (!container.getAttribute("role")) container.setAttribute("role", "application");

    const worldFromEvent = (ev) => {
      const meta = container._cvMiniMapMeta;
      const canvas = meta && meta.canvas;
      if (!meta || !canvas) return null;
      const rect = canvas.getBoundingClientRect();
      const mx = ((ev.clientX - rect.left) / rect.width) * canvas.width;
      const my = ((ev.clientY - rect.top) / rect.height) * canvas.height;
      return minimapPointToWorld(mx, my, meta);
    };

    const navigate = (ev) => {
      const pt = worldFromEvent(ev);
      if (!pt || typeof onNavigate !== "function") return;
      onNavigate(pt.worldX, pt.worldY);
    };

    let dragging = false;
    container.addEventListener("pointerdown", (ev) => {
      dragging = true;
      try {
        container.setPointerCapture(ev.pointerId);
      } catch (_) {}
      navigate(ev);
    });
    container.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      navigate(ev);
    });
    const endDrag = () => {
      dragging = false;
    };
    container.addEventListener("pointerup", endDrag);
    container.addEventListener("pointercancel", endDrag);

    container.addEventListener("keydown", (ev) => {
      const state = typeof getState === "function" ? getState() : null;
      const zoom = (state && state.zoom) || (container._cvMiniMapMeta && container._cvMiniMapMeta.zoom) || 1;
      const clientWidth = (state && state.clientWidth) || 800;
      const clientHeight = (state && state.clientHeight) || 600;
      const scrollLeft = (state && state.scrollLeft) || 0;
      const scrollTop = (state && state.scrollTop) || 0;
      const step = panStep({ clientWidth, clientHeight, zoom });
      let worldX = scrollLeft / zoom + clientWidth / zoom / 2;
      let worldY = scrollTop / zoom + clientHeight / zoom / 2;
      let moved = false;
      if (ev.key === "ArrowLeft") {
        worldX -= step.x;
        moved = true;
      } else if (ev.key === "ArrowRight") {
        worldX += step.x;
        moved = true;
      } else if (ev.key === "ArrowUp") {
        worldY -= step.y;
        moved = true;
      } else if (ev.key === "ArrowDown") {
        worldY += step.y;
        moved = true;
      } else if (ev.key === "Home") {
        worldX = clientWidth / zoom / 2;
        worldY = clientHeight / zoom / 2;
        moved = true;
      }
      if (!moved || typeof onNavigate !== "function") return;
      ev.preventDefault();
      onNavigate(worldX, worldY);
    });
  }

  /* ---------- Context menu ---------- */

  function ensureContextMenu() {
    let menu = document.getElementById("canvasNodeMenu");
    if (menu) return menu;
    menu = document.createElement("div");
    menu.id = "canvasNodeMenu";
    menu.className = "cv-node-menu";
    menu.hidden = true;
    menu.setAttribute("role", "menu");
    document.body.appendChild(menu);
    return menu;
  }

  function restoreFocus(el) {
    if (el && typeof el.focus === "function") {
      try {
        el.focus();
      } catch (_) {}
    }
  }

  function closeContextMenu() {
    const menu = document.getElementById("canvasNodeMenu");
    const prev = document._cvMenuPrevFocus || null;
    if (menu) {
      menu.hidden = true;
      menu.innerHTML = "";
    }
    if (document._cvMenuController) {
      try {
        document._cvMenuController.abort();
      } catch (_) {}
      document._cvMenuController = null;
    }
    document._cvMenuAway = null;
    document._cvMenuKey = null;
    restoreFocus(prev);
    document._cvMenuPrevFocus = null;
  }

  function openContextMenu(opts) {
    const o = opts || {};
    const menu = ensureContextMenu();
    closeContextMenu();
    document._cvMenuPrevFocus = document.activeElement;
    menu.innerHTML = "";
    (o.items || []).forEach((item) => {
      if (item.separator) {
        const hr = document.createElement("div");
        hr.className = "cv-node-menu-sep";
        menu.appendChild(hr);
        return;
      }
      const btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("role", "menuitem");
      btn.tabIndex = -1;
      btn.className = "cv-node-menu-item" + (item.danger ? " danger" : "");
      btn.textContent = item.label;
      btn.dataset.act = item.id;
      btn.onclick = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        closeContextMenu();
        if (typeof o.onSelect === "function") o.onSelect(item.id);
      };
      menu.appendChild(btn);
    });

    menu.hidden = false;
    const pad = 8;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    menu.style.left = "0px";
    menu.style.top = "0px";
    const mw = menu.offsetWidth || 160;
    const mh = menu.offsetHeight || 200;
    let left = o.x || 0;
    let top = o.y || 0;
    if (left + mw + pad > vw) left = Math.max(pad, vw - mw - pad);
    if (top + mh + pad > vh) top = Math.max(pad, vh - mh - pad);
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;

    const items = Array.from(menu.querySelectorAll('[role="menuitem"]'));
    let idx = 0;
    if (items.length) {
      items[0].tabIndex = 0;
      items[0].focus();
    }

    const controller = new AbortController();
    document._cvMenuController = controller;
    const { signal } = controller;

    document._cvMenuAway = (ev) => {
      if (menu.contains(ev.target)) return;
      closeContextMenu();
    };
    document._cvMenuKey = (ev) => {
      if (ev.key === "Escape") {
        ev.preventDefault();
        closeContextMenu();
        return;
      }
      if (!items.length) return;
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        idx = (idx + 1) % items.length;
        items.forEach((el, i) => {
          el.tabIndex = i === idx ? 0 : -1;
        });
        items[idx].focus();
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        idx = (idx - 1 + items.length) % items.length;
        items.forEach((el, i) => {
          el.tabIndex = i === idx ? 0 : -1;
        });
        items[idx].focus();
      } else if (ev.key === "Enter" || ev.key === " ") {
        const active = items[idx];
        if (active) {
          ev.preventDefault();
          active.click();
        }
      }
    };
    // Attach immediately — no setTimeout race.
    document.addEventListener("pointerdown", document._cvMenuAway, { capture: true, signal });
    document.addEventListener("keydown", document._cvMenuKey, { capture: true, signal });

    return menu;
  }

  /* ---------- Template picker / AI organize ---------- */

  const DEFAULT_TEMPLATES = [
    { id: "blank", label: "空白画布" },
    { id: "topic_funnel", label: "选题漏斗" },
    { id: "script_structure", label: "脚本结构" },
    { id: "swot", label: "SWOT 分析" },
  ];

  async function openTemplatePicker(opts) {
    const o = opts || {};
    let templates = o.templates;
    if (!templates || !templates.length) {
      if (typeof o.fetchTemplates === "function") {
        try {
          templates = await o.fetchTemplates();
        } catch (_) {
          templates = DEFAULT_TEMPLATES;
        }
      } else {
        templates = DEFAULT_TEMPLATES;
      }
    }
    const result = await openDialog({
      title: o.title || "新建画布",
      message: o.message || "选一个模板开始，或从空白画布写起。",
      input: {
        label: "画布名称",
        value: o.defaultTitle || "新画布",
        placeholder: "新画布",
      },
      select: {
        label: "模板",
        value: o.defaultTemplate || "blank",
        options: templates.map((t) => ({ value: t.id, label: t.label || t.id })),
      },
      confirmLabel: "创建",
      cancelLabel: "取消",
    });
    if (result.action !== "confirm") return null;
    return {
      title: (result.value || "").trim() || "新画布",
      template_id: result.selectValue || "blank",
    };
  }

  async function organizeSelection(opts) {
    const o = opts || {};
    if (typeof o.api !== "function") throw new Error("organizeSelection requires api()");
    const body = {
      project_id: o.projectId || "",
      board_id: o.boardId || "",
      node_ids: Array.isArray(o.nodeIds) ? o.nodeIds : [],
      instruction: o.instruction || "",
    };
    return o.api("/api/canvas/organize", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  const CanvasEnhancements = {
    openDialog,
    edgeGeometry,
    viewport,
    sanitizeUrl,
    renderMinimap,
    bindMinimapNavigation,
    fitContent,
    openContextMenu,
    closeContextMenu,
    openTemplatePicker,
    organizeSelection,
    DEFAULT_TEMPLATES,
  };

  global.CanvasEnhancements = CanvasEnhancements;
})(typeof window !== "undefined" ? window : globalThis);
