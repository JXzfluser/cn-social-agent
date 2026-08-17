#!/usr/bin/env python3
"""
CN-Social-Agent 快速测试脚本

用法：
    python scripts/demo.py "帮你写一条推广AI产品的朋友圈"
"""
import asyncio
import os
import sys

from cn_social_agent import AIAgent, AgentConfig
from cn_social_agent.llm import MiniMaxLLM


async def main(prompt: str = "你好，请介绍一下你自己"):
    """简单的对话测试"""

    # 读取 API Key
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        print("错误：未设置 MINIMAX_API_KEY 环境变量")
        print("请在 .env 文件中设置：MINIMAX_API_KEY=你的API密钥")
        return

    print(f"使用模型: MiniMax-Text-01")
    print(f"输入: {prompt}")
    print("-" * 50)

    # 1. 初始化 LLM
    llm = MiniMaxLLM(api_key=api_key)

    # 2. 初始化 Agent
    agent = AIAgent(
        config=AgentConfig(
            model="MiniMax-Text-01",
            system_prompt="你是一个友好的社交媒体运营助手，帮助用户生成社交媒体内容。"
        ),
        llm_provider=llm
    )

    # 3. 运行
    print("正在生成回复...")
    response = await agent.run(prompt)

    # 4. 输出结果
    print("-" * 50)
    print("AI 回复:")
    print(response.content)

    if response.tool_calls:
        print("-" * 50)
        print(f"工具调用: {len(response.tool_calls)} 次")


if __name__ == "__main__":
    # 从命令行参数或使用默认提示
    prompt = sys.argv[1] if len(sys.argv) > 1 else "你好，请介绍一下你自己"

    asyncio.run(main(prompt))
