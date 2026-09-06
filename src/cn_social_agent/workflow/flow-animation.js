class FlowAnimation {
  constructor(svgContainer) {
    this.svg = svgContainer;
    this.animationGroup = null;
    this.particles = [];
    this.init();
  }

  init() {
    this.animationGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    this.animationGroup.setAttribute('id', 'flow-animation');
    this.svg.appendChild(this.animationGroup);
  }

  animateEdges(edges) {
    this.clear();

    edges.forEach(edge => {
      if (edge.source && edge.target) {
        this.createFlowPath(edge);
      }
    });
  }

  createFlowPath(edge) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${edge.source.x} ${edge.source.y} L ${edge.target.x} ${edge.target.y}`;
    path.setAttribute('d', d);
    path.setAttribute('stroke', 'var(--primary)');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('fill', 'none');
    path.setAttribute('opacity', '0.5');
    this.animationGroup.appendChild(path);

    this.animateAlongPath(path);
  }

  animateAlongPath(path) {
    const length = path.getTotalLength();
    const duration = 2000;
    const particleCount = 3;

    for (let i = 0; i < particleCount; i++) {
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('r', '3');
      circle.setAttribute('fill', 'var(--primary)');
      this.animationGroup.appendChild(circle);

      this.animateParticle(circle, path, length, duration, i * (duration / particleCount));
    }
  }

  animateParticle(particle, path, length, duration, delay) {
    const start = performance.now() + delay;

    const animate = (now) => {
      const progress = (now - start) % duration;
      const t = progress / duration;
      const point = path.getPointAtLength(t * length);

      particle.setAttribute('cx', point.x);
      particle.setAttribute('cy', point.y);

      requestAnimationFrame(animate);
    };

    requestAnimationFrame(animate);
  }

  clear() {
    while (this.animationGroup.firstChild) {
      this.animationGroup.removeChild(this.animationGroup.firstChild);
    }
  }
}

window.FlowAnimation = FlowAnimation;
