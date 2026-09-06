export class CanvasRenderer {
  constructor(container, options = {}) {
    this.container = container;
    this.options = {
      gridSize: 8,
      minZoom: 0.1,
      maxZoom: 5,
      virtualBuffer: 200,
      theme: 'dark',
      animateConnections: true,
      ...options,
    };

    this.canvas = document.createElement('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.container.appendChild(this.canvas);

    this.nodes = [];
    this.edges = [];
    this.selected = new Set();
    this.hovered = null;
    this.dragging = null;
    this.connecting = null;
    this.selectionBox = null;

    this.viewport = { x: 0, y: 0, zoom: 1 };
    this.offset = { x: 0, y: 0 };

    this.animationFrame = null;
    this.dirty = true;
    this.animationTime = 0;

    this.themes = {
      dark: {
        background: '#0f1219',
        grid: 'rgba(255,255,255,0.03)',
        nodeBg: 'rgba(30,35,50,0.95)',
        nodeHover: 'rgba(255,255,255,0.08)',
        nodeSelected: 'rgba(59,130,246,0.15)',
        border: 'rgba(255,255,255,0.1)',
        borderHover: 'rgba(255,255,255,0.2)',
        borderSelected: '#3b82f6',
        text: '#fff',
        textSecondary: 'rgba(255,255,255,0.4)',
        textTertiary: 'rgba(255,255,255,0.6)',
        connection: 'rgba(100,160,255,0.4)',
        connectionHighlight: '#60a5fa',
      },
      light: {
        background: '#f8fafc',
        grid: 'rgba(0,0,0,0.05)',
        nodeBg: '#ffffff',
        nodeHover: 'rgba(0,0,0,0.03)',
        nodeSelected: 'rgba(59,130,246,0.1)',
        border: 'rgba(0,0,0,0.1)',
        borderHover: 'rgba(0,0,0,0.2)',
        borderSelected: '#3b82f6',
        text: '#1e293b',
        textSecondary: 'rgba(0,0,0,0.5)',
        textTertiary: 'rgba(0,0,0,0.7)',
        connection: 'rgba(59,130,246,0.3)',
        connectionHighlight: '#3b82f6',
      },
    };

    this._bindEvents();
    this._resize();
    window.addEventListener('resize', () => this._resize());
  }

  setTheme(theme) {
    this.options.theme = theme;
    this.dirty = true;
  }

  _resize() {
    const rect = this.container.getBoundingClientRect();
    this.canvas.width = rect.width * devicePixelRatio;
    this.canvas.height = rect.height * devicePixelRatio;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = rect.height + 'px';
    this.ctx.scale(devicePixelRatio, devicePixelRatio);
    this.dirty = true;
  }

  _bindEvents() {
    this.canvas.addEventListener('mousedown', (e) => this._onMouseDown(e));
    this.canvas.addEventListener('mousemove', (e) => this._onMouseMove(e));
    this.canvas.addEventListener('mouseup', (e) => this._onMouseUp(e));
    this.canvas.addEventListener('wheel', (e) => this._onWheel(e));
    this.canvas.addEventListener('dblclick', (e) => this._onDblClick(e));
    document.addEventListener('keydown', (e) => this._onKeyDown(e));
  }

  _screenToWorld(sx, sy) {
    return {
      x: (sx - this.offset.x) / this.viewport.zoom + this.viewport.x,
      y: (sy - this.offset.y) / this.viewport.zoom + this.viewport.y,
    };
  }

  _worldToScreen(wx, wy) {
    return {
      x: (wx - this.viewport.x) * this.viewport.zoom + this.offset.x,
      y: (wy - this.viewport.y) * this.viewport.zoom + this.offset.y,
    };
  }

  _hitTest(wx, wy) {
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const n = this.nodes[i];
      if (wx >= n.x && wx <= n.x + n.w && wy >= n.y && wy <= n.y + n.h) {
        return n;
      }
    }
    return null;
  }

  _onMouseDown(e) {
    const rect = this.canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const world = this._screenToWorld(sx, sy);

    const node = this._hitTest(world.x, world.y);

    if (e.shiftKey && node) {
      if (this.selected.has(node.id)) {
        this.selected.delete(node.id);
      } else {
        this.selected.add(node.id);
      }
      this.dirty = true;
      return;
    }

    if (this.connecting) {
      if (node && this.connecting.from !== node.id) {
        this.edges.push({
          id: 'eg_' + Math.random().toString(36).slice(2, 12),
          from: this.connecting.from,
          to: node.id,
          label: '',
        });
        this.dirty = true;
      }
      this.connecting = null;
      return;
    }

    if (node) {
      if (!this.selected.has(node.id)) {
        this.selected.clear();
        this.selected.add(node.id);
      }
      this.dragging = {
        node,
        startX: world.x - node.x,
        startY: world.y - node.y,
      };
    } else {
      this.selected.clear();
      this.selectionBox = { x: world.x, y: world.y, w: 0, h: 0 };
    }
    this.dirty = true;
  }

  _onMouseMove(e) {
    const rect = this.canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const world = this._screenToWorld(sx, sy);

    if (this.dragging) {
      const n = this.dragging.node;
      n.x = this._snap(world.x - this.dragging.startX);
      n.y = this._snap(world.y - this.dragging.startY);
      this.dirty = true;
      return;
    }

    if (this.selectionBox) {
      this.selectionBox.w = world.x - this.selectionBox.x;
      this.selectionBox.h = world.y - this.selectionBox.y;
      this.dirty = true;
      return;
    }

    const node = this._hitTest(world.x, world.y);
    if (node !== this.hovered) {
      this.hovered = node;
      this.canvas.style.cursor = node ? 'grab' : 'default';
      this.dirty = true;
    }
  }

  _onMouseUp(e) {
    if (this.selectionBox) {
      const box = this._normalizeBox(this.selectionBox);
      this.nodes.forEach((n) => {
        if (this._boxIntersects(box, n)) {
          this.selected.add(n.id);
        }
      });
      this.selectionBox = null;
      this.dirty = true;
    }
    this.dragging = null;
  }

  _onWheel(e) {
    e.preventDefault();
    const rect = this.canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(
      this.options.minZoom,
      Math.min(this.options.maxZoom, this.viewport.zoom * delta)
    );

    const world = this._screenToWorld(sx, sy);
    this.viewport.zoom = newZoom;
    this.offset.x = sx - (world.x - this.viewport.x) * newZoom;
    this.offset.y = sy - (world.y - this.viewport.y) * newZoom;

    this.dirty = true;
  }

  _onDblClick(e) {
    const rect = this.canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const world = this._screenToWorld(sx, sy);

    if (!this._hitTest(world.x, world.y)) {
      this.addNode({
        x: this._snap(world.x),
        y: this._snap(world.y),
      });
    }
  }

  _onKeyDown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === 'Delete' || e.key === 'Backspace') {
      this.deleteSelected();
    }
    if (e.key === 'a' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      this.selectAll();
    }
    if (e.key === 'Escape') {
      this.selected.clear();
      this.connecting = null;
      this.dirty = true;
    }
    if (e.key === 'g' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      this.groupSelected();
    }
    if (e.key === 'g' && e.shiftKey && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      this.ungroupSelected();
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      this.moveSelected(0, -this.options.gridSize);
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      this.moveSelected(0, this.options.gridSize);
    }
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      this.moveSelected(-this.options.gridSize, 0);
    }
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      this.moveSelected(this.options.gridSize, 0);
    }
  }

  _snap(v) {
    return Math.round(v / this.options.gridSize) * this.options.gridSize;
  }

  _normalizeBox(box) {
    return {
      x: Math.min(box.x, box.x + box.w),
      y: Math.min(box.y, box.y + box.h),
      w: Math.abs(box.w),
      h: Math.abs(box.h),
    };
  }

  _boxIntersects(a, b) {
    return !(a.x > b.x + b.w || a.x + a.w < b.x || a.y > b.y + b.h || a.y + a.h < b.y);
  }

  setNodes(nodes) {
    this.nodes = nodes;
    this.dirty = true;
  }

  setEdges(edges) {
    this.edges = edges;
    this.dirty = true;
  }

  addNode(opts = {}) {
    const node = {
      id: 'nd_' + Math.random().toString(36).slice(2, 14),
      kind: opts.kind || 'note',
      color: opts.color || '',
      done: false,
      title: opts.title || '',
      text: opts.text || '',
      url: opts.url || '',
      x: opts.x || 0,
      y: opts.y || 0,
      w: opts.w || 240,
      h: opts.h || 150,
      tags: opts.tags || [],
      pinned: false,
    };
    this.nodes.push(node);
    this.selected.clear();
    this.selected.add(node.id);
    this.dirty = true;
    return node;
  }

  deleteSelected() {
    if (this.selected.size === 0) return;
    this.nodes = this.nodes.filter((n) => !this.selected.has(n.id));
    this.edges = this.edges.filter(
      (e) => !this.selected.has(e.from) && !this.selected.has(e.to)
    );
    this.selected.clear();
    this.dirty = true;
  }

  selectAll() {
    this.nodes.forEach((n) => this.selected.add(n.id));
    this.dirty = true;
  }

  startConnect(nodeId) {
    this.connecting = { from: nodeId };
  }

  autoLayout() {
    const cols = 4;
    const gapX = 280;
    const gapY = 180;
    this.nodes.forEach((n, i) => {
      n.x = 40 + (i % cols) * gapX;
      n.y = 40 + Math.floor(i / cols) * gapY;
    });
    this.dirty = true;
  }

  autoLayoutByKind() {
    const grouped = {};
    this.nodes.forEach((n) => {
      if (!grouped[n.kind]) grouped[n.kind] = [];
      grouped[n.kind].push(n);
    });

    let offsetY = 40;
    const gapX = 280;
    const gapY = 180;

    Object.keys(grouped).sort().forEach((kind) => {
      const nodes = grouped[kind];
      nodes.forEach((n, i) => {
        n.x = 40 + (i % 4) * gapX;
        n.y = offsetY + Math.floor(i / 4) * gapY;
      });
      offsetY += Math.ceil(nodes.length / 4) * gapY + 60;
    });
    this.dirty = true;
  }

  autoLayoutRadial() {
    if (this.nodes.length === 0) return;
    const cx = 600;
    const cy = 400;
    const radius = Math.min(300, 50 + this.nodes.length * 20);

    this.nodes.forEach((n, i) => {
      const angle = (i / this.nodes.length) * Math.PI * 2;
      n.x = cx + Math.cos(angle) * radius - n.w / 2;
      n.y = cy + Math.sin(angle) * radius - n.h / 2;
    });
    this.dirty = true;
  }

  groupSelected() {
    if (this.selected.size < 2) return;
    const selectedNodes = this.nodes.filter((n) => this.selected.has(n.id));
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    selectedNodes.forEach((n) => {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + n.w);
      maxY = Math.max(maxY, n.y + n.h);
    });

    const groupId = 'grp_' + Math.random().toString(36).slice(2, 10);
    selectedNodes.forEach((n) => {
      n.groupId = groupId;
    });

    this.dirty = true;
    return { id: groupId, x: minX, y: minY, w: maxX - minX, h: maxY - minY };
  }

  ungroupSelected() {
    const selectedNodes = this.nodes.filter((n) => this.selected.has(n.id));
    const groupIds = new Set(selectedNodes.map((n) => n.groupId).filter(Boolean));
    if (groupIds.size === 0) return;

    this.nodes.forEach((n) => {
      if (groupIds.has(n.groupId)) {
        n.groupId = null;
      }
    });
    this.dirty = true;
  }

  moveSelected(dx, dy) {
    this.nodes.forEach((n) => {
      if (this.selected.has(n.id)) {
        n.x = this._snap(n.x + dx);
        n.y = this._snap(n.y + dy);
      }
    });
    this.dirty = true;
  }

  fitToContent() {
    if (this.nodes.length === 0) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    this.nodes.forEach((n) => {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + n.w);
      maxY = Math.max(maxY, n.y + n.h);
    });
    const rect = this.container.getBoundingClientRect();
    const padding = 60;
    const contentW = maxX - minX + padding * 2;
    const contentH = maxY - minY + padding * 2;
    const zoom = Math.min(rect.width / contentW, rect.height / contentH, 1.5);
    this.viewport.zoom = zoom;
    this.viewport.x = minX - padding;
    this.viewport.y = minY - padding;
    this.offset.x = (rect.width - contentW * zoom) / 2;
    this.offset.y = (rect.height - contentH * zoom) / 2;
    this.dirty = true;
  }

  render() {
    if (!this.dirty && !this.options.animateConnections) return;
    this.dirty = false;

    const ctx = this.ctx;
    const w = this.canvas.width / devicePixelRatio;
    const h = this.canvas.height / devicePixelRatio;
    const theme = this.themes[this.options.theme];

    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = theme.background;
    ctx.fillRect(0, 0, w, h);

    ctx.save();
    ctx.translate(this.offset.x, this.offset.y);
    ctx.scale(this.viewport.zoom, this.viewport.zoom);
    ctx.translate(-this.viewport.x, -this.viewport.y);

    const viewBounds = {
      x: this.viewport.x - this.options.virtualBuffer,
      y: this.viewport.y - this.options.virtualBuffer,
      w: w / this.viewport.zoom + this.options.virtualBuffer * 2,
      h: h / this.viewport.zoom + this.options.virtualBuffer * 2,
    };

    this._drawGrid(ctx, w, h);
    this._drawGroups(ctx, viewBounds);
    this._drawEdges(ctx, viewBounds);
    this._drawNodes(ctx, viewBounds);
    this._drawSelectionBox(ctx);

    ctx.restore();
  }

  _drawGrid(ctx, w, h) {
    const gridSize = this.options.gridSize;
    const zoom = this.viewport.zoom;
    const step = zoom < 0.5 ? gridSize * 4 : gridSize;
    const theme = this.themes[this.options.theme];

    const startX = Math.floor(this.viewport.x / step) * step;
    const startY = Math.floor(this.viewport.y / step) * step;
    const endX = this.viewport.x + w / zoom;
    const endY = this.viewport.y + h / zoom;

    ctx.strokeStyle = theme.grid;
    ctx.lineWidth = 0.5 / zoom;
    ctx.beginPath();
    for (let x = startX; x <= endX; x += step) {
      ctx.moveTo(x, startY);
      ctx.lineTo(x, endY);
    }
    for (let y = startY; y <= endY; y += step) {
      ctx.moveTo(startX, y);
      ctx.lineTo(endX, y);
    }
    ctx.stroke();
  }

  _drawGroups(ctx, viewBounds) {
    const zoom = this.viewport.zoom;
    const theme = this.themes[this.options.theme];
    const groups = new Map();

    this.nodes.forEach((n) => {
      if (!n.groupId) return;
      if (!groups.has(n.groupId)) {
        groups.set(n.groupId, { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity });
      }
      const g = groups.get(n.groupId);
      g.minX = Math.min(g.minX, n.x);
      g.minY = Math.min(g.minY, n.y);
      g.maxX = Math.max(g.maxX, n.x + n.w);
      g.maxY = Math.max(g.maxY, n.y + n.h);
    });

    groups.forEach((g) => {
      const padding = 20 / zoom;
      const x = g.minX - padding;
      const y = g.minY - padding;
      const w = g.maxX - g.minX + padding * 2;
      const h = g.maxY - g.minY + padding * 2;

      ctx.strokeStyle = 'rgba(99,102,241,0.3)';
      ctx.lineWidth = 1 / zoom;
      ctx.setLineDash([4 / zoom, 4 / zoom]);
      ctx.strokeRect(x, y, w, h);
      ctx.setLineDash([]);
    });
  }

  _drawEdges(ctx, viewBounds) {
    const theme = this.themes[this.options.theme];
    const zoom = this.viewport.zoom;
    this.animationTime += 0.02;

    const nodeMap = new Map(this.nodes.map((n) => [n.id, n]));

    this.edges.forEach((e, i) => {
      const from = nodeMap.get(e.from);
      const to = nodeMap.get(e.to);
      if (!from || !to) return;

      const fx = from.x + from.w / 2;
      const fy = from.y + from.h / 2;
      const tx = to.x + to.w / 2;
      const ty = to.y + to.h / 2;

      if (
        (fx < viewBounds.x && tx < viewBounds.x) ||
        (fx > viewBounds.x + viewBounds.w && tx > viewBounds.x + viewBounds.w) ||
        (fy < viewBounds.y && ty < viewBounds.y) ||
        (fy > viewBounds.y + viewBounds.h && ty > viewBounds.y + viewBounds.h)
      ) {
        return;
      }

      const dx = tx - fx;
      const dy = ty - fy;
      const cx1 = fx + dx * 0.4;
      const cy1 = fy;
      const cx2 = tx - dx * 0.4;
      const cy2 = ty;

      ctx.strokeStyle = theme.connection;
      ctx.lineWidth = 2 / zoom;
      ctx.setLineDash([]);

      ctx.beginPath();
      ctx.moveTo(fx, fy);
      ctx.bezierCurveTo(cx1, cy1, cx2, cy2, tx, ty);
      ctx.stroke();

      if (this.options.animateConnections) {
        const t = (this.animationTime * 0.3 + i * 0.1) % 1;
        const px = this._bezierPoint(fx, cx1, cx2, tx, t);
        const py = this._bezierPoint(fy, cy1, cy2, ty, t);

        ctx.fillStyle = theme.connectionHighlight;
        ctx.beginPath();
        ctx.arc(px, py, 3 / zoom, 0, Math.PI * 2);
        ctx.fill();
      }

      const angle = Math.atan2(ty - cy2, tx - cx2);
      const arrowSize = 8 / zoom;
      ctx.fillStyle = theme.connection;
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(
        tx - arrowSize * Math.cos(angle - 0.3),
        ty - arrowSize * Math.sin(angle - 0.3)
      );
      ctx.lineTo(
        tx - arrowSize * Math.cos(angle + 0.3),
        ty - arrowSize * Math.sin(angle + 0.3)
      );
      ctx.closePath();
      ctx.fill();
    });
  }

  _bezierPoint(p0, p1, p2, p3, t) {
    const mt = 1 - t;
    return mt * mt * mt * p0 + 3 * mt * mt * t * p1 + 3 * mt * t * t * p2 + t * t * t * p3;
  }

  _drawNodes(ctx, viewBounds) {
    const zoom = this.viewport.zoom;

    this.nodes.forEach((node) => {
      if (
        node.x + node.w < viewBounds.x ||
        node.x > viewBounds.x + viewBounds.w ||
        node.y + node.h < viewBounds.y ||
        node.y > viewBounds.y + viewBounds.h
      ) {
        return;
      }

      const isSelected = this.selected.has(node.id);
      const isHovered = this.hovered === node;

      ctx.fillStyle = isSelected
        ? theme.nodeSelected
        : isHovered
        ? theme.nodeHover
        : theme.nodeBg;
      ctx.strokeStyle = isSelected
        ? theme.borderSelected
        : isHovered
        ? theme.borderHover
        : theme.border;
      ctx.lineWidth = isSelected ? 2 / zoom : 1 / zoom;

      const r = 8 / zoom;
      this._roundRect(ctx, node.x, node.y, node.w, node.h, r);
      ctx.fill();
      ctx.stroke();

      if (node.color) {
        const colors = {
          yellow: '#fbbf24',
          green: '#34d399',
          blue: '#60a5fa',
          pink: '#f472b6',
          purple: '#a78bfa',
          gray: '#9ca3af',
        };
        ctx.fillStyle = colors[node.color] || '#fff';
        ctx.fillRect(node.x, node.y, 4 / zoom, node.h);
      }

      if (node.done) {
        ctx.fillStyle = '#34d399';
        ctx.beginPath();
        ctx.arc(node.x + node.w - 16 / zoom, node.y + 16 / zoom, 6 / zoom, 0, Math.PI * 2);
        ctx.fill();
      }

      const fontSize = Math.max(10, 12 / zoom);
      ctx.font = `600 ${fontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = theme.text;
      ctx.textBaseline = 'top';
      const title = node.title || '';
      const maxTitleW = node.w - 24 / zoom;
      ctx.fillText(title, node.x + 12 / zoom, node.y + 10 / zoom, maxTitleW);

      const kindFontSize = Math.max(8, 10 / zoom);
      ctx.font = `500 ${kindFontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = theme.textSecondary;
      const kindLabels = { note: '便签', evidence: '证据', hook: '钩子', outline: '结构', question: '待验证', link: '链接' };
      ctx.fillText(kindLabels[node.kind] || node.kind, node.x + 12 / zoom, node.y + node.h - 20 / zoom);

      if (node.text) {
        const textFontSize = Math.max(8, 11 / zoom);
        ctx.font = `400 ${textFontSize}px -apple-system, sans-serif`;
        ctx.fillStyle = theme.textTertiary;
        const lines = node.text.split('\n').slice(0, 3);
        lines.forEach((line, i) => {
          ctx.fillText(
            line.slice(0, 30),
            node.x + 12 / zoom,
            node.y + 32 / zoom + i * (textFontSize + 4 / zoom),
            node.w - 24 / zoom
          );
        });
      }
    });
  }

  _drawSelectionBox(ctx) {
    if (!this.selectionBox) return;
    const box = this._normalizeBox(this.selectionBox);
    ctx.fillStyle = 'rgba(59,130,246,0.1)';
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 1 / this.viewport.zoom;
    ctx.setLineDash([4 / this.viewport.zoom, 4 / this.viewport.zoom]);
    ctx.fillRect(box.x, box.y, box.w, box.h);
    ctx.strokeRect(box.x, box.y, box.w, box.h);
    ctx.setLineDash([]);
  }

  _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  startRenderLoop() {
    const loop = () => {
      this.render();
      this.animationFrame = requestAnimationFrame(loop);
    };
    loop();
  }

  stopRenderLoop() {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
    }
  }

  destroy() {
    this.stopRenderLoop();
    this.canvas.remove();
  }
}
