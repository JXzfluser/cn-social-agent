export const depthBlur = `
  const sphereGeo = new THREE.SphereGeometry(1, 32, 32);
  const spheres = [];
  for (let i = 0; i < 30; i++) {
    const sphereMat = new THREE.MeshStandardMaterial({
      color: accentColor,
      transparent: true,
      opacity: 0.4,
    });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
    sphere.position.set(
      (Math.random() - 0.5) * 12,
      (Math.random() - 0.5) * 18,
      (Math.random() - 0.5) * 10
    );
    sphere.scale.setScalar(0.3 + Math.random() * 1.5);
    spheres.push(sphere);
    scene.add(sphere);
  }

  const light = new THREE.PointLight(0xffffff, 1, 30);
  light.position.set(0, 3, 5);
  scene.add(light);

  camera.position.z = 8;

  function update(progress) {
    const blur = Math.sin(progress * Math.PI);

    spheres.forEach((s, i) => {
      const offset = (i / spheres.length) * Math.PI * 2;
      s.position.z = s.position.z + Math.sin(progress * Math.PI * 4 + offset) * 0.02;
      s.material.opacity = 0.2 + blur * 0.5;
      s.scale.setScalar((0.3 + Math.random() * 0.1) * (1 + blur * 0.5));
    });

    if (progress > 0.5) {
      const textEl = document.getElementById('text-overlay');
      if (textEl) textEl.style.opacity = Math.min(1, (progress - 0.5) * 2);
    }
  }
`;
