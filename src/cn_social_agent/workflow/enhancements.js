class WorkflowEnhancements {
  constructor(canvas) {
    this.canvas = canvas;
    this.history = [];
    this.historyIndex = -1;
    this.maxHistory = 50;
    this.clipboard = null;
    this.gridSize = 20;
    this.snapToGridEnabled = true;
    this.selectedNodes = [];
    this.nodeStatuses = {};
  }

  pushHistory(action, data) {
    this.history = this.history.slice(0, this.historyIndex + 1);
    this.history.push({ action, data, timestamp: Date.now() });
    if (this.history.length > this.maxHistory) this.history.shift();
    this.historyIndex = this.history.length - 1;
  }

  undo() {
    if (this.historyIndex < 0) return null;
    const entry = this.history[this.historyIndex];
    this.historyIndex--;
    return entry;
  }

  redo() {
    if (this.historyIndex >= this.history.length - 1) return null;
    this.historyIndex++;
    const entry = this.history[this.historyIndex];
    return entry;
  }

  canUndo() { return this.historyIndex >= 0; }
  canRedo() { return this.historyIndex < this.history.length - 1; }

  copyNode(node) {
    this.clipboard = JSON.parse(JSON.stringify(node));
  }

  pasteNode() {
    if (!this.clipboard) return null;
    const newNode = {
      ...JSON.parse(JSON.stringify(this.clipboard)),
      id: `node_${Date.now()}`
    };
    if (newNode.position) {
      newNode.position.x += 30;
      newNode.position.y += 30;
    }
    return newNode;
  }

  snapToGridPosition(x, y) {
    if (!this.snapToGridEnabled) return { x, y };
    return {
      x: Math.round(x / this.gridSize) * this.gridSize,
      y: Math.round(y / this.gridSize) * this.gridSize
    };
  }

  toggleSnapToGrid() {
    this.snapToGridEnabled = !this.snapToGridEnabled;
    return this.snapToGridEnabled;
  }

  updateNodePositions() {
    if (!this.snapToGridEnabled) return;
    this.canvas.nodes.forEach(node => {
      const snapped = this.snapToGridPosition(node.position.x, node.position.y);
      node.position.x = snapped.x;
      node.position.y = snapped.y;
    });
    this.canvas._renderNodes();
    this.canvas._renderEdges();
  }

  startGroup() {
    this.selectedNodes = [];
  }

  addToSelection(nodeId) {
    if (this.selectedNodes.includes(nodeId)) {
      this.selectedNodes = this.selectedNodes.filter(id => id !== nodeId);
    } else {
      this.selectedNodes.push(nodeId);
    }
    this._updateSelectionVisual();
  }

  removeFromSelection(nodeId) {
    this.selectedNodes = this.selectedNodes.filter(id => id !== nodeId);
    this._updateSelectionVisual();
  }

  clearSelection() {
    this.selectedNodes = [];
    this._updateSelectionVisual();
  }

  _updateSelectionVisual() {
    if (!this.canvas.nodesGroup) return;
    this.canvas.nodesGroup.querySelectorAll('[data-node-id]').forEach(el => {
      const nodeId = el.getAttribute('data-node-id');
      if (this.selectedNodes.includes(nodeId)) {
        el.classList.add('selected');
      } else {
        el.classList.remove('selected');
      }
    });
  }

  groupSelected() {
    if (this.selectedNodes.length < 2) return null;
    const groupId = `group_${Date.now()}`;
    this.selectedNodes.forEach(id => {
      const node = this.canvas.nodes.find(n => n.id === id);
      if (node) node.groupId = groupId;
    });
    return groupId;
  }

  ungroupSelected() {
    this.selectedNodes.forEach(id => {
      const node = this.canvas.nodes.find(n => n.id === id);
      if (node) delete node.groupId;
    });
  }

  setNodeStatus(nodeId, status) {
    this.nodeStatuses[nodeId] = { status, timestamp: Date.now() };
    this._renderNodeStatus(nodeId);
  }

  clearNodeStatus(nodeId) {
    delete this.nodeStatuses[nodeId];
    this._renderNodeStatus(nodeId);
  }

  _renderNodeStatus(nodeId) {
    const nodeEl = this.canvas.nodesGroup?.querySelector(`[data-node-id="${nodeId}"]`);
    if (!nodeEl) return;

    nodeEl.querySelectorAll('.node-status-indicator').forEach(el => el.remove());
    const status = this.nodeStatuses[nodeId];
    if (!status) return;

    const colors = { running: 'var(--primary)', success: 'var(--ok)', error: 'var(--danger)' };
    const indicator = document.createElement('div');
    indicator.className = 'node-status-indicator';
    indicator.style.cssText = `
      position:absolute;top:-4px;right:-4px;width:10px;height:10px;
      border-radius:50%;background:${colors[status.status] || 'var(--muted)'};
      border:2px solid var(--panel);z-index:5;
    `;
    if (status.status === 'running') {
      indicator.style.animation = 'pulse 1s infinite';
    }
    nodeEl.style.position = 'relative';
    nodeEl.appendChild(indicator);
  }

  clearAllStatuses() {
    this.nodeStatuses = {};
    this.canvas.nodesGroup?.querySelectorAll('.node-status-indicator').forEach(el => el.remove());
  }

  deleteSelected() {
    if (!this.canvas.selectedNode) return;
    const id = this.canvas.selectedNode.id;
    this.canvas.nodes = this.canvas.nodes.filter(n => n.id !== id);
    this.canvas.edges = this.canvas.edges.filter(e => e.source !== id && e.target !== id);
    this.canvas.selectedNode = null;
    this.canvas._renderNodes();
    this.canvas._renderEdges();
  }

  clearNodeStatuses() {
    this.clearAllStatuses();
  }
}

window.WorkflowEnhancements = WorkflowEnhancements;
