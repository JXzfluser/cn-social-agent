/* Node test for the pure helpers exposed by canvas_enhancements.js.
 * Run: node tests/workbench/js/canvas_enhancements_test.js
 * No jsdom: only DOM-free helpers are exercised.
 */
"use strict";

const assert = require("assert");
const path = require("path");

const MODULE = path.resolve(
  __dirname,
  "../../../src/cn_social_agent/workbench/canvas_enhancements.js"
);
require(MODULE);

const CE = globalThis.CanvasEnhancements;
assert.ok(CE, "CanvasEnhancements must be attached to globalThis");

const V = CE.viewport;
assert.ok(V, "CanvasEnhancements.viewport must be exposed");

const tests = [];
function test(name, fn) {
  tests.push([name, fn]);
}

/* ---------- scroll extent + clamping ---------- */

test("scrollExtent uses actual scrollable size minus viewport", () => {
  assert.strictEqual(V.scrollExtent(3840, 800), 3040);
  assert.strictEqual(V.scrollExtent(800, 800), 0);
  assert.strictEqual(V.scrollExtent(500, 800), 0, "never negative");
});

test("clampScroll keeps scroll within [0, max]", () => {
  assert.deepStrictEqual(V.clampScroll(-40, -10, 1000, 500), {
    scrollLeft: 0,
    scrollTop: 0,
  });
  assert.deepStrictEqual(V.clampScroll(5000, 5000, 1000, 500), {
    scrollLeft: 1000,
    scrollTop: 500,
  });
  assert.deepStrictEqual(V.clampScroll(120, 60, 1000, 500), {
    scrollLeft: 120,
    scrollTop: 60,
  });
});

test("centerScrollFor converts world point to top-left scroll at zoom", () => {
  const r = V.centerScrollFor(1200, 800, 2, 800, 600);
  assert.strictEqual(r.scrollLeft, 1200 * 2 - 400);
  assert.strictEqual(r.scrollTop, 800 * 2 - 300);
});

/* ---------- fit ---------- */

test("computeFit never overflows the viewport and respects zoom bounds", () => {
  const nodes = [
    { x: 0, y: 0, w: 240, h: 150 },
    { x: 760, y: 350, w: 240, h: 150 },
  ];
  const fit = V.computeFit({
    nodes,
    viewWidth: 800,
    viewHeight: 600,
    worldWidth: 2400,
    worldHeight: 1600,
  });
  const contentW = 1000 + 96;
  const contentH = 500 + 96;
  assert.ok(fit.zoom >= 0.5 && fit.zoom <= 1.6, `zoom in range: ${fit.zoom}`);
  assert.ok(contentW * fit.zoom <= 800 + 1e-9, "content width fits view");
  assert.ok(contentH * fit.zoom <= 600 + 1e-9, "content height fits view");
  assert.deepStrictEqual(fit.bounds, { minX: 0, minY: 0, maxX: 1000, maxY: 500 });
});

test("computeFit clamps scroll against the real scrollable extent", () => {
  const nodes = [{ x: 2200, y: 1400, w: 160, h: 120 }];
  const fit = V.computeFit({
    nodes,
    viewWidth: 800,
    viewHeight: 600,
    worldWidth: 2400,
    worldHeight: 1600,
    scrollWidth: 2400 * 1.6,
    scrollHeight: 1600 * 1.6,
  });
  const maxLeft = V.scrollExtent(2400 * 1.6, 800);
  const maxTop = V.scrollExtent(1600 * 1.6, 600);
  assert.ok(fit.scrollLeft <= maxLeft + 1e-9 && fit.scrollLeft >= 0);
  assert.ok(fit.scrollTop <= maxTop + 1e-9 && fit.scrollTop >= 0);
});

test("computeFit on an empty canvas is a no-op view", () => {
  const fit = V.computeFit({ nodes: [], viewWidth: 800, viewHeight: 600 });
  assert.strictEqual(fit.zoom, 1);
  assert.strictEqual(fit.scrollLeft, 0);
  assert.strictEqual(fit.scrollTop, 0);
});

