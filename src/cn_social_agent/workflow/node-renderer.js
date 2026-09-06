const NodeTypes = {
  'trigger.manual': { label: '手动触发', icon: '▶', color: '#f97316', category: 'trigger' },
  'trigger.schedule': { label: '定时触发', icon: '⏰', color: '#f97316', category: 'trigger' },
  'trigger.webhook': { label: 'Webhook', icon: 'hook', color: '#f97316', category: 'trigger' },
  'trigger.event': { label: '事件触发', icon: '⚡', color: '#f97316', category: 'trigger' },
  'action.hotspot_scan': { label: '热点扫描', icon: '🔥', color: '#3b82f6', category: 'action' },
  'action.llm_generate': { label: 'LLM 生成', icon: '✨', color: '#3b82f6', category: 'action' },
  'action.evidence_collect': { label: '素材采集', icon: '📎', color: '#3b82f6', category: 'action' },
  'action.storyboard': { label: '生成分镜', icon: '🎬', color: '#3b82f6', category: 'action' },
  'action.video_render': { label: '视频渲染', icon: '🎥', color: '#3b82f6', category: 'action' },
  'action.image_gen': { label: '图片生成', icon: '🖼', color: '#3b82f6', category: 'action' },
  'publish.weixin': { label: '发微信', icon: '💬', color: '#22c55e', category: 'publish' },
  'publish.toutiao': { label: '发头条', icon: '📰', color: '#22c55e', category: 'publish' },
  'publish.douyin': { label: '发抖音', icon: '🎵', color: '#22c55e', category: 'publish' },
  'publish.xiaohongshu': { label: '发小红书', icon: '📕', color: '#22c55e', category: 'publish' },
  'control.condition': { label: '条件判断', icon: '❓', color: '#a855f7', category: 'control' },
  'control.delay': { label: '延时', icon: '⏳', color: '#a855f7', category: 'control' },
  'control.loop': { label: '循环', icon: '🔄', color: '#a855f7', category: 'control' },
  'control.stop': { label: '停止', icon: '⏹', color: '#a855f7', category: 'control' },
  'output.save_project': { label: '保存项目', icon: '💾', color: '#6b7280', category: 'output' },
  'output.notify': { label: '通知', icon: '🔔', color: '#6b7280', category: 'output' },
  'output.export': { label: '导出', icon: '📤', color: '#6b7280', category: 'output' },
};

const NodeRenderer = {
  render(node, selected) {
    const typeInfo = NodeTypes[node.type] || { label: node.type, icon: '?', color: '#6b7280' };
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('transform', `translate(${node.position.x}, ${node.position.y})`);
    g.setAttribute('data-node-id', node.id);
    g.classList.add('workflow-node');

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('width', '180');
    rect.setAttribute('height', '80');
    rect.setAttribute('rx', '8');
    rect.setAttribute('fill', selected ? '#f0fdfa' : '#ffffff');
    rect.setAttribute('stroke', selected ? '#0f766e' : typeInfo.color);
    rect.setAttribute('stroke-width', selected ? '3' : '2');
    rect.style.filter = 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))';
    g.appendChild(rect);

    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    icon.setAttribute('x', '12');
    icon.setAttribute('y', '32');
    icon.setAttribute('font-size', '20');
    icon.textContent = typeInfo.icon;
    g.appendChild(icon);

    const title = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    title.setAttribute('x', '40');
    title.setAttribute('y', '28');
    title.setAttribute('font-size', '14');
    title.setAttribute('font-weight', '600');
    title.setAttribute('fill', '#1a1a2e');
    title.textContent = node.label || typeInfo.label;
    g.appendChild(title);

    const config = this._getConfigSummary(node);
    if (config) {
      const configText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      configText.setAttribute('x', '40');
      configText.setAttribute('y', '50');
      configText.setAttribute('font-size', '11');
      configText.setAttribute('fill', '#6b7280');
      configText.textContent = config;
      g.appendChild(configText);
    }

    const inputPort = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    inputPort.setAttribute('cx', '0');
    inputPort.setAttribute('cy', '40');
    inputPort.setAttribute('r', '6');
    inputPort.setAttribute('fill', '#ffffff');
    inputPort.setAttribute('stroke', typeInfo.color);
    inputPort.setAttribute('stroke-width', '2');
    inputPort.classList.add('node-input');
    inputPort.dataset.nodeId = node.id;
    inputPort.dataset.portType = 'input';
    inputPort.style.cursor = 'pointer';
    g.appendChild(inputPort);

    const outputPort = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    outputPort.setAttribute('cx', '180');
    outputPort.setAttribute('cy', '40');
    outputPort.setAttribute('r', '6');
    outputPort.setAttribute('fill', typeInfo.color);
    outputPort.setAttribute('stroke', '#ffffff');
    outputPort.setAttribute('stroke-width', '2');
    outputPort.classList.add('node-output');
    outputPort.dataset.nodeId = node.id;
    outputPort.dataset.portType = 'output';
    outputPort.style.cursor = 'pointer';
    g.appendChild(outputPort);

    return g;
  },

  _getConfigSummary(node) {
    const config = node.config || {};
    const parts = [];
    if (config.source) parts.push(`source: ${config.source}`);
    if (config.limit) parts.push(`limit: ${config.limit}`);
    if (config.cron) parts.push(`cron: ${config.cron}`);
    if (config.prompt) parts.push('prompt: ...');
    if (config.seconds) parts.push(`${config.seconds}s`);
    return parts.join(' · ').slice(0, 30);
  }
};

window.NodeTypes = NodeTypes;
window.NodeRenderer = NodeRenderer;
