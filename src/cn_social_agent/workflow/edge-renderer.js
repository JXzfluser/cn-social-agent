const EdgeRenderer = {
  render(sourceNode, targetNode) {
    const sourceX = sourceNode.position.x + 180;
    const sourceY = sourceNode.position.y + 40;
    const targetX = targetNode.position.x;
    const targetY = targetNode.position.y + 40;

    const dx = Math.abs(targetX - sourceX) * 0.5;
    const d = `M ${sourceX} ${sourceY} C ${sourceX + dx} ${sourceY}, ${targetX - dx} ${targetY}, ${targetX} ${targetY}`;

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', '#0f766e');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('stroke-linecap', 'round');

    const arrow = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    const arrowSize = 8;
    arrow.setAttribute('points', `${targetX},${targetY} ${targetX - arrowSize},${targetY - arrowSize/2} ${targetX - arrowSize},${targetY + arrowSize/2}`);
    arrow.setAttribute('fill', '#0f766e');

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.appendChild(path);
    g.appendChild(arrow);
    return g;
  }
};

window.EdgeRenderer = EdgeRenderer;
