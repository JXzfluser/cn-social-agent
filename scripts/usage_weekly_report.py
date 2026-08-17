#!/usr/bin/env python3
"""Print internal FDE usage / cost weekly report (JSONL based, no billing)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cn_social_agent.usage.meter import format_weekly_report, weekly_summary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Usage weekly report for FDE pilots")
    parser.add_argument("--days", type=int, default=7, help="Lookback window (default 7)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of markdown text",
    )
    parser.add_argument(
        "--path",
        type=str,
        default="",
        help="Override USAGE_LOG_PATH / default data/usage/<customer>/events.jsonl",
    )
    args = parser.parse_args()
    path = Path(args.path) if args.path else None
    summary = weekly_summary(days=max(1, args.days), path=path)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(format_weekly_report(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
