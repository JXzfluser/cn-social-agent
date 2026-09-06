class Minimap {
  constructor(container, canvas) {
    this.container = container;
    this.canvas = canvas;
    this.scale = 0.1;
    this.visible = true;
    this.init();
  }

  init() {
    this.container.style.cssText = `
      position: absolute;
      bottom: 80px;
      right: 12px;
      width: 200px;
      height: 150px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      cursor: pointer;
    `;

    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.style.cssText = 'width:100%;height:100%;';
    this.container.appendChild(this.svg);

    this.viewport = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    this.viewport.setAttribute('fill', 'rgba(59, 130, 246, 0.2)');
    this.viewport.setAttribute('stroke', '#3b82f6');
    this.viewport.setAttribute('stroke-width', '1');
    this.svg.appendChild(this.viewport);

    this.container.addEventListener('click', (e) => this.handleClick(e));
  }

  update() {
    if (!this.visible) return;

    while (this.svg.firstChild) {
      this.svg.removeChild(this.svg.firstChild);
    }

    this.svg.appendChild(this.viewport);

    const nodes = this.canvas.nodes || [];
    const edges = this.canvas.edges || [];

    edges.forEach(edge => {
      const source = nodes.find(n => n.id === edge.source);
      const target = nodes.find(n => n.id === edge.target);
      if (source && target) {
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', source.position.x * this.scale);
        line.setAttribute('y1', source.position.y * this.scale);
        line.setAttribute('x2', target.position.x * this.scale);
        line.setAttribute('y2', target.position.y * this.scale);
        line.setAttribute('stroke', 'var(--line)');
        line.setAttribute('stroke-width', '1');
        this.svg.appendChild(line);
      }
    });

    nodes.forEach(node => {
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', node.position.x * this.scale);
      rect.setAttribute('y', node.position.y * this.scale);
      rect.setAttribute('width', '18');
      rect.setAttribute('height', '8');
      rect.setAttribute('fill', 'var(--ink)');
      rect.setAttribute('rx', '2');
      this.svg.appendChild(rect);
    });

    this.updateViewport();
  }

  updateViewport() {
    const rect = this.svg.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    this.viewport.setAttribute('x', '0');
    this.viewport.setAttribute('y', '0');
    this.viewport.setAttribute('width', width);
    this.viewport.setAttribute('height', height);
  }

  handleClick(e) {
    const rect = this.svg.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (this.onNavigate) {
      this.onNavigate(x / this.scale, y / this.scale);
    }
  }

  toggle() {
    this.visible = !this.visible;
    this.container.style.display = this.visible ? 'block' : 'none';
  }
}

window.Minimap = Minimap;
