export const lightSweep = `
  const sweepGeo = new THREE.PlaneGeometry(4, 30);
  const sweepMat = new THREE.MeshBasicMaterial({
    color: accentColor,
    transparent: true,
    opacity: 0,
    blending: THREE.AdditiveBlending,
  });
  const sweep = new THREE.Mesh(sweepGeo, sweepMat);
  sweep.position.x = -15;
  scene.add(sweep);

  const bgGeo = new THREE.PlaneGeometry(20, 30);
  const bgMat = new THREE.MeshBasicMaterial({
    color: 0x000000,
    transparent: true,
    opacity: 1,
  });
  const bg = new THREE.Mesh(bgGeo, bgMat);
  bg.position.z = -1;
  scene.add(bg);

  camera.position.z = 5;

  function update(progress) {
    const ease = progress < 0.5
      ? 2 * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 2) / 2;

    sweep.position.x = -15 + ease * 30;
    sweepMat.opacity = Math.sin(progress * Math.PI) * 0.9;

    bgMat.opacity = Math.max(0, 1 - progress * 2);

    if (progress > 0.4) {
      const textEl = document.getElementById('text-overlay');
      if (textEl) textEl.style.opacity = Math.min(1, (progress - 0.4) * 2.5);
    }
  }
`;
