#!/usr/bin/env node
/**
 * Three.js Card Renderer
 *
 * Renders 3D-enhanced scene cards using Three.js + Puppeteer.
 * Supports depth of field, particle effects, and dynamic lighting.
 */

import { parseArgs } from 'node:util';
import puppeteer from 'puppeteer-core';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const { values } = parseArgs({
  options: {
    output: { type: 'string', required: true },
    title: { type: 'string', default: '' },
    subtitle: { type: 'string', default: '' },
    role: { type: 'string', default: 'value' },
    scene_num: { type: 'string', default: '1' },
    total: { type: 'string', default: '1' },
    accent: { type: 'string', default: '255,90,70' },
    bg: { type: 'string', default: '10,14,18' },
    effect: { type: 'string', default: 'particles' },
    reveal: { type: 'string', default: '1.0' },
    width: { type: 'string', default: '1080' },
    height: { type: 'string', default: '1920' },
  },
});

const outputPath = values.output;
const title = values.title;
const subtitle = values.subtitle;
const role = values.role;
const sceneNum = parseInt(values.scene_num);
const total = parseInt(values.total);
const accent = values.accent.split(',').map(Number);
const bg = values.bg.split(',').map(Number);
const effect = values.effect;
const reveal = parseFloat(values.reveal);
const width = parseInt(values.width);
const height = parseInt(values.height);

const ROLE_LABELS = {
  hook: '开场',
  pain: '痛点',
  context: '背景',
  thesis: '论点',
  evidence: '证据',
  pattern: '规律',
  verdict: '结论',
  value: '干货',
  steps: '步骤',
  proof: '验证',
  compare: '对比',
  pitfall: '避坑',
  cta: '行动',
};

function generateHTML() {
  const label = ROLE_LABELS[role] || '干货';

  return `<!DOCTYPE html>
<html>
<head>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      width: ${width}px;
      height: ${height}px;
      overflow: hidden;
      background: rgb(${bg.join(',')});
      font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
    }
    #canvas-container {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
    }
    #ui-overlay {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: none;
      z-index: 10;
    }
    .accent-bar {
      position: absolute;
      top: 0;
      left: 0;
      width: 14px;
      height: 100%;
      background: rgb(${accent.join(',')});
    }
    .accent-top {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 22px;
      background: rgb(${accent.join(',')});
    }
    .badge {
      position: absolute;
      top: 80px;
      left: 60px;
      padding: 8px 20px;
      background: rgba(${accent.join(',')}, 0.15);
      border: 2px solid rgb(${accent.join(',')});
      border-radius: 20px;
      color: rgb(${accent.join(',')});
      font-size: 28px;
      font-weight: 600;
    }
    .scene-indicator {
      position: absolute;
      top: 80px;
      right: 60px;
      color: rgba(255,255,255,0.5);
      font-size: 24px;
    }
    .title-area {
      position: absolute;
      bottom: 400px;
      left: 60px;
      right: 60px;
    }
    .title {
      font-size: 64px;
      font-weight: 800;
      color: #ffffff;
      line-height: 1.2;
      text-shadow: 0 4px 20px rgba(0,0,0,0.5);
      opacity: ${reveal};
    }
    .subtitle {
      margin-top: 20px;
      font-size: 36px;
      color: rgba(255,255,255,0.7);
      line-height: 1.4;
      opacity: ${Math.min(1, reveal * 1.5)};
    }
    .bottom-bar {
      position: absolute;
      bottom: 0;
      left: 0;
      width: 100%;
      height: 120px;
      background: linear-gradient(transparent, rgba(0,0,0,0.6));
    }
  </style>
</head>
<body>
  <div id="canvas-container"></div>
  <div id="ui-overlay">
    <div class="accent-bar"></div>
    <div class="accent-top"></div>
    <div class="badge">${label}</div>
    <div class="scene-indicator">${sceneNum}/${total}</div>
    <div class="title-area">
      <div class="title">${title}</div>
      <div class="subtitle">${subtitle}</div>
    </div>
    <div class="bottom-bar"></div>
  </div>
  <script type="importmap">
    {
      "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"
      }
    }
  </script>
  <script type="module">
    import * as THREE from 'three';

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, ${width}/${height}, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(${width}, ${height});
    renderer.setClearColor(0x000000, 0);
    document.getElementById('canvas-container').appendChild(renderer.domElement);

    const accentColor = new THREE.Color(${accent[0]/255}, ${accent[1]/255}, ${accent[2]/255});
    const bgColor = new THREE.Color(${bg[0]/255}, ${bg[1]/255}, ${bg[2]/255});

    ${getEffectCode(effect)}

    function animate() {
      requestAnimationFrame(animate);
      update();
      renderer.render(scene, camera);
    }

    animate();
    window.__CARD_READY = true;
  </script>
</body>
</html>`;
}

