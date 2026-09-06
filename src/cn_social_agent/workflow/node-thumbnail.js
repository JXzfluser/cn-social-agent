class NodeThumbnail {
  constructor(container) {
    this.container = container;
    this.node = null;
    this.visible = false;
    this.init();
  }

  init() {
    this.container.style.cssText = `
      position: absolute;
      bottom: 80px;
      left: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      max-width: 200px;
      max-height: 150px;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      display: none;
      z-index: 100;
    `;
  }

  show(node) {
    if (!node) return;
    this.node = node;
    this.visible = true;
    this.render();
    this.container.style.display = 'block';
  }

  hide() {
    this.visible = false;
    this.container.style.display = 'none';
  }

  render() {
    if (!this.node) return;

    const type = this.node.type || 'unknown';
    const label = this.node.label || this.node.id;
    const config = this.node.config || {};

    let content = `
      <div style="font-size:12px;font-weight:600;margin-bottom:8px;">${label}</div>
      <div style="font-size:11px;color:var(--muted);margin-bottom:4px;">类型: ${type}</div>
    `;

    if (type === 'action.llm_generate' && config.prompt) {
      content += `
        <div style="font-size:11px;color:var(--muted);margin-top:8px;">
          <div style="font-weight:500;margin-bottom:4px;">Prompt:</div>
          <div style="max-height:80px;overflow:auto;background:var(--bg);padding:4px;border-radius:4px;">${config.prompt}</div>
        </div>
      `;
    }

    if (type === 'trigger.schedule' && config.cron) {
      content += `
        <div style="font-size:11px;color:var(--muted);margin-top:8px;">
          <div style="font-weight:500;margin-bottom:4px;">Cron:</div>
          <div style="background:var(--bg);padding:4px;border-radius:4px;">${config.cron}</div>
        </div>
      `;
    }

    this.container.innerHTML = content;
  }
}

window.NodeThumbnail = NodeThumbnail;
