#!/usr/bin/env python3
"""服务健康检查脚本"""

import asyncio
from openai import AsyncOpenAI

from src.agentdesk_client import AgentDeskClient
from src.config import get_config
from src.utils import check_services


async def main():
    """主函数"""
    config = get_config()

    # AgentDesk 客户端
    client = AgentDeskClient(
        host=config.agentdesk_host,
        port=config.agentdesk_port,
        token=config.agentdesk_token,
    )

    # UI-TARS 模型客户端
    model = AsyncOpenAI(
        base_url=config.vision_base_url,
        api_key=config.vision_api_key,
    )

    # 检查服务
    result = await check_services(client, model, config)

    print("\n" + "=" * 50)
    if result:
        print("✓ 所有服务正常")
    else:
        print("✗ 部分服务异常，请检查配置")
    print("=" * 50)

    # 关闭连接
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
