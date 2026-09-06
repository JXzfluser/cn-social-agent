class NodePalette {
  constructor(container, onDragStart) {
    this.container = container;
    this.onDragStart = onDragStart;
    this.render();
  }

  render() {
    this.container.innerHTML = '';
    this.container.style.cssText = 'width:200px;background:var(--panel);border-right:1px solid var(--line);overflow-y:auto;padding:12px;';

    const searchBox = document.createElement('input');
    searchBox.type = 'text';
    searchBox.placeholder = '搜索节点...';
    searchBox.style.cssText = 'width:100%;padding:8px 12px;margin-bottom:12px;border:1px solid var(--line);border-radius:6px;font-size:13px;background:var(--bg);color:var(--ink);box-sizing:border-box;';
    this.container.appendChild(searchBox);

    const categories = [
      { name: '触发器', types: ['trigger.manual', 'trigger.schedule', 'trigger.webhook', 'trigger.event'] },
      { name: '动作', types: ['action.hotspot_scan', 'action.llm_generate', 'action.evidence_collect', 'action.storyboard', 'action.video_render', 'action.image_gen'] },
      { name: '发布', types: ['publish.weixin', 'publish.toutiao', 'publish.douyin', 'publish.xiaohongshu'] },
      { name: '控制', types: ['control.condition', 'control.delay', 'control.loop', 'control.stop'] },
      { name: '输出', types: ['output.save_project', 'output.notify', 'output.export'] },
    ];

    categories.forEach(cat => {
      const section = document.createElement('div');
      section.style.cssText = 'margin-bottom:16px;';

      const title = document.createElement('div');
      title.textContent = cat.name;
      title.style.cssText = 'font-size:12px;font-weight:600;color:var(--muted);margin-bottom:8px;text-transform:uppercase;';
      section.appendChild(title);

      cat.types.forEach(type => {
        const info = window.NodeTypes[type];
        if (!info) return;

        const item = document.createElement('div');
        item.draggable = true;
        item.dataset.nodeType = type;
        item.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px;margin-bottom:4px;border-radius:6px;cursor:grab;background:var(--bg);border:1px solid var(--line);transition:all 150ms;';
        item.innerHTML = `<span style="font-size:16px;">${info.icon}</span><span style="font-size:13px;">${info.label}</span>`;

        item.addEventListener('dragstart', (e) => {
          e.dataTransfer.setData('text/plain', type);
          item.style.opacity = '0.5';
        });

        item.addEventListener('dragend', () => {
          item.style.opacity = '1';
        });

        item.addEventListener('mouseenter', () => {
          item.style.borderColor = info.color;
          item.style.background = 'var(--panel)';
        });

        item.addEventListener('mouseleave', () => {
          item.style.borderColor = 'var(--line)';
          item.style.background = 'var(--bg)';
        });

        section.appendChild(item);
      });

      this.container.appendChild(section);
    });

    searchBox.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase();
      this.container.querySelectorAll('[data-node-type]').forEach(item => {
        const type = item.dataset.nodeType;
        const info = window.NodeTypes[type];
        const match = !query || type.toLowerCase().includes(query) || (info && info.label.toLowerCase().includes(query));
        item.style.display = match ? 'flex' : 'none';
      });

      this.container.querySelectorAll('div').forEach(section => {
        const items = section.querySelectorAll('[data-node-type]');
        const visibleItems = Array.from(items).filter(i => i.style.display !== 'none');
        if (section.querySelector('div') && !section.querySelector('[data-node-type]')) {
          section.style.display = visibleItems.length > 0 || !query ? 'block' : 'none';
        }
      });
    });
  }
}

window.NodePalette = NodePalette;
