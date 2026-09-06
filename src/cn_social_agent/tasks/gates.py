"""Machine-checkable acceptance gates.

Each gate turns one rubric item into a :class:`Finding`. Gates are pure
functions of ``(rubric item, gate context)`` — no I/O, no LLM — so they are
fast, deterministic and exhaustively testable. That determinism is what lets
the workbench make a credible claim that a task "passed acceptance".

Adding a gate means writing a function and registering it in ``GATES``; expert
packs then reference it by name.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from cn_social_agent.experts.models import RubricItem, pick

from .models import Artifact, Finding, Task


@dataclass
class GateContext:
    """Everything a gate is allowed to look at."""

    task: Task
    artifacts: list[Artifact]
    brief: str = ""
    locale: str = "zh-CN"
    options: dict = field(default_factory=dict)

    def artifact_of_kind(self, kind: str) -> Optional[Artifact]:
        for artifact in self.artifacts:
            if artifact.kind == kind:
                return artifact
        return None

    @property
    def primary(self) -> Optional[Artifact]:
        return self.artifacts[0] if self.artifacts else None

    @property
    def text(self) -> str:
        return self.primary.content if self.primary else ""

    def json_body(self) -> Optional[Any]:
        """Parse the primary artifact as JSON, tolerating code fences."""
        raw = self.text
        if not raw:
            return None
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except ValueError:
            return None


Gate = Callable[[RubricItem, GateContext], Finding]


def _finding(item: RubricItem, ctx: GateContext, passed: bool, message: str = "") -> Finding:
    return Finding(
        item_id=item.id,
        title=pick(item.title, ctx.locale),
        passed=passed,
        severity=item.severity,
        kind="auto",
        message=message or pick(item.hint, ctx.locale),
    )


# ── gates ────────────────────────────────────────────────────────


def gate_artifact_exists(item: RubricItem, ctx: GateContext) -> Finding:
    kind = (item.params.get("kind") or "").strip()
    if not ctx.artifacts:
        return _finding(item, ctx, False, "no artifacts produced")
    if kind:
        match = ctx.artifact_of_kind(kind)
        if match is None:
            return _finding(
                item, ctx, False, f"no artifact of kind '{kind}' (got: "
                + ", ".join(a.kind for a in ctx.artifacts) + ")"
            )
        if not (match.content or match.storage_key):
            return _finding(item, ctx, False, f"artifact '{kind}' is empty")
    return _finding(item, ctx, True, "artifact present")


def gate_text_length(item: RubricItem, ctx: GateContext) -> Finding:
    text = ctx.text
    length = len(text)
    minimum = int(item.params.get("min") or 0)
    maximum = int(item.params.get("max") or 0)
    if minimum and length < minimum:
        return _finding(item, ctx, False, f"length {length} < min {minimum}")
    if maximum and length > maximum:
        return _finding(item, ctx, False, f"length {length} > max {maximum}")
    return _finding(item, ctx, True, f"length {length}")


def gate_required_sections(item: RubricItem, ctx: GateContext) -> Finding:
    candidates = [str(s) for s in (item.params.get("any_of") or [])]
    required_all = [str(s) for s in (item.params.get("all_of") or [])]
    text = ctx.text
    if required_all:
        missing = [s for s in required_all if s not in text]
        if missing:
            return _finding(item, ctx, False, "missing sections: " + ", ".join(missing))
        return _finding(item, ctx, True, "all required sections present")
    if not candidates:
        return _finding(item, ctx, True, "no section requirement")
    min_matches = int(item.params.get("min_matches") or 1)
    hits = [s for s in candidates if s in text]
    if len(hits) < min_matches:
        return _finding(
            item, ctx, False,
            f"matched {len(hits)}/{min_matches} expected sections",
        )
    return _finding(item, ctx, True, f"matched sections: {len(hits)}")


def gate_forbidden_patterns(item: RubricItem, ctx: GateContext) -> Finding:
    patterns = [str(p) for p in (item.params.get("patterns") or [])]
    if not patterns:
        return _finding(item, ctx, True, "no forbidden patterns")

    scope = (item.params.get("scope") or "").strip()
    haystack = ctx.text
    if scope == "first_scene":
        data = ctx.json_body()
        scenes = (data or {}).get("scenes") if isinstance(data, dict) else None
        if isinstance(scenes, list) and scenes:
            haystack = json.dumps(scenes[0], ensure_ascii=False)
    elif scope:
        haystack = str((ctx.options or {}).get(scope) or ctx.text)

    for pattern in patterns:
        try:
            if re.search(pattern, haystack, flags=re.IGNORECASE):
                return _finding(item, ctx, False, f"forbidden pattern found: {pattern}")
        except re.error:
            if pattern in haystack:
                return _finding(item, ctx, False, f"forbidden text found: {pattern}")
    return _finding(item, ctx, True, "no forbidden patterns found")


_CJK_TOKEN = re.compile(r"[一-龥]{2,}")
_EN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}")


def _keywords(text: str) -> list[str]:
    tokens = _CJK_TOKEN.findall(text) + _EN_TOKEN.findall(text)
    seen: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if lowered not in seen:
            seen.append(lowered)
    return seen


def gate_keyword_present(item: RubricItem, ctx: GateContext) -> Finding:
    """Deliverable must actually talk about the requested subject."""
    source = ctx.task.title or ctx.brief or ""
    keywords = [str(k) for k in (item.params.get("keywords") or [])] or _keywords(source)
    if not keywords:
        return _finding(item, ctx, True, "no topic keywords to check")
    min_hits = int(item.params.get("min_hits") or 1)
    haystack = ctx.text.lower()
    hits = [k for k in keywords if _token_present(k, haystack)]
    if len(hits) < min_hits:
        return _finding(
            item, ctx, False,
            f"topic coverage {len(hits)}/{min_hits} — deliverable drifts from the brief",
        )
    return _finding(item, ctx, True, f"topic keywords matched: {len(hits)}")


def _token_present(token: str, haystack: str) -> bool:
    """Substring match, with CJK n-gram fallback.

    Chinese has no spaces, so a whole title becomes one token. Requiring that
    exact run to reappear would fail perfectly on-topic copy that merely
    paraphrases, so long CJK tokens fall back to any 3-character window.
    """
    lowered = token.lower()
    if lowered in haystack:
        return True
    if not _CJK_TOKEN.fullmatch(token) or len(token) < 4:
        return False
    window = 3
    return any(token[i : i + window] in haystack for i in range(len(token) - window + 1))


def gate_json_fields(item: RubricItem, ctx: GateContext) -> Finding:
    fields = [str(f) for f in (item.params.get("fields") or [])]
    data = ctx.json_body()
    if data is None:
        return _finding(item, ctx, False, "artifact is not valid JSON")
    if not isinstance(data, dict):
        return _finding(item, ctx, False, "JSON root is not an object")
    missing = [f for f in fields if f not in data]
    if missing:
        return _finding(item, ctx, False, "missing fields: " + ", ".join(missing))
    return _finding(item, ctx, True, "all required fields present")


def gate_scene_count(item: RubricItem, ctx: GateContext) -> Finding:
    data = ctx.json_body()
    scenes = (data or {}).get("scenes") if isinstance(data, dict) else None
    if not isinstance(scenes, list):
        return _finding(item, ctx, False, "no scenes array")
    count = len(scenes)
    minimum = int(item.params.get("min") or 0)
    maximum = int(item.params.get("max") or 0)
    if minimum and count < minimum:
        return _finding(item, ctx, False, f"{count} scenes < min {minimum}")
    if maximum and count > maximum:
        return _finding(item, ctx, False, f"{count} scenes > max {maximum}")
    return _finding(item, ctx, True, f"{count} scenes")


def gate_card_count(item: RubricItem, ctx: GateContext) -> Finding:
    data = ctx.json_body()
    cards = (data or {}).get("cards") if isinstance(data, dict) else None
    if not isinstance(cards, list):
        return _finding(item, ctx, False, "no cards array")
    count = len(cards)
    minimum = int(item.params.get("min") or 0)
    maximum = int(item.params.get("max") or 0)
    if minimum and count < minimum:
        return _finding(item, ctx, False, f"{count} cards < min {minimum}")
    if maximum and count > maximum:
        return _finding(item, ctx, False, f"{count} cards > max {maximum}")
    return _finding(item, ctx, True, f"{count} cards")


def gate_storyboard_duration(item: RubricItem, ctx: GateContext) -> Finding:
    """Total storyboard duration must respect the requested budget."""
    data = ctx.json_body()
    if not isinstance(data, dict):
        return _finding(item, ctx, False, "artifact is not valid JSON")
    budget = _duration_budget(ctx)
    tolerance = float(item.params.get("tolerance") or 1.0)

    total = data.get("total_duration")
    if total is None:
        scenes = data.get("scenes")
        if isinstance(scenes, list):
            total = sum(_to_float(s.get("duration")) for s in scenes if isinstance(s, dict))
    total = _to_float(total)
    if total <= 0:
        scenes = data.get("scenes")
        if isinstance(scenes, list) and scenes:
            # Fall back to narration pacing: ~4.5 chars per second of speech.
            total = sum(
                max(1.0, len(str(s.get("narration") or "")) / 4.5)
                for s in scenes
                if isinstance(s, dict)
            )
    if total <= 0:
        return _finding(item, ctx, False, "cannot determine total duration")

    if budget and total > budget * tolerance:
        return _finding(
            item, ctx, False,
            f"duration {total:.1f}s exceeds budget {budget}s (tolerance {tolerance})",
        )
    return _finding(item, ctx, True, f"duration {total:.1f}s within budget {budget}s")


def _duration_budget(ctx: GateContext) -> float:
    for source in (ctx.task.meta or {}, ctx.options or {}):
        for key in ("duration", "target_duration", "max_duration"):
            value = _to_float(source.get(key))
            if value > 0:
                return value
    return 0.0


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def gate_max_line_length(item: RubricItem, ctx: GateContext) -> Finding:
    """Every value of ``field`` inside a JSON array must be short enough."""
    field_name = str(item.params.get("field") or "")
    maximum = int(item.params.get("max") or 0)
    data = ctx.json_body()
    rows = _collect_rows(data)
    if not rows:
        return _finding(item, ctx, False, f"no rows to inspect for '{field_name}'")
    offenders = [
        str(row.get(field_name) or "")
        for row in rows
        if len(str(row.get(field_name) or "")) > maximum
    ]
    if offenders:
        sample = offenders[0][:40]
        return _finding(
            item, ctx, False,
            f"{len(offenders)} line(s) exceed {maximum} chars, e.g. “{sample}…”",
        )
    return _finding(item, ctx, True, f"all '{field_name}' lines within {maximum} chars")


def gate_min_line_length(item: RubricItem, ctx: GateContext) -> Finding:
    field_name = str(item.params.get("field") or "")
    minimum = int(item.params.get("min") or 0)
    data = ctx.json_body()
    rows = _collect_rows(data)
    if not rows:
        return _finding(item, ctx, False, f"no rows to inspect for '{field_name}'")
    thin = [
        str(row.get(field_name) or "")
        for row in rows
        if len(str(row.get(field_name) or "").strip()) < minimum
    ]
    if thin:
        return _finding(
            item, ctx, False,
            f"{len(thin)} '{field_name}' value(s) shorter than {minimum} chars",
        )
    return _finding(item, ctx, True, f"all '{field_name}' values meet minimum length")


def _collect_rows(data: Any) -> list[dict]:
    if not isinstance(data, dict):
        return []
    for key in ("scenes", "cards", "items", "slides"):
        value = data.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


GATES: dict[str, Gate] = {
    "artifact_exists": gate_artifact_exists,
    "text_length": gate_text_length,
    "required_sections": gate_required_sections,
    "forbidden_patterns": gate_forbidden_patterns,
    "keyword_present": gate_keyword_present,
    "json_fields": gate_json_fields,
    "scene_count": gate_scene_count,
    "card_count": gate_card_count,
    "storyboard_duration": gate_storyboard_duration,
    "max_line_length": gate_max_line_length,
    "min_line_length": gate_min_line_length,
}


def run_gate(item: RubricItem, ctx: GateContext) -> Finding:
    """Evaluate one rubric item, translating a missing gate into a failure."""
    gate = GATES.get(item.rule)
    if gate is None:
        return Finding(
            item_id=item.id,
            title=pick(item.title, ctx.locale),
            passed=False,
            severity=item.severity,
            kind="auto",
            message=f"unknown gate '{item.rule}' — cannot verify this criterion",
        )
    try:
        return gate(item, ctx)
    except Exception as exc:  # noqa: BLE001
        # A crashing gate must fail the item, never silently pass it.
        return Finding(
            item_id=item.id,
            title=pick(item.title, ctx.locale),
            passed=False,
            severity=item.severity,
            kind="auto",
            message=f"gate error: {exc}",
        )
