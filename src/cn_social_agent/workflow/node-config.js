class NodeConfig {
  constructor(container) {
    this.container = container;
    this.currentNode = null;
    this.onSave = null;
    this.onDelete = null;
    this.renderEmpty();
  }

  renderEmpty() {
    this.container.innerHTML = '<div style="padding:20px;color:var(--muted);font-size:13px;">点击节点查看配置</div>';
    this.container.style.cssText = 'width:280px;background:var(--panel);border-left:1px solid var(--line);overflow-y:auto;';
  }

  render(node) {
    this.currentNode = node;
    if (!node) {
      this.renderEmpty();
      return;
    }

    const typeInfo = window.NodeTypes[node.type] || { label: node.type, icon: '?' };

    this.container.innerHTML = `
      <div style="padding:16px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
          <span style="font-size:24px;">${typeInfo.icon}</span>
          <div>
            <div style="font-size:14px;font-weight:600;">${typeInfo.label}</div>
            <div style="font-size:11px;color:var(--muted);">${node.type}</div>
          </div>
        </div>

        <div style="margin-bottom:12px;">
          <label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">标签</label>
          <input type="text" id="nodeLabel" value="${node.label || ''}" placeholder="自定义标签"
            style="width:100%;padding:8px;border:1px solid var(--line);border-radius:6px;font-size:13px;background:var(--bg);color:var(--ink);" />
        </div>

        <div id="nodeConfigFields"></div>

        <div style="display:flex;gap:8px;margin-top:16px;">
          <button id="nodeSaveBtn" class="primary" style="flex:1;padding:8px;border:none;border-radius:6px;cursor:pointer;font-size:13px;">保存</button>
          <button id="nodeDeleteBtn" style="padding:8px 12px;border:1px solid var(--danger);border-radius:6px;cursor:pointer;font-size:13px;color:var(--danger);background:transparent;">删除</button>
        </div>
      </div>
    `;

    this._renderConfigFields(node);

    document.getElementById('nodeSaveBtn').addEventListener('click', () => {
      node.label = document.getElementById('nodeLabel').value;
      this._readConfigFields(node);
      if (this.onSave) this.onSave(node);
    });

    document.getElementById('nodeDeleteBtn').addEventListener('click', () => {
      if (this.onDelete) this.onDelete(node);
    });
  }

  _renderConfigFields(node) {
    const container = document.getElementById('nodeConfigFields');
    if (!container) return;

    const config = node.config || {};
    const fields = this._getFieldsForType(node.type);

    container.innerHTML = fields.map(field => {
      const value = config[field.key] || '';
      if (field.type === 'select') {
        return `
          <div style="margin-bottom:12px;">
            <label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">${field.label}</label>
            <select data-field="${field.key}" style="width:100%;padding:8px;border:1px solid var(--line);border-radius:6px;font-size:13px;background:var(--bg);color:var(--ink);">
              ${field.options.map(opt => `<option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>${opt.label}</option>`).join('')}
            </select>
          </div>
        `;
      }
      if (field.type === 'textarea') {
        return `
          <div style="margin-bottom:12px;">
            <label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">${field.label}</label>
            <textarea data-field="${field.key}" rows="3" placeholder="${field.placeholder || ''}"
              style="width:100%;padding:8px;border:1px solid var(--line);border-radius:6px;font-size:13px;background:var(--bg);color:var(--ink);resize:vertical;">${value}</textarea>
          </div>
        `;
      }
      return `
        <div style="margin-bottom:12px;">
          <label style="display:block;font-size:12px;font-weight:500;margin-bottom:4px;">${field.label}</label>
          <input type="${field.type || 'text'}" data-field="${field.key}" value="${value}" placeholder="${field.placeholder || ''}"
            style="width:100%;padding:8px;border:1px solid var(--line);border-radius:6px;font-size:13px;background:var(--bg);color:var(--ink);" />
        </div>
      `;
    }).join('');
  }

  _getFieldsForType(type) {
    const configs = {
      'trigger.schedule': [
        { key: 'cron', label: 'Cron 表达式', placeholder: '0 9 * * *' },
      ],
      'trigger.webhook': [
        { key: 'path', label: '路径', placeholder: '/hook/my-workflow' },
      ],
      'action.hotspot_scan': [
        { key: 'source', label: '来源', type: 'select', options: [
          { value: 'all', label: '全部' },
          { value: 'github', label: 'GitHub' },
          { value: 'hn', label: 'Hacker News' },
        ]},
        { key: 'limit', label: '数量', type: 'number', placeholder: '5' },
      ],
      'action.llm_generate': [
        { key: 'prompt', label: 'Prompt', type: 'textarea', placeholder: '输入提示词...' },
        { key: 'model', label: '模型', type: 'select', options: [
          { value: 'smart', label: '智能' },
          { value: 'fast', label: '快速' },
        ]},
        { key: 'maxLength', label: '最大长度', type: 'number', placeholder: '1000' },
      ],
      'control.condition': [
        { key: 'expression', label: '条件表达式', placeholder: 'hotspot.score > 70' },
      ],
      'control.delay': [
        { key: 'seconds', label: '秒数', type: 'number', placeholder: '60' },
      ],
    };
    return configs[type] || [];
  }

  _readConfigFields(node) {
    const container = document.getElementById('nodeConfigFields');
    if (!container) return;

    if (!node.config) node.config = {};
    container.querySelectorAll('[data-field]').forEach(el => {
      const key = el.dataset.field;
      node.config[key] = el.value;
    });
  }
}

window.NodeConfig = NodeConfig;
