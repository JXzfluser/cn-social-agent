"""Static contracts for workbench HTML / canvas enhancement module."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKBENCH = ROOT / "src" / "cn_social_agent" / "workbench"
INDEX = WORKBENCH / "index.html"
CANVAS_JS = WORKBENCH / "canvas_enhancements.js"
JS_TESTS = Path(__file__).resolve().parent / "js" / "canvas_enhancements_test.js"


def _html() -> str:
    return INDEX.read_text(encoding="utf-8")


def _node_or_skip() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    return node


def _run_node_script(script: str) -> str:
    """Evaluate a script that requires canvas_enhancements.js and prints JSON."""
    node = _node_or_skip()
    proc = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc.stdout.strip()


def _canvas_script_block(html: str) -> str:
    """Extract the Knowledge canvas script region from index.html."""
    start = html.find("/* ---------- Knowledge canvas ---------- */")
    assert start >= 0, "canvas script block missing"
    # End at the next major section or script close near end of canvas wiring
    end_markers = (
        'if ($("globalPlatClose"))',
        "wireCanvasMarquee();",
    )
    end = len(html)
    for marker in end_markers:
        idx = html.find(marker, start)
        if idx >= 0:
            # include a bit past wireCanvas for create/rename/delete checks
            end = max(end if end < len(html) else 0, idx + 800)
    # Prefer cutting at globalPlatClose which follows canvas wiring
    plat = html.find('if ($("globalPlatClose"))', start)
    if plat >= 0:
        end = plat
    return html[start:end]


def test_project_board_module_and_controls():
    html = _html()
    js = WORKBENCH / "project_board.js"
    assert js.is_file()
    assert "/static/project_board.js" in html
    text = js.read_text(encoding="utf-8")
    for name in ("progressHtml", "buildBoardQuery", "drawerHtml", "wireLaneDropZones", "makeCardDraggable"):
        assert name in text
    assert 'id="boardSearch"' in html
    assert 'id="boardCategory"' in html
    assert 'id="boardArtifact"' in html
    assert 'id="boardSort"' in html
    assert 'id="boardDrawer"' in html
    assert "bc-progress" in html or "bc-progress" in text
    assert "data-lane" in html

    html = _html()
    assert CANVAS_JS.is_file(), "canvas_enhancements.js must exist"
    assert "/static/canvas_enhancements.js" in html
    text = CANVAS_JS.read_text(encoding="utf-8")
    assert "window.CanvasEnhancements" in text or "CanvasEnhancements" in text
    for name in (
        "openDialog",
        "edgeGeometry",
        "renderMinimap",
        "fitContent",
        "openContextMenu",
        "openTemplatePicker",
        "organizeSelection",
    ):
        assert name in text, f"CanvasEnhancements missing helper: {name}"


def test_canvas_dialog_minimap_toolbar_contracts():
    html = _html()
    assert 'id="wbDialog"' in html or 'id="canvasDialog"' in html
    assert "<dialog" in html
    # Prefer dedicated workbench dialog for canvas actions
    assert re.search(r'id="(wbDialog|canvasDialog)"', html)
    assert 'id="canvasMinimap"' in html
    assert 'id="canvasFitBtn"' in html
    assert 'id="canvasOrganizeBtn"' in html
    assert 'id="canvasTemplateBtn"' in html or 'id="canvasNewBoardBtn"' in html
    assert 'id="canvasNodeMenu"' in html or 'class="cv-node-menu"' in html
    # CSS polish hooks
    assert "wb-dialog" in html or "cv-dialog" in html
    assert "cv-minimap" in html


def test_canvas_region_has_no_window_prompt_or_confirm():
    html = _html()
    block = _canvas_script_block(html)
    assert "window.prompt" not in block
    assert "window.confirm" not in block
    # bare prompt/confirm calls in canvas region also disallowed
    assert not re.search(r"(?<![\w.])prompt\s*\(", block)
    assert not re.search(r"(?<![\w.])confirm\s*\(", block)


def test_canvas_enhancements_js_syntax():
    if not CANVAS_JS.is_file():
        pytest.fail("canvas_enhancements.js missing")
    node = _node_or_skip()
    proc = subprocess.run(
        [node, "--check", str(CANVAS_JS)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_canvas_enhancements_pure_helpers_pass_node_suite():
    """Pure zoom/minimap/sanitize helpers are unit tested with plain Node."""
    node = _node_or_skip()
    assert JS_TESTS.is_file(), "node helper test suite missing"
    proc = subprocess.run(
        [node, str(JS_TESTS)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_js_edge_geometry_matches_python_with_zero_inset():
    """JS mirrors canvas_geometry.py; the default arrow inset is the only delta."""
    import json

    from cn_social_agent.content.canvas_geometry import curve_path, edge_endpoints

    pairs = [
        ({"x": 0, "y": 0, "w": 240, "h": 150}, {"x": 600, "y": 400, "w": 200, "h": 120}),
        ({"x": 120, "y": 80, "w": 240, "h": 150}, {"x": 120, "y": 600, "w": 240, "h": 150}),
        ({"x": 800, "y": 200, "w": 200, "h": 200}, {"x": 200, "y": 200, "w": 200, "h": 200}),
    ]
    script = (
        "require('./src/cn_social_agent/workbench/canvas_enhancements.js');"
        "const CE=globalThis.CanvasEnhancements;"
        f"const pairs={json.dumps(pairs)};"
        "const out=pairs.map(([a,b])=>({"
        "ep:CE.edgeGeometry.edgeEndpoints(a,b,0),"
        "d:CE.edgeGeometry.curvePath(a,b,0)}));"
        "console.log(JSON.stringify(out));"
    )
    got = json.loads(_run_node_script(script))
    for (a, b), row in zip(pairs, got):
        x1, y1, x2, y2 = edge_endpoints(a, b)
        assert abs(row["ep"]["x1"] - x1) < 1e-6
        assert abs(row["ep"]["y1"] - y1) < 1e-6
        assert abs(row["ep"]["x2"] - x2) < 1e-6
        assert abs(row["ep"]["y2"] - y2) < 1e-6
        assert row["d"] == curve_path(a, b)


def test_dialog_and_menu_are_reentrant_and_accessible():
    js = CANVAS_JS.read_text(encoding="utf-8")
    html = _html()
    # Dialog message is announced.
    assert 'aria-describedby="wbDialogMessage"' in html
    assert "aria-describedby" in js
    # Listeners are torn down as a group instead of stacking per open.
    assert "AbortController" in js
    # Re-entrant opens settle the previous dialog rather than throwing.
    assert re.search(r"activeDialog|dialogQueue", js)
    # Context menu no longer defers listener attachment through setTimeout.
    assert "setTimeout(() => {\n      document.addEventListener" not in js
    # Context menu keyboard navigation + focus restore.
    assert "ArrowDown" in js and "ArrowUp" in js
    assert re.search(r"menuPrevFocus|restoreFocus", js)


def test_minimap_is_keyboard_accessible():
    html = _html()
    mini = re.search(r'<div class="cv-minimap"[^>]*>', html)
    assert mini, "minimap element missing"
    tag = mini.group(0)
    assert 'tabindex="0"' in tag
    assert "aria-label" in tag
    js = CANVAS_JS.read_text(encoding="utf-8")
    assert "keydown" in js


def _function_body(block: str, name: str) -> str:
    """Slice a top-level canvas helper by its indentation-4 closing brace."""
    start = block.find(f"function {name}(")
    assert start > 0, f"{name} missing"
    end = block.find("\n    }\n", start)
    assert end > start, f"{name} body not delimited"
    return block[start:end]


def test_minimap_view_state_matches_module_contract():
    """Keyboard panning reads scroll offsets, so the page must supply them."""
    body = _function_body(_canvas_script_block(_html()), "canvasViewCenter")
    for key in ("scrollLeft", "scrollTop", "zoom", "clientWidth", "clientHeight"):
        assert f"{key}:" in body, f"canvasViewCenter must report {key} as a field"


def test_canvas_zoom_has_matching_scroll_extent():
    html = _html()
    block = _canvas_script_block(html)
    # A sizer element gives the scroll container an extent that matches the
    # CSS transform, which does not itself affect layout.
    assert 'id="canvasSizer"' in html
    assert "cv-sizer" in html
    assert "canvasSizer" in block
    # Scroll clamping reads the real scrollable size.
    assert "scrollWidth" in block and "scrollHeight" in block


def test_history_survives_arrange_and_ai_organize():
    block = _canvas_script_block(_html())
    assert "resetHistory" in block, "applyCanvasPayload must support keeping history"
    for fn in ("arrangeCanvas", "organizeCanvasWithAi"):
        start = block.find(f"function {fn}(")
        assert start > 0, f"{fn} missing"
        body = block[start : start + 1600]
        assert "resetHistory: false" in body, f"{fn} must not reset undo history"
        assert body.count("pushCanvasHistory()") >= 2, f"{fn} needs pre/post snapshots"


def test_autosave_failures_are_not_swallowed():
    block = _canvas_script_block(_html())
    assert "await saveCanvas().catch(() => {});" not in block
    start = block.find("async function flushCanvasSave(")
    assert start > 0
    body = block[start : start + 900]
    assert "throw" in body, "flush must propagate failures so callers abort"
    assert "dirty = true" in body, "failed flush keeps local edits dirty"


def test_canvas_navigation_never_swallows_errors():
    """Every loadCanvas entry point passes options and surfaces failures."""
    html = _html()
    for call in re.finditer(r"loadCanvas\((.{0,60})", html):
        arg = call.group(1)
        # Valid: no argument, an object literal, or a ternary between literals.
        if arg.startswith(")") or "{" in arg.split(")")[0]:
            continue
        pytest.fail(f"loadCanvas must be called with an options object, got: {arg!r}")
    assert "loadCanvas(pid).catch(() => {})" not in html
    for call in re.finditer(r"loadCanvas\(\{[^)]*\}\)\s*\.catch\(\(\) => \{\}\)", html):
        pytest.fail(f"canvas navigation swallows errors: {call.group(0)!r}")


def test_node_urls_are_sanitized_and_edits_snapshot_once():
    block = _canvas_script_block(_html())
    assert "sanitizeUrl" in block
    # No raw assignment of node.url into an anchor href.
    assert "link.href = node.url" not in block
    url_start = block.find("urlInput.oninput")
    assert url_start > 0
    body = block[url_start : url_start + 400]
    assert "_cvHist" in body, "url editing takes one history snapshot per session"


def test_pointer_interactions_clean_up_on_cancel():
    block = _canvas_script_block(_html())
    assert block.count("pointercancel") >= 2, "drag and resize both handle pointercancel"
