#!/usr/bin/env python3
"""DeskAgent 主入口"""

import asyncio
import sys
from openai import AsyncOpenAI

from src.agentdesk_client import AgentDeskClient
from src.agent_loop import DeskAgent
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

    # UI-TARS 1.5 模型客户端
    model = AsyncOpenAI(
        base_url=config.vision_base_url,
        api_key=config.vision_api_key,
    )

    # 检查服务
    if not await check_services(client, model, config):
        print("\n服务检查失败，请检查配置后重试。")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("DeskAgent 已就绪")
    print("=" * 50)

    # 获取任务
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = input("\n请输入任务: ")

    if not task.strip():
        print("任务不能为空")
        sys.exit(1)

    print(f"\n开始执行任务: {task}")
    print("=" * 50)

    # 创建 Agent
    agent = DeskAgent(
        agentdesk=client,
        model=model,
        model_name=config.vision_model,
        max_steps=config.max_iterations,
        context_window_size=config.context_window_size,
        debug=config.debug,
    )

    # 执行任务
    result = await agent.run(task)

    # 输出结果
    print("\n" + "=" * 50)
    print("执行结果")
    print("=" * 50)
    print(f"状态: {'成功 ✓' if result['success'] else '失败 ✗'}")
    print(f"步骤: {result['steps']}")
    print(f"信息: {result['message']}")

    # 关闭连接
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())