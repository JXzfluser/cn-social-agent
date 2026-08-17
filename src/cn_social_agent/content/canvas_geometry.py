"""Canvas edge geometry — boundary endpoints and cubic SVG curves."""

from __future__ import annotations

from typing import Any


def _center(node: dict[str, Any]) -> tuple[float, float]:
    x = float(node.get("x") or 0)
    y = float(node.get("y") or 0)
    w = max(1.0, float(node.get("w") or 240))
    h = max(1.0, float(node.get("h") or 150))
    return x + w / 2.0, y + h / 2.0


def _bounds(node: dict[str, Any]) -> tuple[float, float, float, float]:
    x = float(node.get("x") or 0)
    y = float(node.get("y") or 0)
    w = max(1.0, float(node.get("w") or 240))
    h = max(1.0, float(node.get("h") or 150))
    return x, y, x + w, y + h


def _ray_rect_exit(
    cx: float, cy: float, dx: float, dy: float, node: dict[str, Any]
) -> tuple[float, float]:
    """Intersect center→direction ray with the node rectangle; return exit point."""
    left, top, right, bottom = _bounds(node)
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        # Identical / overlapping centers: nudge toward the right edge mid.
        return right, cy

    candidates: list[tuple[float, float, float]] = []  # (t, x, y)
    if abs(dx) > 1e-9:
        for edge_x in (left, right):
            t = (edge_x - cx) / dx
            if t > 1e-9:
                py = cy + t * dy
                if top - 1e-6 <= py <= bottom + 1e-6:
                    candidates.append((t, edge_x, max(top, min(bottom, py))))
    if abs(dy) > 1e-9:
        for edge_y in (top, bottom):
            t = (edge_y - cy) / dy
            if t > 1e-9:
                px = cx + t * dx
                if left - 1e-6 <= px <= right + 1e-6:
                    candidates.append((t, max(left, min(right, px)), edge_y))

    if not candidates:
        # Fallback: closest side mid toward the direction.
        if abs(dx) >= abs(dy):
            return (right if dx >= 0 else left), cy
        return cx, (bottom if dy >= 0 else top)

    candidates.sort(key=lambda item: item[0])
    _, px, py = candidates[0]
    return px, py


def edge_endpoints(
    source: dict[str, Any], target: dict[str, Any]
) -> tuple[float, float, float, float]:
    """Return (x1, y1, x2, y2) on the source/target rectangle boundaries."""
    sx, sy = _center(source)
    tx, ty = _center(target)
    dx, dy = tx - sx, ty - sy
    x1, y1 = _ray_rect_exit(sx, sy, dx, dy, source)
    x2, y2 = _ray_rect_exit(tx, ty, -dx, -dy, target)
    return x1, y1, x2, y2


def curve_path(source: dict[str, Any], target: dict[str, Any]) -> str:
    """SVG cubic path from source boundary to target boundary."""
    x1, y1, x2, y2 = edge_endpoints(source, target)
    dx = x2 - x1
    dy = y2 - y1
    # Mild S-curve: control points offset perpendicular to the chord.
    # For horizontal/vertical, still produces a readable bend.
    ox = -dy * 0.18
    oy = dx * 0.18
    # Soften when nearly aligned so short vertical/horizontal edges stay tidy.
    dist = (dx * dx + dy * dy) ** 0.5
    if dist < 1e-6:
        ox, oy = 24.0, 0.0
    c1x, c1y = x1 + dx * 0.35 + ox, y1 + dy * 0.35 + oy
    c2x, c2y = x2 - dx * 0.35 + ox, y2 - dy * 0.35 + oy
    return f"M {x1:.2f} {y1:.2f} C {c1x:.2f} {c1y:.2f} {c2x:.2f} {c2y:.2f} {x2:.2f} {y2:.2f}"
