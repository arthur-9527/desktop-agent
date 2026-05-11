"""
远程桌面控制 Agent - 入口
"""
import asyncio
import argparse
import logging

from config import LOG_LEVEL
from desktop import DesktopController
from llm import LLMClient
from agent import RemoteDesktopAgent


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="远程桌面控制 Agent")
    parser.add_argument(
        "-i", "--instruction",
        type=str,
        help="任务指令",
    )
    parser.add_argument(
        "-H", "--host",
        type=str,
        help="AgentDesk 主机地址",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        help="AgentDesk 端口",
    )
    parser.add_argument(
        "-t", "--token",
        type=str,
        help="AgentDesk 认证令牌",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        help="最大执行轮次",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="交互式模式",
    )
    args = parser.parse_args()

    setup_logging()

    # 创建 Agent
    desktop = DesktopController(
        host=args.host,
        port=args.port,
        token=args.token,
    )
    llm = LLMClient()
    agent = RemoteDesktopAgent(
        desktop=desktop,
        llm=llm,
        max_iterations=args.max_iterations or 10,
    )

    # 检查 AgentDesk 连接
    if not desktop.is_available():
        print("❌ 无法连接到 AgentDesk，请检查配置")
        return

    print("✅ AgentDesk 连接成功")
    print(f"   主机: {desktop.host}:{desktop.port}")
    print()

    # 交互式模式
    if args.interactive:
        while True:
            instruction = input("\n请输入任务指令 (输入 'quit' 退出): ").strip()
            if instruction.lower() in ["quit", "exit", "q"]:
                break
            if not instruction:
                continue

            asyncio.run(agent.run_interactive(instruction))
        return

    # 命令行模式
    if args.instruction:
        result = asyncio.run(agent.run(args.instruction))
        print(f"\n{'='*50}")
        if result["success"]:
            print("✅ 任务完成!")
        else:
            print("❌ 任务失败")
        print(f"消息: {result['message']}")
        print(f"{'='*50}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()