class WorkflowEditor {
  constructor() {
    this.currentWorkflow = null;
    this.canvas = null;
    this.palette = null;
    this.config = null;
    this.init();
  }

  init() {
    const view = document.getElementById('viewWorkflow');
    if (!view) return;

    view.innerHTML = `
      <div style="display:flex;height:100%;overflow:hidden;">
        <div id="workflowPalette" style="width:180px;flex-shrink:0;border-right:1px solid var(--line);overflow:auto;background:var(--panel);"></div>
        <div style="flex:1;display:flex;flex-direction:column;min-width:0;">
          <div id="workflowToolbar" style="padding:8px 12px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px;background:var(--panel);">
            <select id="workflowSelect" style="padding:6px 10px;border:1px solid var(--line);border-radius:6px;font-size:13px;background:var(--bg);color:var(--ink);min-width:160px;">
              <option value="">选择工作流...</option>
            </select>
            <button id="workflowNewBtn" style="padding:6px 14px;border:none;border-radius:6px;cursor:pointer;font-size:13px;background:var(--primary);color:white;font-weight:500;">新建</button>
            <button id="workflowSaveBtn" style="padding:6px 14px;border:1px solid var(--line);border-radius:6px;cursor:pointer;font-size:13px;background:var(--bg);">保存</button>
            <button id="workflowRunBtn" style="padding:6px 14px;border:none;border-radius:6px;cursor:pointer;font-size:13px;background:var(--ok);color:white;font-weight:500;">运行</button>
            <div style="flex:1;"></div>
            <button id="workflowMoreBtn" style="padding:6px 12px;border:1px solid var(--line);border-radius:6px;cursor:pointer;font-size:13px;background:var(--bg);">更多 ⋯</button>
          </div>
          <div id="workflowCanvasWrap" style="flex:1;position:relative;background:var(--bg);overflow:hidden;">
            <div id="workflowMinimap" style="position:absolute;bottom:12px;right:12px;width:160px;height:120px;background:var(--panel);border:1px solid var(--line);border-radius:6px;display:none;z-index:10;"></div>
            <div id="workflowNodeThumbnail" style="position:absolute;bottom:12px;left:12px;display:none;z-index:10;"></div>
            <div id="workflowRunResult" style="display:none;position:absolute;bottom:12px;left:12px;right:200px;max-height:200px;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:auto;z-index:10;"></div>
          </div>
        </div>
        <div id="workflowConfig" style="width:260px;border-left:1px solid var(--line);background:var(--panel);flex-shrink:0;overflow:auto;"></div>
      </div>
      <div id="workflowSidebar" style="position:fixed;right:0;top:56px;bottom:0;width:320px;background:var(--panel);border-left:1px solid var(--line);z-index:100;display:none;box-shadow:-2px 0 8px rgba(0,0,0,0.1);">
        <div style="padding:12px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;">
          <span id="sidebarTitle" style="font-weight:600;font-size:14px;"></span>
          <button id="closeSidebar" style="background:none;border:none;cursor:pointer;font-size:20px;color:var(--muted);line-height:1;">×</button>
        </div>
        <div id="sidebarContent" style="flex:1;overflow:auto;height:calc(100% - 50px);"></div>
      </div>
    `;

    this.canvas = new WorkflowCanvas(document.getElementById('workflowCanvasWrap'));
    this.palette = new NodePalette(document.getElementById('workflowPalette'));
    this.config = new NodeConfig(document.getElementById('workflowConfig'));
    this.enhancements = new WorkflowEnhancements(this.canvas);
    this.minimap = new Minimap(document.getElementById('workflowMinimap'), this.canvas);
    this.nodeThumbnail = new NodeThumbnail(document.getElementById('workflowNodeThumbnail'));
    this.flowAnimation = new FlowAnimation(this.canvas.svg);

    this.canvas.onSelect = (node) => this.config.render(node);
    this.canvas.onEdgeAdd = (edge) => this._onEdgeAdd(edge);
    this.canvas.onNodeHover = (node) => {
      if (node) {
        this.nodeThumbnail.show(node);
      } else {
        this.nodeThumbnail.hide();
      }
    };

    this.config.onSave = (node) => this._onNodeSave(node);
    this.config.onDelete = (node) => this._onNodeDelete(node);

    this._initDropZone();
    this._initToolbar();
    this._initKeyboard();
    this._loadWorkflows();
  }

