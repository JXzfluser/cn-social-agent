/**
 * Particle Converge Transition
 * Particles scatter from random positions and converge to form a sphere,
 * with text reveal at 60% progress.
 */

export const particleConverge = `
  const particleCount = 2000;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(particleCount * 3);
  const targets = new Float32Array(particleCount * 3);

  for (let i = 0; i < particleCount; i++) {
    positions[i * 3] = (Math.random() - 0.5) * 20;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 30;
    positions[i * 3 + 2] = (Math.random() - 0.5) * 10;

    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = 2 + Math.random() * 0.5;
    targets[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    targets[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    targets[i * 3 + 2] = r * Math.cos(phi);
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

  const material = new THREE.PointsMaterial({
    color: accentColor,
    size: 0.08,
    transparent: true,
    opacity: 0.8,
    blending: THREE.AdditiveBlending,
  });

  const particles = new THREE.Points(geometry, material);
  scene.add(particles);
  camera.position.z = 8;

  function update(progress) {
    const pos = geometry.attributes.position.array;
    const ease = 1 - Math.pow(1 - progress, 3);

    for (let i = 0; i < particleCount; i++) {
      const i3 = i * 3;
      pos[i3] += (targets[i3] - pos[i3]) * ease * 0.1;
      pos[i3 + 1] += (targets[i3 + 1] - pos[i3 + 1]) * ease * 0.1;
      pos[i3 + 2] += (targets[i3 + 2] - pos[i3 + 2]) * ease * 0.1;
    }

    geometry.attributes.position.needsUpdate = true;

    if (progress > 0.6) {
      const textEl = document.getElementById('text-overlay');
      if (textEl) textEl.style.opacity = Math.min(1, (progress - 0.6) * 2.5);
    }

    if (progress > 0.85) {
      material.opacity = 0.8 * (1 - (progress - 0.85) / 0.15);
    }
  }
`;
