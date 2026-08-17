#!/usr/bin/env python3
"""InsForge Agent Workbench entrypoint."""

from __future__ import annotations

import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(project_root, "src")
if src in sys.path:
    sys.path.remove(src)
sys.path.insert(0, src)

def _load_env_file(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(project_root, ".env"))
    load_dotenv(os.path.join(project_root, "insforge", ".env"))
except ImportError:
    _load_env_file(os.path.join(project_root, ".env"))
    _load_env_file(os.path.join(project_root, "insforge", ".env"))

from aiohttp import web

from cn_social_agent.api import create_app


def main() -> None:
    host = os.getenv("WORKBENCH_HOST", "0.0.0.0")
    port = int(os.getenv("WORKBENCH_PORT", "8080"))
    print("=" * 50)
    print("CN-Social-Agent Workbench")
    print("=" * 50)
    print(f"  UI:     http://127.0.0.1:{port}/")
    print(f"  Health: http://127.0.0.1:{port}/health")
    print(f"  Store:  {os.getenv('WORKBENCH_STORE', 'memory')}")
    print(f"  LLM:    {os.getenv('WORKBENCH_LLM', 'mock')}")
    print("=" * 50)
    web.run_app(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
