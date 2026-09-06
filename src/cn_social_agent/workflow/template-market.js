class TemplateMarket {
  constructor(container) {
    this.container = container;
    this.templates = [];
    this.selectedCategory = 'all';
    this.init();
  }

  init() {
    this.container.innerHTML = `
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="padding:12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;">
          <span style="font-weight:600;font-size:14px;">模板市场</span>
          <button id="refreshTemplatesBtn" style="padding:4px 8px;border:1px solid var(--line);border-radius:4px;cursor:pointer;font-size:12px;background:var(--panel);">刷新</button>
        </div>
        <div style="padding:8px;border-bottom:1px solid var(--line);">
          <select id="templateCategoryFilter" style="width:100%;padding:6px;border:1px solid var(--line);border-radius:4px;font-size:12px;background:var(--panel);">
            <option value="all">全部类别</option>
            <option value="content">内容创作</option>
            <option value="automation">自动化</option>
            <option value="social">社交媒体</option>
          </select>
        </div>
        <div id="templateList" style="flex:1;overflow:auto;padding:8px;"></div>
      </div>
    `;

    document.getElementById('refreshTemplatesBtn').addEventListener('click', () => this.load());
    document.getElementById('templateCategoryFilter').addEventListener('change', (e) => {
      this.selectedCategory = e.target.value;
      this.renderList();
    });

    this.load();
  }

  async load() {
    try {
      const data = await window.WorkflowAPI.listTemplates();
      this.templates = data.templates || [];
      this.renderList();
    } catch (err) {
      console.error('Failed to load templates:', err);
      this.renderEmpty('加载模板失败');
    }
  }

  renderList() {
    const list = document.getElementById('templateList');
    if (!list) return;

    if (this.templates.length === 0) {
      this.renderEmpty('暂无模板');
      return;
    }

    const filtered = this.templates.filter(t => 
      this.selectedCategory === 'all' || t.category === this.selectedCategory
    );

    if (filtered.length === 0) {
      this.renderEmpty('该类别暂无模板');
      return;
    }

    list.innerHTML = filtered.map(t => {
      const category = t.category || 'other';
      const categoryLabel = {
        'content': '内容创作',
        'automation': '自动化',
        'social': '社交媒体',
        'other': '其他'
      }[category] || category;

      return `
        <div class="template-item" data-template-id="${t.id}" style="padding:10px 12px;margin-bottom:6px;background:var(--bg);border-radius:6px;cursor:pointer;border-left:3px solid var(--line);">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:13px;font-weight:500;">${t.name}</span>
            <span style="font-size:10px;padding:2px 6px;background:var(--panel);border-radius:4px;color:var(--muted);">${categoryLabel}</span>
          </div>
          <div style="font-size:11px;color:var(--muted);margin-top:4px;">${t.description || '暂无描述'}</div>
        </div>
      `;
    }).join('');

    list.querySelectorAll('.template-item').forEach(item => {
      item.addEventListener('click', () => {
        const templateId = item.dataset.templateId;
        this.selectTemplate(templateId);
      });
    });
  }

  renderEmpty(msg) {
    const list = document.getElementById('templateList');
    if (list) {
      list.innerHTML = `<div style="padding:16px;color:var(--muted);text-align:center;">${msg}</div>`;
    }
  }

  selectTemplate(templateId) {
    const template = this.templates.find(t => t.id === templateId);
    if (!template) return;

    
    document.querySelectorAll('.template-item').forEach(item => {
      item.style.background = item.dataset.templateId === templateId ? 'var(--panel)' : 'var(--bg)';
    });

    if (this.onTemplateSelect) {
      this.onTemplateSelect(template);
    }
  }
}

window.TemplateMarket = TemplateMarket;
