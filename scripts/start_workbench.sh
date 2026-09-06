#!/usr/bin/env bash
# Nexus 工作台标准启动（生产姿势）
# 要点：env -i 清掉 WorkBuddy 沙箱的 broker 变量，否则服务内 npm/vite 会
# 被 CODEBUDDY_BROKER_DENY 卡死（讲解演示 build 依赖 npm）。
set -e
cd "$(dirname "$0")/.."
if [ -f .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
lsof -ti :18080 2>/dev/null | xargs -r kill 2>/dev/null || true
sleep 1
"$PY" scripts/ensure_workbench_tables.py > /dev/null 2>&1 || true
exec env -i \
  HOME="$HOME" \
  PATH="/Users/zfl/.workbuddy/binaries/node/versions/22.22.2-2/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
  PYTHONPATH=src \
  WORKBENCH_STORE=insforge \
  WORKBENCH_AUTH=auto \
  WORKBENCH_HOST=127.0.0.1 \
  WORKBENCH_PORT=18080 \
  "$PY" run_workbench.py
