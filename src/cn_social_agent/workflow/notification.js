class WorkflowNotification {
  constructor() {
    this.notifications = [];
    this.container = null;
    this.init();
  }

  init() {
    this.container = document.createElement('div');
    this.container.id = 'workflow-notifications';
    this.container.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 10000;
      max-width: 360px;
    `;
    document.body.appendChild(this.container);
  }

  show(message, type = 'info', duration = 5000) {
    const id = `notif_${Date.now()}`;
    const notif = { id, message, type, time: new Date() };
    this.notifications.unshift(notif);

    const notifEl = document.createElement('div');
    notifEl.id = id;
    notifEl.style.cssText = `
      margin-bottom: 10px;
      padding: 12px 16px;
      border-radius: 6px;
      background: ${this._getBgColor(type)};
      color: ${this._getTextColor(type)};
      border-left: 4px solid ${this._getBorderColor(type)};
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      animation: slideIn 0.3s ease;
      cursor: pointer;
      font-size: 13px;
    `;
    notifEl.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <span>${this._getIcon(type)} ${message}</span>
        <span style="font-size:11px;opacity:0.7;">${new Date().toLocaleTimeString('zh-CN')}</span>
      </div>
    `;
    notifEl.addEventListener('click', () => this.dismiss(id));

    this.container.appendChild(notifEl);

    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
  }

  dismiss(id) {
    const notifEl = document.getElementById(id);
    if (notifEl) {
      notifEl.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => notifEl.remove(), 300);
    }
    this.notifications = this.notifications.filter(n => n.id !== id);
  }

  _getBgColor(type) {
    const colors = {
      success: '#10b981',
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#3b82f6',
    };
    return `${colors[type] || colors.info}15`;
  }

  _getTextColor(type) {
    const colors = {
      success: '#10b981',
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#3b82f6',
    };
    return colors[type] || colors.info;
  }

  _getBorderColor(type) {
    const colors = {
      success: '#10b981',
      error: '#ef4444',
      warning: '#f59e0b',
      info: '#3b82f6',
    };
    return colors[type] || colors.info;
  }

  _getIcon(type) {
    const icons = {
      success: '✓',
      error: '✗',
      warning: '⚠',
      info: 'ℹ',
    };
    return icons[type] || icons.info;
  }

  workflowComplete(workflowName, runId) {
    this.show(`工作流「${workflowName}」运行完成`, 'success');
  }

  workflowFailed(workflowName, error) {
    this.show(`工作流「${workflowName}」运行失败: ${error}`, 'error');
  }

  workflowSaved(workflowName) {
    this.show(`工作流「${workflowName}」已保存`, 'success');
  }
}

window.WorkflowNotification = WorkflowNotification;
window.workflowNotify = new WorkflowNotification();
