export const cameraFlythrough = `
  const boxes = [];
  for (let i = 0; i < 50; i++) {
    const geo = new THREE.BoxGeometry(
      0.5 + Math.random() * 2,
      0.5 + Math.random() * 3,
      0.5 + Math.random() * 2
    );
    const mat = new THREE.MeshStandardMaterial({
      color: accentColor,
      transparent: true,
      opacity: 0.3 + Math.random() * 0.4,
      wireframe: Math.random() > 0.5,
    });
    const box = new THREE.Mesh(geo, mat);
    box.position.set(
      (Math.random() - 0.5) * 15,
      (Math.random() - 0.5) * 20,
      (Math.random() - 0.5) * 15
    );
    box.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
    boxes.push(box);
    scene.add(box);
  }

  const gridHelper = new THREE.GridHelper(30, 30, accentColor, 0x222222);
  gridHelper.position.y = -5;
  scene.add(gridHelper);

  const light = new THREE.PointLight(0xffffff, 1, 50);
  light.position.set(0, 5, 5);
  scene.add(light);

  camera.position.set(0, 0, 10);

  function update(progress) {
    const ease = progress < 0.5
      ? 2 * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 2) / 2;

    camera.position.z = 10 - ease * 15;
    camera.position.y = ease * 3;
    camera.rotation.y = ease * Math.PI * 0.5;

    boxes.forEach((box, i) => {
      box.rotation.x += 0.01 * (i % 2 === 0 ? 1 : -1);
      box.rotation.z += 0.005;
    });

    if (progress > 0.5) {
      const textEl = document.getElementById('text-overlay');
      if (textEl) textEl.style.opacity = Math.min(1, (progress - 0.5) * 2);
    }
  }
`;
