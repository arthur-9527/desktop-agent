#!/usr/bin/env python3
"""DesktopActions 交互式测试脚本

测试 6 个高层动作，每个动作执行后显示结果。
"""


import asyncio
import sys

try:
    from .actions import DesktopActions  # 包导入
except ImportError:
    from actions import DesktopActions  # 直接运行


DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9877
DEFAULT_TOKEN = "admin123"


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_success(msg: str):
    """打印成功消息"""
    print(f"✅ {msg}")


def print_error(msg: str):
    """打印错误消息"""
    print(f"❌ {msg}")


def input_int(prompt: str, default: int) -> int:
    """输入整数"""
    while True:
        try:
            value = input(f"{prompt} [{default}]: ").strip()
            if not value:
                return default
            return int(value)
        except ValueError:
            print("请输入有效的整数")


def input_str(prompt: str, default: str) -> str:
    """输入字符串"""
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else default


def input_optional_int(prompt: str) -> int | None:
    """输入可选整数"""
    value = input(f"{prompt} [可选，直接回车跳过]: ").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        print_error("输入无效，视为跳过")
        return None


class ActionsTester:
    """动作测试器"""

    def __init__(self):
        self.actions: DesktopActions | None = None

    async def init_client(self):
        """初始化客户端"""
        print_header("配置 AgentDesk 连接")
        host = input_str("主机地址", DEFAULT_HOST)
        port = input_int("HTTP 端口", DEFAULT_PORT)
        token = input_str("认证令牌", DEFAULT_TOKEN)

        self.actions = DesktopActions(host=host, port=port, token=token)
        print_success(f"客户端已初始化: http://{host}:{port}")

    async def close(self):
        """关闭客户端"""
        if self.actions:
            await self.actions.close()

    async def test_mouse_left_click(self):
        """测试左键点击"""
        print_header("测试: mouse_left_click(x, y)")
        x = input_int("X 坐标 (0-1000)", 500)
        y = input_int("Y 坐标 (0-1000)", 500)

        result = await self.actions.mouse_left_click(x, y)
        print(f"结果: {result}")

    async def test_mouse_right_click(self):
        """测试右键点击"""
        print_header("测试: mouse_right_click(x, y)")
        x = input_int("X 坐标 (0-1000)", 500)
        y = input_int("Y 坐标 (0-1000)", 500)

        result = await self.actions.mouse_right_click(x, y)
        print(f"结果: {result}")

    async def test_mouse_double_click(self):
        """测试双击"""
        print_header("测试: mouse_double_click(x, y)")
        x = input_int("X 坐标 (0-1000)", 500)
        y = input_int("Y 坐标 (0-1000)", 500)

        result = await self.actions.mouse_double_click(x, y)
        print(f"结果: {result}")

    async def test_mouse_scroll(self):
        """测试滚动"""
        print_header("测试: mouse_scroll(direction, amount, x?, y?)")
        print("方向选项: up, down, left, right")
        direction = input_str("滚动方向", "down")
        amount = input_int("滚动量", 3)
        x = input_optional_int("X 坐标 (0-1000，可选)")
        y = input_optional_int("Y 坐标 (0-1000，可选)")

        result = await self.actions.mouse_scroll(direction, amount, x, y)
        print(f"结果: {result}")

    async def test_mouse_drag(self):
        """测试拖拽"""
        print_header("测试: mouse_drag(x1, y1, x2, y2)")
        print("起点:")
        x1 = input_int("  X1 (0-1000)", 400)
        y1 = input_int("  Y1 (0-1000)", 400)
        print("终点:")
        x2 = input_int("  X2 (0-1000)", 600)
        y2 = input_int("  Y2 (0-1000)", 600)

        result = await self.actions.mouse_drag(x1, y1, x2, y2)
        print(f"结果: {result}")

    async def test_keyboard_hotkey(self):
        """测试快捷键"""
        print_header("测试: keyboard_hotkey(*keys)")
        print("示例: ControlLeft C (复制)")
        print("示例: ControlLeft V (粘贴)")
        print("示例: LeftWin D (显示桌面)")
        keys_str = input_str("按键（空格分隔）", "ControlLeft C")
        keys = keys_str.split()

        result = await self.actions.keyboard_hotkey(*keys)
        print(f"结果: {result}")

    def print_menu(self):
        """打印菜单"""
        print_header("DesktopActions 交互式测试")
        print("请选择要测试的动作:\n")

        print("【鼠标】")
        print("  1. mouse_left_click(x, y)    - 左键点击")
        print("  2. mouse_right_click(x, y)   - 右键点击")
        print("  3. mouse_double_click(x, y)  - 双击")
        print("  4. mouse_scroll(...)          - 滚动（可选坐标）")
        print("  5. mouse_drag(x1,y1,x2,y2)   - 拖拽")

        print("\n【键盘】")
        print("  6. keyboard_hotkey(*keys)    - 快捷键")

        print("\n【其他】")
        print("  q. 退出")

    async def run_test(self, choice: str):
        """执行指定测试"""
        test_map = {
            "1": self.test_mouse_left_click,
            "2": self.test_mouse_right_click,
            "3": self.test_mouse_double_click,
            "4": self.test_mouse_scroll,
            "5": self.test_mouse_drag,
            "6": self.test_keyboard_hotkey,
        }

        if choice in test_map:
            await test_map[choice]()
        else:
            print_error("无效选项")

    async def run(self):
        """运行交互式测试"""
        await self.init_client()

        # 主循环
        while True:
            self.print_menu()
            choice = input("\n输入选项: ").strip().lower()

            if choice == "q":
                print("\n感谢使用，再见！")
                break

            await self.run_test(choice)

            input("\n按回车继续...")

        await self.close()


async def main():
    """主函数"""
    tester = ActionsTester()
    try:
        await tester.run()
    except KeyboardInterrupt:
        print("\n\n程序被中断")
        await tester.close()
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())