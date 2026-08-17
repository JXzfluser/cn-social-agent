"""
发布流程验证测试

包含:
1. 模拟发布测试（无需真实 token）
2. publish_single 函数测试
3. 审核通过后发布集成测试
4. 完整用户操作流程文档

运行方式:
    python -m scripts.test_publish_flow
"""

import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from pathlib import Path
import sys

# 设置路径 - 处理 cn_social_agent 符号链接
script_dir = Path(__file__).parent.parent.resolve()
src_path = script_dir / "src"
sys.path.insert(0, str(src_path))

# 添加项目根目录以便 cn_social_agent.auth_core 可以正确导入
sys.path.insert(0, str(script_dir))


def print_section(title: str) -> None:
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print("=" * 60)


def print_result(label: str, value) -> None:
    """打印结果"""
    print(f"  {label}: {value}")


async def mock_publish_single():
    """
    模拟发布测试 - 无需真实 token
    测试 publish_single 函数的基本调用流程
    """
    print_section("1. 模拟发布测试 (publish_single)")

    from cn_social_agent.social.publisher import publish_single, SocialPublisher

    # 直接 patch _do_publish 方法，模拟发布成功
    async def mock_do_publish(self, post, platform, account):
        return True

    with patch.object(SocialPublisher, '_do_publish', mock_do_publish):
        result = await publish_single(
            platform="dingtalk",
            content="测试内容",
            title="测试标题"
        )

        print_result("平台", result.platform)
        print_result("成功", result.success)
        print_result("消息", result.message)
        print_result("时间戳", result.timestamp)
        print_result("重试次数", result.retry_count)

        return result


async def mock_publish_with_accounts():
    """
    测试使用配置账号发布
    模拟完整的账号配置场景
    """
    print_section("2. 使用账号配置发布测试")

    from cn_social_agent.social.publisher import SocialPublisher
    from cn_social_agent.social.models import PlatformAccount, Post

    # 创建模拟账号配置
    accounts = {
        "dingtalk": PlatformAccount(
            platform="dingtalk",
            account_id="mock_dingtalk_id",
            access_token="mock_webhook_token_abc123"
        ),
        "feishu": PlatformAccount(
            platform="feishu",
            account_id="mock_feishu_id",
            access_token="mock_feishu_webhook_xyz789"
        )
    }

    publisher = SocialPublisher(accounts)

    # 直接 patch _do_publish 方法，模拟发布成功
    async def mock_do_publish(self, post, platform, account):
        return True

    with patch.object(SocialPublisher, '_do_publish', mock_do_publish):
        result = await publisher.post_to_platform(
            platform="dingtalk",
            content="这是一条测试消息，用于验证发布流程",
            title="发布流程验证"
        )

        print_result("平台", result.platform)
        print_result("成功", result.success)
        print_result("消息", result.message)

        return result


async def mock_review_then_publish():
    """
    测试审核通过后发布集成
    模拟完整的工作流: 提交审核 -> 审核通过 -> 发布
    """
    print_section("3. 审核通过后发布集成测试")

    from cn_social_agent.review.db import (
        submit_review, approve_review, ReviewRequestDB
    )
    from cn_social_agent.social.publisher import publish_single

    # 步骤 1: 提交审核
    print("\n  [步骤 1] 提交审核请求...")
    request_id = submit_review(
        content="【新品发布】限时优惠活动开始！\n\n好消息！我们推出全新产品，现在购买享受8折优惠。\n#新品 #优惠",
        title="新品发布推广",
        platforms=["dingtalk", "feishu"],
        created_by="test_user",
        analysis_data={"quality_score": 85, "violation_level": "safe"}
    )
    print_result("审核请求ID", request_id)

    # 验证审核请求已创建
    record = ReviewRequestDB.get_by_id(request_id)
    print_result("审核状态", record["status"])
    print_result("内容预览", record["content"][:50] + "...")

    # 步骤 2: 审核通过
    print("\n  [步骤 2] 审核通过...")
    result = approve_review(request_id, "admin_user")
    print_result("审核成功", result["success"])
    print_result("通过的平台", result["approved_platforms"])
    print_result("发布内容", result["content"][:50] + "...")

    # 验证状态已更新
    record = ReviewRequestDB.get_by_id(request_id)
    print_result("更新后状态", record["status"])

    # 步骤 3: 发布（模拟）
    print("\n  [步骤 3] 执行发布...")

    from cn_social_agent.social.publisher import SocialPublisher

    # 直接 patch _do_publish 方法，模拟发布成功
    async def mock_do_publish(self, post, platform, account):
        return True

    with patch.object(SocialPublisher, '_do_publish', mock_do_publish):
        publish_result = await publish_single(
            platform="dingtalk",
            content=result["content"],
            title=result["title"]
        )

        print_result("发布平台", publish_result.platform)
        print_result("发布成功", publish_result.success)
        print_result("发布消息", publish_result.message)

    return {
        "request_id": request_id,
        "review_result": result,
        "publish_result": publish_result
    }


async def mock_multi_platform_publish():
    """
    测试多平台发布
    """
    print_section("4. 多平台发布测试")

    from cn_social_agent.social.publisher import SocialPublisher
    from cn_social_agent.social.models import PlatformAccount, Post

    accounts = {
        "dingtalk": PlatformAccount(platform="dingtalk", account_id="dt_id", access_token="dt_token"),
        "feishu": PlatformAccount(platform="feishu", account_id="fs_id", access_token="fs_token"),
        "wecom": PlatformAccount(platform="wecom", account_id="wc_id", access_token="wc_token"),
    }

    publisher = SocialPublisher(accounts)
    post = Post(
        title="多平台统一发布测试",
        content="这是一条同时发布到多个平台的消息"
    )

    # 直接 patch _do_publish 方法，模拟发布成功
    async def mock_do_publish(self, post, platform, account):
        return True

    with patch.object(SocialPublisher, '_do_publish', mock_do_publish):
        results = await publisher.publish(post, ["dingtalk", "feishu", "wecom"])

    print_result("钉钉结果", results.get("dingtalk"))
    print_result("飞书结果", results.get("feishu"))
    print_result("企业微信结果", results.get("wecom"))

    return results