/* ---------- minimap math ---------- */

test("minimapProjection letterboxes the world inside the minimap canvas", () => {
  const p = V.minimapProjection({
    canvasWidth: 168,
    canvasHeight: 112,
    worldWidth: 2400,
    worldHeight: 1600,
  });
  assert.ok(Math.abs(p.scale - 0.07) < 1e-9, `scale ${p.scale}`);
  assert.ok(Math.abs(p.offsetX) < 1e-9);
  assert.ok(Math.abs(p.offsetY) < 1e-9);

  const wide = V.minimapProjection({
    canvasWidth: 200,
    canvasHeight: 100,
    worldWidth: 1000,
    worldHeight: 1000,
  });
  assert.strictEqual(wide.scale, 0.1);
  assert.strictEqual(wide.offsetX, 50);
  assert.strictEqual(wide.offsetY, 0);
});

test("minimap point/world conversions round-trip", () => {
  const p = V.minimapProjection({
    canvasWidth: 168,
    canvasHeight: 112,
    worldWidth: 2400,
    worldHeight: 1600,
  });
  const pt = V.minimapWorldToPoint(1200, 800, p);
  const back = V.minimapPointToWorld(pt.x, pt.y, p);
  assert.ok(Math.abs(back.worldX - 1200) < 1e-6);
  assert.ok(Math.abs(back.worldY - 800) < 1e-6);
});

test("minimapViewportRect shrinks as zoom increases", () => {
  const p = V.minimapProjection({
    canvasWidth: 168,
    canvasHeight: 112,
    worldWidth: 2400,
    worldHeight: 1600,
  });
  const at1 = V.minimapViewportRect({
    projection: p,
    zoom: 1,
    scrollLeft: 0,
    scrollTop: 0,
    clientWidth: 800,
    clientHeight: 600,
  });
  const at2 = V.minimapViewportRect({
    projection: p,
    zoom: 2,
    scrollLeft: 800,
    scrollTop: 600,
    clientWidth: 800,
    clientHeight: 600,
  });
  assert.ok(Math.abs(at1.width - 800 * p.scale) < 1e-9);
  assert.ok(at2.width < at1.width, "higher zoom shows less world");
  assert.ok(Math.abs(at2.x - 400 * p.scale) < 1e-9, "scroll maps through zoom");
});

test("panStep moves the view by a fraction of the viewport in world units", () => {
  const step = V.panStep({ clientWidth: 800, clientHeight: 600, zoom: 2 });
  assert.ok(step.x > 0 && step.y > 0);
  assert.ok(step.x < 800, "world-space step is smaller when zoomed in");
});

/* ---------- minimap keyboard navigation (DOM-free fake container) ---------- */

function fakeMinimap() {
  const attrs = {};
  const handlers = {};
  const el = {
    _cvMiniMapMeta: null,
    hasAttribute: (k) => Object.prototype.hasOwnProperty.call(attrs, k),
    getAttribute: (k) => (k in attrs ? attrs[k] : null),
    setAttribute: (k, v) => {
      attrs[k] = String(v);
    },
    addEventListener: (type, fn) => {
      handlers[type] = handlers[type] || [];
      handlers[type].push(fn);
    },
    setPointerCapture() {},
    releasePointerCapture() {},
    fire: (type, ev) => (handlers[type] || []).forEach((fn) => fn(ev)),
  };
  el._cvMiniMapMeta = Object.assign(
    V.minimapProjection({
      canvasWidth: 168,
      canvasHeight: 112,
      worldWidth: 2400,
      worldHeight: 1600,
    }),
    { canvas: null, zoom: 1 }
  );
  return el;
}

