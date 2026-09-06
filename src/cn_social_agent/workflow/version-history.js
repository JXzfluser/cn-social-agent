class VersionHistoryPanel {
  constructor(container, workflowId) {
    this.container = container;
    this.workflowId = workflowId;
    this.versions = [];
    this.selectedVersion = null;
    this.init();
  }

  init() {
    this.container.innerHTML = `
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="padding:12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;">
          <span style="font-weight:600;font-size:14px;">版本历史</span>
          <button id="refreshVersionsBtn" style="padding:4px 8px;border:1px solid var(--line);border-radius:4px;cursor:pointer;font-size:12px;background:var(--panel);">刷新</button>
        </div>
        <div id="versionList" style="flex:1;overflow:auto;padding:8px;"></div>
      </div>
    `;

    document.getElementById('refreshVersionsBtn').addEventListener('click', () => this.load());
    this.load();
  }

  async load() {
    if (!this.workflowId) {
      this.renderEmpty('请先选择一个工作流');
      return;
    }
    this.renderEmpty('暂无版本记录 — 版本端点就绪后将自动展示');
  }

  renderList() {
    const list = document.getElementById('versionList');
    if (!list) return;

    if (this.versions.length === 0) {
      this.renderEmpty('暂无版本记录');
      return;
    }

    list.innerHTML = this.versions.map((v, i) => {
      const created = v.thumbnail ? new Date() : new Date();
      return `
        <div class="version-item" data-version-index="${i}" style="padding:10px 12px;margin-bottom:6px;background:var(--bg);border-radius:6px;cursor:pointer;border-left:3px solid var(--line);">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:13px;font-weight:500;">版本 ${i + 1}</span>
            <span style="font-size:11px;color:var(--muted);">${created.toLocaleString('zh-CN')}</span>
          </div>
          <div style="font-size:11px;color:var(--muted);margin-top:4px;">模板: ${v.name || '未命名'}</span>
        </div>
      `;
    }).join('');

    list.querySelectorAll('.version-item').forEach(item => {
      item.addEventListener('click', () => {
        const idx = item.dataset.versionIndex;
        this.selectVersion(this.versions[idx]);
      });
    });
  }

  renderEmpty(msg) {
    const list = document.getElementById('versionList');
    if (list) {
      list.innerHTML = `<div style="padding:16px;color:var(--muted);text-align:center;">${msg}</div>`;
    }
  }

  selectVersion(version) {
    this.selectedVersion = version;

    document.querySelectorAll('.version-item').forEach(item => {
      item.style.background = item.dataset.versionIndex === `${this.versions.indexOf(version)}` ? 'var(--panel)' : 'var(--bg)';
    });

    if (this.onVersionSelect) {
      this.onVersionSelect(version);
    }
  }
}

window.VersionHistoryPanel = VersionHistoryPanel;