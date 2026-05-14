#!/usr/bin/env python3
"""DeskAgent 主入口 - 三模型架构

三模型架构：
- Planner (LLM): 主循环决策（每轮）
- Grounding (UI-TARS): 视觉定位（按需）
- Calibrator (LLM): 周期校准（每 N 步）
"""

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

    # UI-TARS 视觉模型客户端 (Grounding)
    vision_model = AsyncOpenAI(
        base_url=config.vision_base_url,
        api_key=config.vision_api_key,
    )

    # Planner LLM 客户端
    planner_model = AsyncOpenAI(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
    )

    # Calibrator LLM 客户端（未配置时复用 Planner）
    calibrator_model = None
    if config.calibration_base_url:
        calibrator_model = AsyncOpenAI(
            base_url=config.calibration_base_url or config.llm_base_url,
            api_key=config.calibration_api_key or config.llm_api_key,
        )

    # 检查服务
    if not await check_services(client, vision_model, config):
        print("\n服务检查失败，请检查配置后重试。")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("DeskAgent 已就绪 (三模型架构)")
    print("=" * 50)
    print(f"  Planner: {config.general_model}")
    print(f"  Vision:  {config.vision_model}")
    if config.calibration_interval > 0:
        calibration_model = config.calibration_model or config.general_model
        print(f"  Calibrator: {calibration_model} (每 {config.calibration_interval} 步)")
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
        vision_model=vision_model,
        planner_model=planner_model,
        calibrator_model=calibrator_model,
        config=config,
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
    
    # Metrics 报告
    if result.get('metrics'):
        metrics = result['metrics']
        print("\nMetrics:")
        print(f"  成功率: {metrics.get('success_rate', 'N/A')}")
        print(f"  总耗时: {metrics.get('total_time_s', 0)}s")
        print(f"  模型调用: Planner={metrics.get('model_calls', {}).get('planner', 0)}, "
              f"Vision={metrics.get('model_calls', {}).get('vision', 0)}, "
              f"Calibrator={metrics.get('model_calls', {}).get('calibrator', 0)}")

    # 关闭连接
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())