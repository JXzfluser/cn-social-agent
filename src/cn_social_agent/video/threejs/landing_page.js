#!/usr/bin/env node
/**
 * Three.js Landing Page Generator
 *
 * Generates scroll-driven interactive landing pages with Three.js.
 * Outputs a self-contained HTML file with embedded Three.js scenes.
 */

import { parseArgs } from 'node:util';
import { writeFile, mkdir } from 'node:fs/promises';
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
    sections: { type: 'string', default: '[]' },
    accent: { type: 'string', default: '255,90,70' },
    bg: { type: 'string', default: '10,14,18' },
    template: { type: 'string', default: 'product' },
  },
});

const outputPath = values.output;
const title = values.title;
const subtitle = values.subtitle;
const sections = JSON.parse(values.sections);
const accent = values.accent.split(',').map(Number);
const bg = values.bg.split(',').map(Number);
const template = values.template;

function generateLandingPage() {
  const sectionHTML = sections.map((s, i) => `
    <section class="scene" data-scene="${i}">
      <div class="scene-content">
        <h2 class="scene-title">${s.title || ''}</h2>
        <p class="scene-desc">${s.description || ''}</p>
        ${s.stat ? `<div class="stat">${s.stat}</div>` : ''}
      </div>
    </section>
  `).join('\n');

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    html {
      scroll-behavior: smooth;
    }
    
    body {
      background: rgb(${bg.join(',')});
      color: #ffffff;
      font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', sans-serif;
      overflow-x: hidden;
    }
    
    #canvas-container {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100vh;
      z-index: 0;
    }
    
    .content {
      position: relative;
      z-index: 10;
    }
    
    .hero {
      height: 100vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      text-align: center;
      padding: 0 20px;
    }
    
    .hero-title {
      font-size: clamp(48px, 8vw, 96px);
      font-weight: 800;
      line-height: 1.1;
      margin-bottom: 24px;
      text-shadow: 0 4px 30px rgba(0,0,0,0.5);
    }
    
    .hero-subtitle {
      font-size: clamp(20px, 3vw, 32px);
      color: rgba(255,255,255,0.7);
      max-width: 600px;
      line-height: 1.5;
    }
    
    .scroll-indicator {
      position: absolute;
      bottom: 40px;
      left: 50%;
      transform: translateX(-50%);
      animation: bounce 2s infinite;
      color: rgba(255,255,255,0.5);
      font-size: 14px;
      text-align: center;
    }
    
    @keyframes bounce {
      0%, 100% { transform: translateX(-50%) translateY(0); }
      50% { transform: translateX(-50%) translateY(-10px); }
    }
    
    .scene {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 80px 20px;
    }
    
    .scene-content {
      max-width: 800px;
      text-align: center;
      opacity: 0;
      transform: translateY(60px);
      transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
    }
    
    .scene-content.visible {
      opacity: 1;
      transform: translateY(0);
    }
    
    .scene-title {
      font-size: clamp(32px, 5vw, 56px);
      font-weight: 700;
      margin-bottom: 20px;
      background: linear-gradient(135deg, rgb(${accent.join(',')}), #ffffff);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    
    .scene-desc {
      font-size: clamp(18px, 2.5vw, 24px);
      color: rgba(255,255,255,0.7);
      line-height: 1.6;
    }
    
    .stat {
      margin-top: 40px;
      font-size: clamp(48px, 8vw, 80px);
      font-weight: 800;
      color: rgb(${accent.join(',')});
      text-shadow: 0 0 40px rgba(${accent.join(',')}, 0.5);
    }
    
    .cta-section {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 80px 20px;
    }
    
    .cta-button {
      margin-top: 40px;
      padding: 20px 48px;
      font-size: 20px;
      font-weight: 600;
      color: #ffffff;
      background: rgb(${accent.join(',')});
      border: none;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.3s ease;
      text-decoration: none;
    }
    
    .cta-button:hover {
      transform: scale(1.05);
      box-shadow: 0 10px 40px rgba(${accent.join(',')}, 0.4);
    }
    
    .accent-bar {
      position: fixed;
      top: 0;
      left: 0;
      width: 4px;
      height: 100%;
      background: rgb(${accent.join(',')});
      z-index: 100;
    }
    
    .progress-bar {
      position: fixed;
      top: 0;
      left: 0;
      height: 3px;
      background: rgb(${accent.join(',')});
      z-index: 101;
      transition: width 0.1s;
    }
  </style>
</head>
<body>
  <div class="accent-bar"></div>
  <div class="progress-bar" id="progress"></div>
  
  <div id="canvas-container"></div>
  
  <div class="content">
    <section class="hero">
      <h1 class="hero-title">${title}</h1>
      <p class="hero-subtitle">${subtitle}</p>
      <div class="scroll-indicator">↓ 向下滚动探索</div>
    </section>
    
    ${sectionHTML}
    
    <section class="cta-section">
      <h2 class="scene-title">立即体验</h2>
      <p class="scene-desc">开始你的下一个项目</p>
      <a href="#" class="cta-button">免费试用</a>
    </section>
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
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setClearColor(0x000000, 0);
    document.getElementById('canvas-container').appendChild(renderer.domElement);
    
    const accentColor = new THREE.Color(${accent[0]/255}, ${accent[1]/255}, ${accent[2]/255});
    
    ${getTemplateCode(template)}
    
    let scrollProgress = 0;
    
    window.addEventListener('scroll', () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      scrollProgress = scrollTop / docHeight;
      
      document.getElementById('progress').style.width = (scrollProgress * 100) + '%';
    });
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    }, { threshold: 0.2 });
    
    document.querySelectorAll('.scene-content').forEach(el => observer.observe(el));
    
    function animate() {
      requestAnimationFrame(animate);
      updateScroll(scrollProgress);
      renderer.render(scene, camera);
    }
    
    animate();
    
    window.addEventListener('resize', () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });
  </script>
