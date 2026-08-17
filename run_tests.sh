#!/bin/bash
# 发布流程测试脚本
# 运行方式: ./run_tests.sh

set -e

echo "========================================"
echo "CN-Social-Agent 发布流程测试"
echo "========================================"

# 激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 运行测试
echo ""
echo "运行发布流程测试..."
python -m pytest tests/test_publish_workflow.py -v --tb=short

echo ""
echo "========================================"
echo "测试完成"
echo "========================================"