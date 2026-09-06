from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path


AGENT_LEARNING_DIR = Path(__file__).resolve().parents[3] / "agent-learning"
WEB_DOCS_DIR = AGENT_LEARNING_DIR / "docs" / "web"


def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name)
    return name[:100]


def enrich_kb_from_url(url: str, title: str, text: str) -> Path | None:
    if not url or not text:
        return None
    WEB_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = _sanitize_filename(title or "untitled")
    filename = f"{timestamp}_{url_hash}_{safe_title}.md"
    note_path = WEB_DOCS_DIR / filename
    content = f"""# {title}

> 来源: {url}
> 抓取时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{text[:8000]}
"""
    note_path.write_text(content, encoding="utf-8")
    return note_path
