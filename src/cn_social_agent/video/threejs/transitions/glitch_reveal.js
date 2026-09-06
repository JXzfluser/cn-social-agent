export const glitchReveal = `
  const planeGeo = new THREE.PlaneGeometry(20, 30);
  const planeMat = new THREE.MeshBasicMaterial({
    color: 0x000000,
    transparent: true,
    opacity: 1,
  });
  const plane = new THREE.Mesh(planeGeo, planeMat);
  scene.add(plane);

  const glitchLines = [];
  for (let i = 0; i < 15; i++) {
    const lineGeo = new THREE.PlaneGeometry(20, 0.1 + Math.random() * 0.3);
    const lineMat = new THREE.MeshBasicMaterial({
      color: accentColor,
      transparent: true,
      opacity: 0,
    });
    const line = new THREE.Mesh(lineGeo, lineMat);
    line.position.y = (Math.random() - 0.5) * 20;
    glitchLines.push(line);
    scene.add(line);
  }

  camera.position.z = 5;

  function update(progress) {
    const glitchIntensity = Math.sin(progress * Math.PI * 8) * (1 - progress);

    glitchLines.forEach((line) => {
      const show = Math.random() < Math.abs(glitchIntensity);
      line.material.opacity = show ? 0.8 : 0;
      line.position.x = (Math.random() - 0.5) * 2;
      line.position.y = (Math.random() - 0.5) * 15;
    });

    planeMat.opacity = Math.max(0, 1 - progress * 1.5);

    if (progress > 0.5) {
      const textEl = document.getElementById('text-overlay');
      if (textEl) textEl.style.opacity = Math.min(1, (progress - 0.5) * 2);
    }
  }
`;