def print_token_configuration_guide():
    """
    打印 Token 配置指南
    """
    print_section("附录: Token 配置指南")

    print("""
  当需要使用真实 token 时，按以下步骤配置:

  1. 钉钉 (DingTalk)
  ------------------
  环境变量:
    DINTTALK_APP_KEY=your_app_key
    DINTTALK_APP_SECRET=your_app_secret

  Webhook Token (可选，用于机器人消息):
    在账号配置中设置 access_token 为 Webhook 地址的 token 部分

  2. 飞书 (Feishu)
  ----------------
  环境变量:
    FEISHU_APP_ID=your_app_id
    FEISHU_APP_SECRET=your_app_secret

  Webhook Token:
    在账号配置中设置 access_token 为群机器人的 Webhook token

  3. 企业微信 (WeCom)
  -----------------
  环境变量:
    WECOM_CORP_ID=your_corp_id
    WECOM_SECRET=your_secret

  Webhook Token:
    在账号配置中设置 access_token 为机器人 Webhook 的 key

  4. 微信公众号 (Weixin)
  ---------------------
  环境变量:
    WEIXIN_APP_ID=your_app_id
    WEIXIN_APP_SECRET=your_app_secret

  5. 配置方式
  ---------
  a) 环境变量 (推荐):
     export DINTTALK_APP_KEY=xxx
     export DINTTALK_APP_SECRET=xxx

  b) .env 文件:
     DINTTALK_APP_KEY=xxx
     DINTTALK_APP_SECRET=xxx

  c) config.yaml:
     platforms:
       dingtalk_app_key: xxx
       dingtalk_app_secret: xxx
""")


def print_user_flow_doc():
    """
    打印完整用户操作流程文档
    """
    print_section("附录: 完整用户操作流程文档")

    print("""
  ┌─────────────────────────────────────────────────────────────┐
  │                    用户操作流程                              │
  └─────────────────────────────────────────────────────────────┘

  【第一步】内容输入
  ────────────────
  1. 用户在 Web界面输入主题或关键词
  2. 系统自动抓取相关信息或等待用户输入内容
  3. 用户编辑和调整内容

  【第二步】质量分析
  ────────────────
  1. 系统对内容进行质量评分 (0-100)
  2. 检查违规内容 (安全/警告/违规)
  3. 提供修改建议（如有违规）

  【第三步】选择平台
  ────────────────
  1. 用户选择要发布的平台 (可多选)
  2. 支持的平台:
     - 钉钉 DingTalk
     - 飞书 Feishu
     - 企业微信 WeCom
     - 微信公众号 Weixin
     - 小红书 XiaoHongShu
     - 微博 Weibo

  【第四步】提交审核
  ────────────────
  1. 用户点击"提交审核"按钮
  2. 系统创建审核请求，状态变为 "pending"
  3. 管理员收到审核通知

  【第五步】审核流程
  ────────────────
  管理员操作:
  1. 登录管理后台
  2. 查看待审核列表
  3. 可执行操作:
     - 审核通过 → 内容进入发布队列
     - 审核拒绝 → 用户需修改后重新提交
     - 请求修改 →发送修改建议给用户

  【第六步】自动发布
  ────────────────
  1. 审核通过后，系统自动触发发布
  2. 发布到所有审核通过的平台
  3. 更新审核请求状态为 "published"
  4. 记录发布结果和发布时间

  【第七步】查看结果
  ────────────────
  1. 用户可在"我的发布"查看历史记录
  2. 查看每条内容的发布状态
  3. 如有发布失败，可查看失败原因

  ┌─────────────────────────────────────────────────────────────┐
  │                    API 调用流程 │
  └─────────────────────────────────────────────────────────────┘

  后端 API 调用顺序:

  1. OAuth 授权
     POST /api/oauth/{platform}/authorize
     →跳转到平台授权页面

  2.回调处理
     GET /api/oauth/{platform}/callback
     → 保存 auth_code 和 access_token

  3. 提交审核
     POST /api/review/submit
     { content, title, platforms }
     → 返回 request_id

  4. 审核操作 (管理员)
     POST /api/review/approve/{request_id}
     POST /api/review/reject/{request_id}

  5. 发布
     POST /api/publish/{platform}
     { content, title }
     → 返回发布结果

  6. 查询状态
     GET /api/review/status/{request_id}
     GET /api/publish/history
""")


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("        发布流程验证测试")
    print(" (模拟模式 - 无需真实 Token)")
    print("=" * 60)

    # 初始化数据库
    from cn_social_agent.auth_core import init_db
    init_db()

    # 运行测试
    try:
        # 1. 模拟发布测试
        await mock_publish_single()

        # 2. 使用账号配置发布测试
        await mock_publish_with_accounts()

        # 3. 审核通过后发布集成测试
        await mock_review_then_publish()

        # 4. 多平台发布测试
        await mock_multi_platform_publish()

        # 打印配置指南和用户流程
        print_token_configuration_guide()
        print_user_flow_doc()

        print("\n" + "=" * 60)
        print("  所有测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())