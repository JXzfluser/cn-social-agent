class WorkflowCanvas {
  constructor(container) {
    this.container = container;
    this.nodes = [];
    this.edges = [];
    this.selectedNode = null;
    this.scale = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    this.isPanning = false;
    this.isDragging = false;
    this.dragNode = null;
    this.dragStart = { x: 0, y: 0 };
    this.connecting = false;
    this.connectStart = null;

    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.style.cssText = 'width:100%;height:100%;cursor:grab;';
    this.container.appendChild(this.svg);

    this.gridGroup = this._createGroup('grid');
    this.edgesGroup = this._createGroup('edges');
    this.nodesGroup = this._createGroup('nodes');
    this.tempGroup = this._createGroup('temp');

    this._initEvents();
    this._drawGrid();
  }

  _createGroup(id) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('id', id);
    this.svg.appendChild(g);
    return g;
  }

  _initEvents() {
    this.svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const rect = this.svg.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;
      this._zoom(delta, cx, cy);
    });

    this.svg.addEventListener('mousedown', (e) => {
      if (e.button === 1 || (e.button === 0 && e.ctrlKey)) {
        this.isPanning = true;
        this.dragStart = { x: e.clientX - this.offsetX, y: e.clientY - this.offsetY };
        this.svg.style.cursor = 'grabbing';
        e.preventDefault();
      }
    });

    this.svg.addEventListener('mousemove', (e) => {
      if (this.isPanning) {
        this.offsetX = e.clientX - this.dragStart.x;
        this.offsetY = e.clientY - this.dragStart.y;
        this._updateTransform();
      } else if (this.isDragging && this.dragNode) {
        const pos = this._screenToCanvas(e.clientX, e.clientY);
        this.dragNode.position.x = pos.x - this.dragOffset.x;
        this.dragNode.position.y = pos.y - this.dragOffset.y;
        this._renderNodes();
        this._renderEdges();
      } else if (this.connecting) {
        const pos = this._screenToCanvas(e.clientX, e.clientY);
        this._drawTempEdge(pos);
      }
    });

    this.svg.addEventListener('mouseup', (e) => {
      if (this.isPanning) {
        this.isPanning = false;
        this.svg.style.cursor = 'grab';
      }
      if (this.isDragging) {
        this.isDragging = false;
        this.dragNode = null;
      }
      if (this.connecting) {
        this._finishConnect(e);
      }
    });

    this.svg.addEventListener('click', (e) => {
      if (e.target === this.svg || e.target.parentElement === this.gridGroup) {
        this.selectNode(null);
      }
    });
  }

  _zoom(factor, cx, cy) {
    const newScale = Math.max(0.2, Math.min(3, this.scale * factor));
    const ratio = newScale / this.scale;
    this.offsetX = cx - (cx - this.offsetX) * ratio;
    this.offsetY = cy - (cy - this.offsetY) * ratio;
    this.scale = newScale;
    this._updateTransform();
  }

  _updateTransform() {
    const transform = `translate(${this.offsetX}px, ${this.offsetY}px) scale(${this.scale})`;
    [this.gridGroup, this.edgesGroup, this.nodesGroup, this.tempGroup].forEach(g => {
      g.setAttribute('transform', `translate(${this.offsetX},${this.offsetY}) scale(${this.scale})`);
    });
  }

  _screenToCanvas(sx, sy) {
    const rect = this.svg.getBoundingClientRect();
    return {
      x: (sx - rect.left - this.offsetX) / this.scale,
      y: (sy - rect.top - this.offsetY) / this.scale,
    };
  }

  _drawGrid() {
    const step = 20;
    const size = 2000;
    for (let x = -size; x <= size; x += step) {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x);
      line.setAttribute('y1', -size);
      line.setAttribute('x2', x);
      line.setAttribute('y2', size);
      line.setAttribute('stroke', '#e5e7eb');
      line.setAttribute('stroke-width', '0.5');
      this.gridGroup.appendChild(line);
    }
    for (let y = -size; y <= size; y += step) {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', -size);
      line.setAttribute('y1', y);
      line.setAttribute('x2', size);
      line.setAttribute('y2', y);
      line.setAttribute('stroke', '#e5e7eb');
      line.setAttribute('stroke-width', '0.5');
      this.gridGroup.appendChild(line);
    }
  }

  setNodes(nodes) {
    this.nodes = nodes || [];
    this._renderNodes();
    this._renderEdges();
  }

  setEdges(edges) {
    this.edges = edges || [];
    this._renderEdges();
  }

  addNode(node) {
    this.nodes.push(node);
    this._renderNodes();
    return node;
  }

  removeNode(nodeId) {
    this.nodes = this.nodes.filter(n => n.id !== nodeId);
    this.edges = this.edges.filter(e => e.source !== nodeId && e.target !== nodeId);
    if (this.selectedNode && this.selectedNode.id === nodeId) {
      this.selectNode(null);
    }
    this._renderNodes();
    this._renderEdges();
  }

  addEdge(edge) {
    const exists = this.edges.some(e => e.source === edge.source && e.target === edge.target);
    if (!exists) {
      this.edges.push(edge);
      this._renderEdges();
    }
  }

  removeEdge(edgeId) {
    this.edges = this.edges.filter(e => e.id !== edgeId);
    this._renderEdges();
  }

  selectNode(node) {
    this.selectedNode = node;
    this._renderNodes();
    if (this.onSelect) this.onSelect(node);
  }

  startConnect(nodeId, portType) {
    this.connecting = true;
    this.connectStart = { nodeId, portType };
    this.svg.style.cursor = 'crosshair';
  }

  _drawTempEdge(pos) {
    while (this.tempGroup.firstChild) {
      this.tempGroup.removeChild(this.tempGroup.firstChild);
    }
    if (!this.connectStart) return;

    const node = this.nodes.find(n => n.id === this.connectStart.nodeId);
    if (!node) return;

    const startPos = this._getPortPosition(node, this.connectStart.portType);
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${startPos.x} ${startPos.y} L ${pos.x} ${pos.y}`;
    path.setAttribute('d', d);
    path.setAttribute('stroke', '#0f766e');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-dasharray', '5,5');
    this.tempGroup.appendChild(path);
  }

  _finishConnect(e) {
    const target = e.target.closest('.node-output, .node-input');
    if (target) {
      const targetNodeId = target.dataset.nodeId;
      const targetPort = target.dataset.portType;
      if (this.connectStart.nodeId !== targetNodeId) {
        const edge = {
          id: `edge_${Date.now()}`,
          source: this.connectStart.portType === 'output' ? this.connectStart.nodeId : targetNodeId,
          target: this.connectStart.portType === 'output' ? targetNodeId : this.connectStart.nodeId,
        };
        this.addEdge(edge);
        if (this.onEdgeAdd) this.onEdgeAdd(edge);
      }
    }
    this.connecting = false;
    this.connectStart = null;
    this.svg.style.cursor = 'grab';
    while (this.tempGroup.firstChild) {
      this.tempGroup.removeChild(this.tempGroup.firstChild);
    }
  }

  _getPortPosition(node, portType) {
    const nodeWidth = 180;
    const nodeHeight = 80;
    if (portType === 'output') {
      return { x: node.position.x + nodeWidth, y: node.position.y + nodeHeight / 2 };
    }
    return { x: node.position.x, y: node.position.y + nodeHeight / 2 };
  }

  _renderNodes() {
    while (this.nodesGroup.firstChild) {
      this.nodesGroup.removeChild(this.nodesGroup.firstChild);
    }
    this.nodes.forEach(node => {
      const g = window.NodeRenderer.render(node, this.selectedNode?.id === node.id);
      this._attachNodeEvents(g, node);
      this.nodesGroup.appendChild(g);
    });
  }

  _renderEdges() {
    while (this.edgesGroup.firstChild) {
      this.edgesGroup.removeChild(this.edgesGroup.firstChild);
    }
    this.edges.forEach(edge => {
      const sourceNode = this.nodes.find(n => n.id === edge.source);
      const targetNode = this.nodes.find(n => n.id === edge.target);
      if (sourceNode && targetNode) {
        const path = window.EdgeRenderer.render(sourceNode, targetNode);
        this.edgesGroup.appendChild(path);
      }
    });
  }

  _attachNodeEvents(g, node) {
    g.addEventListener('mousedown', (e) => {
      if (e.target.closest('.node-output')) {
        e.stopPropagation();
        this.startConnect(node.id, 'output');
        return;
      }
      if (e.target.closest('.node-input')) {
        return;
      }
      this.isDragging = true;
      this.dragNode = node;
      const pos = this._screenToCanvas(e.clientX, e.clientY);
      this.dragOffset = {
        x: pos.x - node.position.x,
        y: pos.y - node.position.y,
      };
      this.selectNode(node);
    });
  }

  getNodeAtPosition(x, y) {
    return this.nodes.find(n => {
      return x >= n.position.x && x <= n.position.x + 180 &&
             y >= n.position.y && y <= n.position.y + 80;
    });
  }

  fitView() {
    if (this.nodes.length === 0) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    this.nodes.forEach(n => {
      minX = Math.min(minX, n.position.x);
      minY = Math.min(minY, n.position.y);
      maxX = Math.max(maxX, n.position.x + 180);
      maxY = Math.max(maxY, n.position.y + 80);
    });
    const rect = this.svg.getBoundingClientRect();
    const padding = 50;
    const scaleX = (rect.width - padding * 2) / (maxX - minX);
    const scaleY = (rect.height - padding * 2) / (maxY - minY);
    this.scale = Math.min(scaleX, scaleY, 1.5);
    this.offsetX = (rect.width - (maxX - minX) * this.scale) / 2 - minX * this.scale;
    this.offsetY = (rect.height - (maxY - minY) * this.scale) / 2 - minY * this.scale;
    this._updateTransform();
  }
}

window.WorkflowCanvas = WorkflowCanvas;
