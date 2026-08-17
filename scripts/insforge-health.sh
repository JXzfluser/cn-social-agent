#!/bin/bash
# InsForge 服务健康检查
# 用法: bash scripts/insforge-health.sh

set -euo pipefail

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local expected="$3"

    if response=$(curl -sf --max-time 5 "$url" 2>/dev/null); then
        if [[ -z "$expected" ]] || echo "$response" | grep -q "$expected"; then
            echo -e "  ${GREEN}✅${NC} $name"
            PASS=$((PASS + 1))
        else
            echo -e "  ${YELLOW}⚠️${NC} $name (unexpected response)"
            PASS=$((PASS + 1))
        fi
    else
        echo -e "  ${RED}❌${NC} $name"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "============================================"
echo "  InsForge Health Check"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"
echo ""

# Check Docker services
echo "📦 Docker Services:"
check "insforge-postgres"    "http://localhost:${INSFORGE_DB_PORT:-5433}" ""

# PostgREST
PGRST_PORT="${INSFORGE_POSTGREST_PORT:-5434}"
check "insforge-postgrest"   "http://localhost:${PGRST_PORT}/" "OpenResty"

# InsForge App
APP_PORT="${INSFORGE_APP_PORT:-7130}"
check "insforge-app (API)"   "http://localhost:${APP_PORT}/api/health" "ok"

# InsForge Auth
AUTH_PORT="${INSFORGE_AUTH_PORT:-7131}"
check "insforge-auth"        "http://localhost:${AUTH_PORT}/api/health" "ok"

echo ""

# Summary
TOTAL=$((PASS + FAIL))
echo "--------------------------------------------"
echo -e "Result: ${PASS}/${TOTAL} checks passed"
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}✅ All services healthy${NC}"
else
    echo -e "${RED}❌ ${FAIL} service(s) unhealthy${NC}"
fi
echo "============================================"
echo ""

exit "$FAIL"