test("arrow keys pan relative to the current scroll position", () => {
  const el = fakeMinimap();
  const seen = [];
  // The shape the workbench actually supplies for the current view.
  const view = {
    x: 1000,
    y: 700,
    zoom: 2,
    scrollLeft: 1600,
    scrollTop: 1000,
    clientWidth: 800,
    clientHeight: 600,
    worldWidth: 2400,
    worldHeight: 1600,
  };
  CE.bindMinimapNavigation(el, () => view, (wx, wy) => seen.push([wx, wy]));

  const centerX = view.scrollLeft / view.zoom + view.clientWidth / view.zoom / 2;
  const centerY = view.scrollTop / view.zoom + view.clientHeight / view.zoom / 2;
  const step = V.panStep({
    clientWidth: view.clientWidth,
    clientHeight: view.clientHeight,
    zoom: view.zoom,
  });

  el.fire("keydown", { key: "ArrowRight", preventDefault() {} });
  assert.deepStrictEqual(seen[0], [centerX + step.x, centerY]);

  el.fire("keydown", { key: "ArrowUp", preventDefault() {} });
  assert.deepStrictEqual(seen[1], [centerX, centerY - step.y]);

  el.fire("keydown", { key: "Tab", preventDefault() {} });
  assert.strictEqual(seen.length, 2, "unrelated keys do not navigate");
});

test("minimap container becomes focusable when bound", () => {
  const el = fakeMinimap();
  CE.bindMinimapNavigation(el, () => ({}), () => {});
  assert.strictEqual(el.getAttribute("tabindex"), "0");
});

/* ---------- URL sanitization ---------- */

test("sanitizeUrl allows only http/https", () => {
  assert.strictEqual(CE.sanitizeUrl("https://example.com/a?b=1"), "https://example.com/a?b=1");
  assert.strictEqual(CE.sanitizeUrl("  http://example.com  "), "http://example.com/");
  assert.strictEqual(CE.sanitizeUrl("javascript:alert(1)"), "");
  assert.strictEqual(CE.sanitizeUrl("jAvAsCrIpT:alert(1)"), "");
  assert.strictEqual(CE.sanitizeUrl("java\nscript:alert(1)"), "");
  assert.strictEqual(CE.sanitizeUrl("data:text/html;base64,PHN2Zz4="), "");
  assert.strictEqual(CE.sanitizeUrl("vbscript:msgbox(1)"), "");
  assert.strictEqual(CE.sanitizeUrl("file:///etc/passwd"), "");
  assert.strictEqual(CE.sanitizeUrl("example.com"), "", "scheme-less is not clickable");
  assert.strictEqual(CE.sanitizeUrl(""), "");
  assert.strictEqual(CE.sanitizeUrl(null), "");
  assert.strictEqual(CE.sanitizeUrl(undefined), "");
});

/* ---------- edge geometry ---------- */

test("edgeEndpoints land on the rectangle boundary with zero inset", () => {
  const a = { x: 0, y: 0, w: 240, h: 150 };
  const b = { x: 600, y: 0, w: 240, h: 150 };
  const ep = CE.edgeGeometry.edgeEndpoints(a, b, 0);
  assert.ok(Math.abs(ep.x1 - 240) < 1e-6, "exits source right edge");
  assert.ok(Math.abs(ep.x2 - 600) < 1e-6, "stops at target left edge");
});

test("default inset pulls the arrow tip short of the target boundary", () => {
  const a = { x: 0, y: 0, w: 240, h: 150 };
  const b = { x: 600, y: 0, w: 240, h: 150 };
  const flush = CE.edgeGeometry.edgeEndpoints(a, b, 0);
  const inset = CE.edgeGeometry.edgeEndpoints(a, b);
  assert.strictEqual(CE.edgeGeometry.ARROW_INSET, 10);
  assert.ok(
    Math.abs(inset.x2 - (flush.x2 - CE.edgeGeometry.ARROW_INSET)) < 1e-6,
    "inset applied along the chord"
  );
});

let failed = 0;
for (const [name, fn] of tests) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`not ok - ${name}\n    ${err && err.message}`);
  }
}
console.log(`${tests.length - failed}/${tests.length} passed`);
process.exit(failed ? 1 : 0);