  _initDropZone() {
    const wrap = document.getElementById('workflowCanvasWrap');
    wrap.addEventListener('dragover', (e) => e.preventDefault());
    wrap.addEventListener('drop', (e) => {
      e.preventDefault();
      const type = e.dataTransfer.getData('text/plain');
      if (!type) return;

      const pos = this.canvas._screenToCanvas(e.clientX, e.clientY);
      const node = {
        id: `node_${Date.now()}`,
        type: type,
        position: { x: pos.x - 90, y: pos.y - 40 },
        config: {},
      };
      this.canvas.addNode(node);
      this._autoSave();
    });
  }

  _initKeyboard() {
    document.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        if (e.shiftKey) {
          this.enhancements.redo();
        } else {
          this.enhancements.undo();
        }
      }

      if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
        if (this.canvas.selectedNode) {
          this.enhancements.copyNode(this.canvas.selectedNode);
        }
      }

      if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
        this.enhancements.pasteNode();
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        this.enhancements.deleteSelected();
      }

      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        this._saveWorkflow();
      }
    });
  }

  _initToolbar() {
    document.getElementById('workflowSelect').addEventListener('change', (e) => {
      const id = e.target.value;
      if (id) this._loadWorkflow(id);
    });
    document.getElementById('workflowNewBtn').addEventListener('click', () => this._createWorkflow());
    document.getElementById('workflowSaveBtn').addEventListener('click', () => this._saveWorkflow());
    document.getElementById('workflowRunBtn').addEventListener('click', () => this._runWorkflow());

    const moreBtn = document.getElementById('workflowMoreBtn');
    if (moreBtn) {
      moreBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const existing = document.getElementById('workflowMoreMenu');
        if (existing) { existing.remove(); return; }

        const rect = moreBtn.getBoundingClientRect();
        const menu = document.createElement('div');
        menu.id = 'workflowMoreMenu';
        menu.style.cssText = `position:fixed;top:${rect.bottom + 4}px;right:${window.innerWidth - rect.right}px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:4px 0;z-index:1000;min-width:160px;box-shadow:0 4px 12px rgba(0,0,0,0.15);`;
        const items = [
          { label: '适配画布', action: () => this.canvas.fitView() },
          { label: '版本历史', action: () => this._toggleSidebar('版本历史') },
          { label: '模板市场', action: () => this._toggleSidebar('模板市场') },
          { label: '定时任务', action: () => this._toggleSidebar('定时任务') },
          { label: '小地图', action: () => this.minimap.toggle() },
          { label: '单步执行', action: () => this._singleStepWorkflow() },
          { label: '导出工作流', action: () => this._exportWorkflow() },
          { label: '导入工作流', action: () => this._importWorkflow() },
        ];
        items.forEach(({ label, action }) => {
          const btn = document.createElement('button');
          btn.textContent = label;
          btn.style.cssText = 'display:block;width:100%;text-align:left;padding:8px 16px;border:none;background:none;cursor:pointer;font-size:13px;color:var(--ink);';
          btn.onmouseenter = () => { btn.style.background = 'var(--bg)'; };
          btn.onmouseleave = () => { btn.style.background = 'none'; };
          btn.onclick = () => { menu.remove(); action(); };
          menu.appendChild(btn);
        });
        document.body.appendChild(menu);
        document.addEventListener('click', () => menu.remove(), { once: true });
      });
    }

    const closeBtn = document.getElementById('closeSidebar');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        document.getElementById('workflowSidebar').style.display = 'none';
      });
    }
  }

  _toggleSidebar(title) {
    const sidebar = document.getElementById('workflowSidebar');
    const content = document.getElementById('sidebarContent');
    const titleEl = document.getElementById('sidebarTitle');
    if (sidebar.style.display === 'flex') {
      sidebar.style.display = 'none';
      return;
    }
    titleEl.textContent = title;
    content.innerHTML = '';
    if (title === '版本历史') {
      new VersionHistoryPanel(content, this.currentWorkflow?.id);
    } else if (title === '模板市场') {
      new TemplateMarket(content);
    } else if (title === '定时任务') {
      new ScheduleManager(content);
    }
    sidebar.style.display = 'flex';
  }

  async _loadWorkflows() {
    try {
      const data = await window.WorkflowAPI.list();
      const select = document.getElementById('workflowSelect');
      select.innerHTML = '<option value="">选择工作流...</option>';
      (data.workflows || []).forEach(wf => {
        const opt = document.createElement('option');
        opt.value = wf.id;
        opt.textContent = wf.name;
        select.appendChild(opt);
      });
    } catch (err) {
      console.error('Failed to load workflows:', err);
    }
  }

  async _loadWorkflow(id) {
    try {
      const wf = await window.WorkflowAPI.get(id);
      this.currentWorkflow = wf;
      this.canvas.setNodes(wf.nodes || []);
      this.canvas.setEdges(wf.edges || []);
      this.config.renderEmpty();
      setTimeout(() => this.canvas.fitView(), 100);
    } catch (err) {
      console.error('Failed to load workflow:', err);
    }
  }

  async _createWorkflow() {
    const name = prompt('工作流名称:', '新建工作流');
    if (!name) return;

    try {
      const wf = await window.WorkflowAPI.create({ name, nodes: [], edges: [] });
      this.currentWorkflow = wf;
      this.canvas.setNodes([]);
      this.canvas.setEdges([]);
      await this._loadWorkflows();
      document.getElementById('workflowSelect').value = wf.id;
    } catch (err) {
      console.error('Failed to create workflow:', err);
    }
  }

  async _saveWorkflow() {
    if (!this.currentWorkflow) return;

    try {
      await window.WorkflowAPI.update(this.currentWorkflow.id, {
        name: this.currentWorkflow.name,
        nodes: this.canvas.nodes,
        edges: this.canvas.edges,
      });

      if (window.workflowNotify) {
        window.workflowNotify.workflowSaved(this.currentWorkflow.name);
      }
    } catch (err) {
      console.error('Failed to save workflow:', err);
    }
  }

  async _autoSave() {
    if (!this.currentWorkflow) return;
    await this._saveWorkflow();
  }

  async _runWorkflow() {
    if (!this.currentWorkflow) return;

    const runBtn = document.getElementById('workflowRunBtn');
    runBtn.disabled = true;
    runBtn.textContent = '运行中...';

    this.enhancements.clearNodeStatuses();
    this.canvas.nodes.forEach(n => this.enhancements.setNodeStatus(n.id, 'pending'));

    const resultPanel = document.getElementById('workflowRunResult');
    resultPanel.style.display = 'block';
    resultPanel.innerHTML = '<div style="padding:16px;color:var(--muted);">运行中...</div>';

    try {
      const result = await window.WorkflowAPI.run(this.currentWorkflow.id);

      if (result.nodeStates) {
        for (const [nodeId, state] of Object.entries(result.nodeStates)) {
          this.enhancements.setNodeStatus(nodeId, state.status || 'pending');
        }
      }

      this._showRunResult(result);
    } catch (err) {
      resultPanel.innerHTML = `<div style="padding:16px;color:#ef4444;">运行失败: ${err.message}</div>`;
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = '运行';
    }
  }

  _showRunResult(result) {
    const panel = document.getElementById('workflowRunResult');
    const statusColor = result.status === 'success' ? '#22c55e' : '#ef4444';
    const statusText = result.status === 'success' ? '成功' : '失败';

    if (window.workflowNotify) {
      if (result.status === 'success') {
        window.workflowNotify.workflowComplete(this.currentWorkflow?.name || '工作流', result.id);
      } else {
        window.workflowNotify.workflowFailed(this.currentWorkflow?.name || '工作流', result.error || '未知错误');
      }
    }

    let html = `
      <div style="padding:12px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-weight:600;font-size:14px;">运行结果</span>
          <span style="margin-left:8px;padding:2px 8px;border-radius:4px;font-size:12px;background:${statusColor}20;color:${statusColor};">${statusText}</span>
        </div>
        <button onclick="document.getElementById('workflowRunResult').style.display='none'" style="background:none;border:none;cursor:pointer;font-size:18px;color:var(--muted);">×</button>
      </div>
      <div style="padding:12px 16px;font-size:12px;color:var(--muted);border-bottom:1px solid var(--line);">
        触发方式: ${result.triggerType} | 开始: ${result.startedAt} | 结束: ${result.finishedAt || '-'}
        ${result.error ? `<br>错误: <span style="color:#ef4444;">${result.error}</span>` : ''}
      </div>
      <div style="padding:12px 16px;">
    `;

    if (result.nodeStates) {
      for (const [nodeId, state] of Object.entries(result.nodeStates)) {
        const node = this.canvas.nodes.find(n => n.id === nodeId);
        const nodeName = node?.label || nodeId;
        const statusIcon = state.status === 'done' ? '✓' : state.status === 'failed' ? '✗' : '○';
        const statusColor = state.status === 'done' ? '#22c55e' : state.status === 'failed' ? '#ef4444' : '#94a3b8';

        html += `
          <div style="margin-bottom:8px;padding:8px 12px;background:var(--bg);border-radius:6px;border-left:3px solid ${statusColor};">
            <div style="display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:13px;font-weight:500;">
                <span style="color:${statusColor};margin-right:6px;">${statusIcon}</span>
                ${nodeName}
              </span>
              <span style="font-size:11px;color:var(--muted);">${state.durationMs || 0}ms</span>
            </div>
            ${state.output ? `<pre style="margin:6px 0 0;padding:8px;background:var(--panel);border-radius:4px;font-size:11px;overflow-x:auto;max-height:120px;overflow-y:auto;">${JSON.stringify(state.output, null, 2)}</pre>` : ''}
            ${state.error ? `<div style="margin-top:6px;font-size:12px;color:#ef4444;">${state.error}</div>` : ''}
          </div>
        `;
      }
    }

    html += '</div>';
    panel.innerHTML = html;
  }

  _onNodeSave(node) {
    this._autoSave();
  }

  _onNodeDelete(node) {
    this.canvas.removeNode(node.id);
    this._autoSave();
  }

  _onEdgeAdd(edge) {
    this._autoSave();
  }

  async _singleStepWorkflow() {
    if (!this.currentWorkflow) return;

    const runBtn = document.getElementById('workflowRunBtn');
    runBtn.disabled = true;
    runBtn.textContent = '单步执行中...';

    this.enhancements.clearNodeStatuses();
    this.canvas.nodes.forEach(n => this.enhancements.setNodeStatus(n.id, 'pending'));

    try {
      const result = await window.WorkflowAPI.run(this.currentWorkflow.id, {}, true);

      if (result.nodeStates) {
        for (const [nodeId, state] of Object.entries(result.nodeStates)) {
          this.enhancements.setNodeStatus(nodeId, state.status || 'pending');
        }
      }

      if (result.status === 'success' || result.status === 'stopped') {
        // Single step stopped after one node, show result and ask if continue
        const finishedNode = Object.keys(result.nodeStates).find(k => result.nodeStates[k].status === 'done');
        if (finishedNode) {
          alert(`单步执行完成！\n已执行节点: ${finishedNode}\n状态: ${result.nodeStates[finishedNode].status}`);
        }
      }
    } catch (err) {
      alert(`单步执行失败: ${err.message}`);
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = '单步';
    }
  }

  async _exportWorkflow() {
    if (!this.currentWorkflow) return;

    try {
      const data = await window.WorkflowAPI.exportWorkflow(this.currentWorkflow.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${this.currentWorkflow.name || 'workflow'}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('导出失败: ' + err.message);
    }
  }

  async _importWorkflow() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      try {
        const text = await file.text();
        const data = JSON.parse(text);
        const result = await window.WorkflowAPI.importWorkflow(data);
        await this._loadWorkflows();
        document.getElementById('workflowSelect').value = result.id;
        this._loadWorkflow(result.id);
        alert('导入成功');
      } catch (err) {
        alert('导入失败: ' + err.message);
      }
    };
    input.click();
  }
}

window.WorkflowEditor = WorkflowEditor;