</body>
</html>`;
}

function getTemplateCode(templateType) {
  const templates = {
    product: `
      camera.position.z = 5;
      
      const particleCount = 800;
      const geometry = new THREE.BufferGeometry();
      const positions = new Float32Array(particleCount * 3);
      const colors = new Float32Array(particleCount * 3);
      
      for (let i = 0; i < particleCount; i++) {
        positions[i * 3] = (Math.random() - 0.5) * 20;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 40;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 15;
        
        const mix = Math.random();
        colors[i * 3] = accentColor.r * mix + 0.1 * (1 - mix);
        colors[i * 3 + 1] = accentColor.g * mix + 0.1 * (1 - mix);
        colors[i * 3 + 2] = accentColor.b * mix + 0.15 * (1 - mix);
      }
      
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      
      const material = new THREE.PointsMaterial({
        size: 0.06,
        transparent: true,
        opacity: 0.6,
        vertexColors: true,
        blending: THREE.AdditiveBlending,
      });
      
      const particles = new THREE.Points(geometry, material);
      scene.add(particles);
      
      const gridHelper = new THREE.GridHelper(30, 30, 0x222222, 0x111111);
      gridHelper.position.y = -8;
      scene.add(gridHelper);
      
      function updateScroll(progress) {
        const pos = geometry.attributes.position.array;
        for (let i = 0; i < particleCount; i++) {
          pos[i * 3 + 1] += 0.01;
          if (pos[i * 3 + 1] > 20) pos[i * 3 + 1] = -20;
        }
        geometry.attributes.position.needsUpdate = true;
        
        camera.position.y = -progress * 8;
        camera.rotation.x = progress * 0.3;
        
        particles.rotation.y = progress * Math.PI * 0.5;
      }
    `,
    tech: `
      camera.position.set(0, 2, 6);
      camera.lookAt(0, 0, 0);
      
      const cubes = [];
      for (let i = 0; i < 40; i++) {
        const size = 0.2 + Math.random() * 0.6;
        const geo = new THREE.BoxGeometry(size, size, size);
        const mat = new THREE.MeshStandardMaterial({
          color: accentColor,
          transparent: true,
          opacity: 0.3 + Math.random() * 0.4,
          wireframe: Math.random() > 0.5,
        });
        const cube = new THREE.Mesh(geo, mat);
        cube.position.set(
          (Math.random() - 0.5) * 12,
          (Math.random() - 0.5) * 20,
          (Math.random() - 0.5) * 8
        );
        cube.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
        cubes.push(cube);
        scene.add(cube);
      }
      
      const light = new THREE.PointLight(0xffffff, 1, 20);
      light.position.set(0, 5, 5);
      scene.add(light);
      
      function updateScroll(progress) {
        cubes.forEach((cube, i) => {
          cube.rotation.x += 0.005 * (i % 2 === 0 ? 1 : -1);
          cube.rotation.z += 0.003;
          cube.position.y += Math.sin(progress * Math.PI * 2 + i) * 0.01;
        });
        
        camera.position.y = 2 - progress * 6;
        camera.rotation.y = progress * Math.PI * 0.4;
      }
    `,
    minimal: `
      camera.position.z = 5;
      
      const ringGeo = new THREE.TorusGeometry(2, 0.03, 16, 100);
      const ringMat = new THREE.MeshBasicMaterial({ color: accentColor, transparent: true, opacity: 0.5 });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      scene.add(ring);
      
      const ring2Geo = new THREE.TorusGeometry(2.5, 0.02, 16, 100);
      const ring2Mat = new THREE.MeshBasicMaterial({ color: 0x444444, transparent: true, opacity: 0.3 });
      const ring2 = new THREE.Mesh(ring2Geo, ring2Mat);
      ring2.rotation.x = Math.PI / 3;
      scene.add(ring2);
      
      function updateScroll(progress) {
        ring.rotation.z = progress * Math.PI * 2;
        ring2.rotation.z = -progress * Math.PI * 1.5;
        
        const scale = 1 + Math.sin(progress * Math.PI) * 0.3;
        ring.scale.setScalar(scale);
      }
    `,
  };
  
  return templates[templateType] || templates.product;
}

console.log(`Generating landing page: ${title}`);
console.log(`Template: ${template}`);
console.log(`Sections: ${sections.length}`);

const html = generateLandingPage();

await writeFile(outputPath, html, 'utf-8');

console.log(`Output: ${outputPath}`);
console.log('Done!');