function getEffectCode(effectType) {
  const effects = {
    particles: `
      camera.position.z = 5;

      const particleCount = 500;
      const geometry = new THREE.BufferGeometry();
      const positions = new Float32Array(particleCount * 3);
      const sizes = new Float32Array(particleCount);

      for (let i = 0; i < particleCount; i++) {
        positions[i * 3] = (Math.random() - 0.5) * 12;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 18;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 8;
        sizes[i] = Math.random() * 3 + 1;
      }

      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

      const material = new THREE.PointsMaterial({
        color: accentColor,
        size: 0.05,
        transparent: true,
        opacity: 0.4,
        blending: THREE.AdditiveBlending,
      });

      const particles = new THREE.Points(geometry, material);
      scene.add(particles);

      function update() {
        const pos = geometry.attributes.position.array;
        for (let i = 0; i < particleCount; i++) {
          pos[i * 3 + 1] += 0.002;
          if (pos[i * 3 + 1] > 9) pos[i * 3 + 1] = -9;
        }
        geometry.attributes.position.needsUpdate = true;
        particles.rotation.z += 0.001;
      }
    `,
    waves: `
      camera.position.set(0, 2, 6);
      camera.lookAt(0, 0, 0);

      const planeGeo = new THREE.PlaneGeometry(16, 16, 64, 64);
      const planeMat = new THREE.MeshStandardMaterial({
        color: accentColor,
        wireframe: true,
        transparent: true,
        opacity: 0.3,
      });
      const plane = new THREE.Mesh(planeGeo, planeMat);
      plane.rotation.x = -Math.PI / 2.5;
      plane.position.y = -2;
      scene.add(plane);

      const light = new THREE.PointLight(0xffffff, 1, 20);
      light.position.set(0, 5, 5);
      scene.add(light);

      function update() {
        const pos = plane.geometry.attributes.position;
        const time = Date.now() * 0.001;
        for (let i = 0; i < pos.count; i++) {
          const x = pos.getX(i);
          const y = pos.getY(i);
          pos.setZ(i, Math.sin(x * 0.5 + time) * 0.3 + Math.cos(y * 0.3 + time) * 0.2);
        }
        pos.needsUpdate = true;
        plane.geometry.computeVertexNormals();
      }
    `,
    grid: `
      camera.position.set(0, 3, 5);
      camera.lookAt(0, 0, 0);

      const gridHelper = new THREE.GridHelper(20, 40, accentColor, new THREE.Color(0x222222));
      gridHelper.position.y = -2;
      scene.add(gridHelper);

      const light = new THREE.PointLight(0xffffff, 0.8, 15);
      light.position.set(0, 4, 3);
      scene.add(light);

      const cubes = [];
      for (let i = 0; i < 12; i++) {
        const geo = new THREE.BoxGeometry(0.3, 0.3 + Math.random() * 1.5, 0.3);
        const mat = new THREE.MeshStandardMaterial({
          color: accentColor,
          transparent: true,
          opacity: 0.5,
        });
        const cube = new THREE.Mesh(geo, mat);
        cube.position.set(
          (Math.random() - 0.5) * 8,
          -1.5 + (0.3 + Math.random() * 1.5) / 2,
          (Math.random() - 0.5) * 8
        );
        cubes.push(cube);
        scene.add(cube);
      }

      function update() {
        cubes.forEach((cube, i) => {
          cube.rotation.y += 0.005 * (i % 2 === 0 ? 1 : -1);
        });
      }
    `,
    rings: `
      camera.position.z = 6;

      const rings = [];
      for (let i = 0; i < 5; i++) {
        const geo = new THREE.TorusGeometry(1 + i * 0.5, 0.02, 16, 100);
        const mat = new THREE.MeshBasicMaterial({
          color: accentColor,
          transparent: true,
          opacity: 0.3 - i * 0.05,
        });
        const ring = new THREE.Mesh(geo, mat);
        ring.rotation.x = Math.PI / 2 + i * 0.1;
        rings.push(ring);
        scene.add(ring);
      }

      function update() {
        rings.forEach((ring, i) => {
          ring.rotation.z += 0.002 * (i % 2 === 0 ? 1 : -1);
        });
      }
    `,
    none: `
      camera.position.z = 5;

      function update() {}
    `,
  };

  return effects[effectType] || effects.particles;
}

console.log(`Rendering card: ${title}`);
console.log(`Role: ${role}, Scene: ${sceneNum}/${total}`);
console.log(`Effect: ${effect}`);

const tmpDir = join(__dirname, '.tmp', `card_${Date.now()}`);
await mkdir(tmpDir, { recursive: true });

const browser = await puppeteer.launch({
  headless: 'new',
  executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  args: [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--enable-webgl',
    '--use-gl=angle',
    '--use-angle=swiftshader',
    '--ignore-gpu-blocklist',
  ],
});

const page = await browser.newPage();
await page.setViewport({ width, height });

const htmlPath = join(tmpDir, 'card.html');
await writeFile(htmlPath, generateHTML(), 'utf-8');

await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle2', timeout: 30000 });
await page.waitForFunction('window.__CARD_READY === true', { timeout: 30000 });

await new Promise(r => setTimeout(r, 500));

const outPath = `${outputPath}.png`;
await page.screenshot({ path: outPath, type: 'png' });

await browser.close();
await rm(tmpDir, { recursive: true, force: true });

console.log(`Output: ${outPath}`);
