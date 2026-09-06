#!/usr/bin/env node
import { parseArgs } from 'node:util';
import puppeteer from 'puppeteer-core';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

import {
  particleConverge,
  cameraFlythrough,
  glitchReveal,
  lightSweep,
  depthBlur,
} from './transitions/index.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const { values } = parseArgs({
  options: {
    transition: { type: 'string', default: 'particle_converge' },
    text: { type: 'string', default: '' },
    accent: { type: 'string', default: '255,90,70' },
    output: { type: 'string', required: true },
    duration: { type: 'string', default: '1.5' },
    width: { type: 'string', default: '1080' },
    height: { type: 'string', default: '1920' },
    fps: { type: 'string', default: '30' },
  },
});

const transitionType = values.transition;
const text = values.text;
const accent = values.accent.split(',').map(Number);
const outputBase = values.output;
const duration = parseFloat(values.duration);
const width = parseInt(values.width);
const height = parseInt(values.height);
const fps = parseInt(values.fps);
const totalFrames = Math.ceil(duration * fps);

const TRANSITION_MAP = {
  particle_converge: particleConverge,
  camera_flythrough: cameraFlythrough,
  glitch_reveal: glitchReveal,
  light_sweep: lightSweep,
  depth_blur: depthBlur,
};

const transitionCode = TRANSITION_MAP[transitionType];
if (!transitionCode) {
  console.error(`Unknown transition: ${transitionType}`);
  console.error(`Available: ${Object.keys(TRANSITION_MAP).join(', ')}`);
  process.exit(1);
}

function generateHTML() {
  return `<!DOCTYPE html>
<html>
<head>
  <style>
    * { margin: 0; padding: 0; }
    body {
      width: ${width}px;
      height: ${height}px;
      overflow: hidden;
      background: #000;
    }
    canvas { display: block; }
    #text-overlay {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
      font-size: 72px;
      font-weight: bold;
      color: rgb(${accent.join(',')});
      text-shadow: 0 0 40px rgba(${accent.join(',')}, 0.5);
      opacity: 0;
      z-index: 10;
      text-align: center;
      max-width: 80%;
    }
  </style>
</head>
<body>
  <div id="text-overlay">${text || ''}</div>
  <script type="importmap">
    {
      "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"
      }
    }
  </script>
  <script type="module">
    import * as THREE from 'three';

    window.__RENDER_STATE = {
      frame: 0,
      totalFrames: ${totalFrames},
      ready: false,
    };

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, ${width}/${height}, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(${width}, ${height});
    renderer.setClearColor(0x000000, 1);
    document.body.appendChild(renderer.domElement);

    const accentColor = new THREE.Color(${accent[0]/255}, ${accent[1]/255}, ${accent[2]/255});

    ${transitionCode}

    function animate() {
      if (!window.__RENDER_STATE.ready) return;

      const progress = window.__RENDER_STATE.frame / window.__RENDER_STATE.totalFrames;
      update(progress);

      renderer.render(scene, camera);
      window.__RENDER_STATE.frame++;

      if (window.__RENDER_STATE.frame <= window.__RENDER_STATE.totalFrames) {
        requestAnimationFrame(animate);
      } else {
        window.__RENDER_STATE.done = true;
      }
    }

    window.__RENDER_STATE.ready = true;
    animate();
    window.__RENDER_READY = true;
  </script>
</body>
</html>`;
}

console.log(`Rendering: ${transitionType}`);
console.log(`Duration: ${duration}s, Frames: ${totalFrames}, FPS: ${fps}`);
console.log(`Resolution: ${width}x${height}`);

const tmpDir = join(__dirname, '.tmp', `frames_${Date.now()}`);
await mkdir(tmpDir, { recursive: true });

console.log('Launching browser...');
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

page.on('console', msg => console.log('BROWSER:', msg.text()));
page.on('pageerror', err => console.error('PAGE ERROR:', err.message));

const htmlPath = join(tmpDir, 'transition.html');
await writeFile(htmlPath, generateHTML(), 'utf-8');
console.log('HTML written to', htmlPath);

console.log('Loading page...');
await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle2', timeout: 30000 });

console.log('Waiting for Three.js to be ready...');
await page.waitForFunction('window.__RENDER_READY === true', { timeout: 30000 });

console.log('Capturing frames...');
for (let i = 0; i < totalFrames; i++) {
  const framePath = join(tmpDir, `frame_${String(i).padStart(4, '0')}.png`);
  await page.screenshot({ path: framePath, type: 'png' });
  await page.evaluate(() => { window.__RENDER_STATE.ready = true; });
  await new Promise(r => setTimeout(r, 16));
  if (i % 10 === 0) process.stdout.write(`\rFrame ${i + 1}/${totalFrames}`);
}
console.log('\nFrame capture complete');

await browser.close();

const outputPath = `${outputBase}.mp4`;
console.log('Compiling MP4 with ffmpeg...');

try {
  execSync([
    'ffmpeg', '-y',
    '-framerate', String(fps),
    '-i', join(tmpDir, 'frame_%04d.png'),
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-preset', 'fast',
    '-crf', '18',
    outputPath,
  ].join(' '), { stdio: 'inherit' });
  console.log(`\nOutput: ${outputPath}`);
} catch (e) {
  console.error('ffmpeg failed:', e.message);
  process.exit(1);
} finally {
  await rm(tmpDir, { recursive: true, force: true });
}

console.log('Done!');
