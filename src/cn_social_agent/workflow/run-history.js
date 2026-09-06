class RunHistoryPanel {
  constructor(container, workflowId) {
    this.container = container;
    this.workflowId = workflowId;
    this.runs = [];
    this.selectedRun = null;
    this.init();
  }

  init() {
    this.container.innerHTML = `
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="padding:12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;">
          <span style="font-weight:600;font-size:14px;">运行历史</span>
          <button id="refreshRunsBtn" style="padding:4px 8px;border:1px solid var(--line);border-radius:4px;cursor:pointer;font-size:12px;background:var(--panel);">刷新</button>
        </div>
        <div id="runHistoryList" style="flex:1;overflow:auto;padding:8px;"></div>
      </div>
    `;

    document.getElementById('refreshRunsBtn').addEventListener('click', () => this.load());
    this.load();
  }

  async load() {
    if (!this.workflowId) return;

    try {
      const data = await window.WorkflowAPI.listRuns(this.workflowId);
      this.runs = data.runs || [];
      this.renderList();
    } catch (err) {
      console.error('Failed to load run history:', err);
    }
  }

  renderList() {
    const list = document.getElementById('runHistoryList');
    if (!list) return;

    if (this.runs.length === 0) {
      list.innerHTML = '<div style="padding:16px;color:var(--muted);text-align:center;">暂无运行记录</div>';
      return;
    }

    list.innerHTML = this.runs.map(run => {
      const statusColor = run.status === 'success' ? '#22c55e' : run.status === 'failed' ? '#ef4444' : '#94a3b8';
      const statusText = run.status === 'success' ? '成功' : run.status === 'failed' ? '失败' : run.status;
      const time = new Date(run.startedAt).toLocaleString('zh-CN');

      return `
        <div class="run-item" data-run-id="${run.id}" style="padding:10px 12px;margin-bottom:6px;background:var(--bg);border-radius:6px;cursor:pointer;border-left:3px solid ${statusColor};">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:13px;font-weight:500;">${statusText}</span>
            <span style="font-size:11px;color:var(--muted);">${run.triggerType}</span>
          </div>
          <div style="font-size:11px;color:var(--muted);margin-top:4px;">${time}</div>
        </div>
      `;
    }).join('');

    list.querySelectorAll('.run-item').forEach(item => {
      item.addEventListener('click', () => {
        const runId = item.dataset.runId;
        this.selectRun(runId);
      });
    });
  }

  async selectRun(runId) {
    const run = this.runs.find(r => r.id === runId);
    if (!run) return;

    this.selectedRun = run;

    const list = document.getElementById('runHistoryList');
    if (list) {
      list.querySelectorAll('.run-item').forEach(item => {
        item.style.background = item.dataset.runId === runId ? 'var(--panel)' : 'var(--bg)';
      });
    }

    if (this.onRunSelect) {
      this.onRunSelect(run);
    }
  }

  setWorkflowId(workflowId) {
    this.workflowId = workflowId;
    this.load();
  }
}

window.RunHistoryPanel = RunHistoryPanel;
