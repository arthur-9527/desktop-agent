#!/usr/bin/env python3
"""DesktopAtomicOps 交互式测试脚本

提供菜单式交互界面，逐个测试 18 个原子操作。
"""


import asyncio
import sys
from typing import Optional

try:
    from .atomic_ops import DesktopAtomicOps  # 包导入
except ImportError:
    from atomic_ops import DesktopAtomicOps  # 直接运行


# 测试配置
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


def print_info(msg: str):
    """打印信息消息"""
    print(f"ℹ️  {msg}")


def input_int(prompt: str, default: Optional[int] = None) -> int:
    """输入整数"""
    while True:
        try:
            value = input(f"{prompt} [{default}]: ").strip()
            if not value and default is not None:
                return default
            return int(value)
        except ValueError:
            print("请输入有效的整数")


def input_str(prompt: str, default: Optional[str] = None) -> str:
    """输入字符串"""
    value = input(f"{prompt} [{default}]: ").strip()
    if not value and default is not None:
        return default
    return value


def input_bool(prompt: str, default: bool = False) -> bool:
    """输入布尔值"""
    default_str = "y" if default else "n"
    value = input(f"{prompt} (y/n) [{default_str}]: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "true", "1")


def input_optional_int(prompt: str) -> Optional[int]:
    """输入可选整数（空输入返回 None）"""
    value = input(f"{prompt} [可选，直接回车跳过]: ").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        print_error("输入无效，视为跳过")
        return None


def input_optional_str(prompt: str) -> Optional[str]:
    """输入可选字符串（空输入返回 None）"""
    value = input(f"{prompt} [可选，直接回车跳过]: ").strip()
    return value if value else None


class AtomicOpsTester:
    """原子操作测试器"""

    def __init__(self):
        self.ops: Optional[DesktopAtomicOps] = None

    async def init_client(self):
        """初始化客户端"""
        print_header("配置 AgentDesk 连接")
        host = input_str("主机地址", DEFAULT_HOST)
        port = input_int("HTTP 端口", DEFAULT_PORT)
        token = input_str("认证令牌", DEFAULT_TOKEN)

        self.ops = DesktopAtomicOps(host=host, port=port, token=token)
        print_success(f"客户端已初始化: http://{host}:{port}")

    async def close(self):
        """关闭客户端"""
        if self.ops:
            await self.ops.close()

    # ========================================================================
    # 1. 健康检查
    # ========================================================================
    async def test_health_check(self):
        """测试健康检查"""
        print_header("测试: health_check()")
        print("GET /api/health")

        try:
            result = await self.ops.health_check()
            print_success("请求成功")
            print(f"响应: {result}")
        except Exception as e:
            print_error(f"请求失败: {e}")

    # ========================================================================
    # 2-3. 截图
    # ========================================================================
    async def test_screenshot_post(self):
        """测试 POST 截图"""
        print_header("测试: screenshot_post()")
        print("POST /api/screenshot")

        quality = input_int("JPEG 质量 (0-100)", 80)
        max_width = input_int("最大宽度", 1366)
        max_height = input_int("最大高度", 768)
        show_grid = input_bool("显示网格", False)

        grid_level = None
        if show_grid:
            grid_level = input_optional_int("网格层级 (32/64/128)")

        try:
            result = await self.ops.screenshot_post(
                quality=quality,
                max_width=max_width,
                max_height=max_height,
                show_grid=show_grid,
                grid_level=grid_level,
            )
            print_success("请求成功")
            if "data" in result:
                print(f"截图尺寸: {result.get('width')}x{result.get('height')}")
                print(f"数据长度: {len(result.get('data', ''))} 字符 (base64)")
            elif "frameData" in result:
                frame = result["frameData"]
                print(f"截图尺寸: {frame.get('width')}x{frame.get('height')}")
                print(f"网格信息: {result.get('gridInfo')}")
            else:
                print(f"响应: {result}")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_screenshot_get(self):
        """测试 GET 截图"""
        print_header("测试: screenshot_get()")
        print("GET /api/screenshot")

        quality = input_int("JPEG 质量 (0-100)", 80)
        max_width = input_int("最大宽度", 1366)
        max_height = input_int("最大高度", 768)
        show_grid = input_bool("显示网格", False)

        grid_level = None
        if show_grid:
            grid_level = input_optional_int("网格层级 (32/64/128)")

        save_path = input_str("保存路径", "screenshot_test.jpg")

        try:
            data = await self.ops.screenshot_get(
                quality=quality,
                max_width=max_width,
                max_height=max_height,
                show_grid=show_grid,
                grid_level=grid_level,
            )
            print_success(f"请求成功，收到 {len(data)} 字节")

            # 保存文件
            with open(save_path, "wb") as f:
                f.write(data)
            print_success(f"已保存到: {save_path}")

        except Exception as e:
            print_error(f"请求失败: {e}")

    # ========================================================================
    # 4. 屏幕信息
    # ========================================================================
    async def test_screen_info(self):
        """测试屏幕信息"""
        print_header("测试: screen_info()")
        print("GET /api/screen/info")

        try:
            result = await self.ops.screen_info()
            print_success("请求成功")
            print(f"屏幕宽度: {result.get('width')}")
            print(f"屏幕高度: {result.get('height')}")
            print(f"缩放因子: {result.get('scaleFactor')}")
        except Exception as e:
            print_error(f"请求失败: {e}")

    # ========================================================================
    # 5-12. 鼠标操作
    # ========================================================================
    async def test_mouse_move(self):
        """测试鼠标移动"""
        print_header("测试: mouse_move(x, y)")
        print("POST /api/mouse {action: 'move'}")

        x = input_int("X 坐标 (0-1000)", 500)
        y = input_int("Y 坐标 (0-1000)", 500)

        try:
            await self.ops.mouse_move(x, y)
            print_success("鼠标移动成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_mouse_left_click(self):
        """测试左键点击"""
        print_header("测试: mouse_left_click(x?, y?)")
        print("POST /api/mouse {action: 'left_click'}")

        use_coords = input_bool("指定坐标", True)
        x, y = None, None
        if use_coords:
            x = input_int("X 坐标 (0-1000)", 500)
            y = input_int("Y 坐标 (0-1000)", 500)

        try:
            await self.ops.mouse_left_click(x, y)
            print_success("左键点击成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_mouse_right_click(self):
        """测试右键点击"""
        print_header("测试: mouse_right_click(x?, y?)")
        print("POST /api/mouse {action: 'right_click'}")

        use_coords = input_bool("指定坐标", True)
        x, y = None, None
        if use_coords:
            x = input_int("X 坐标 (0-1000)", 500)
            y = input_int("Y 坐标 (0-1000)", 500)

        try:
            await self.ops.mouse_right_click(x, y)
            print_success("右键点击成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_mouse_double_click(self):
        """测试双击"""
        print_header("测试: mouse_double_click()")
        print("POST /api/mouse {action: 'double_click'}")

        try:
            await self.ops.mouse_double_click()
            print_success("双击成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_mouse_scroll(self):
        """测试滚轮滚动"""
        print_header("测试: mouse_scroll(direction, amount)")
        print("POST /api/mouse {action: 'scroll'}")

        print("方向选项: up, down, left, right")
        direction = input_str("滚动方向", "down")
        amount = input_int("滚动量", 3)

        try:
            await self.ops.mouse_scroll(direction, amount)
            print_success("滚动成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_mouse_press_left(self):
        """测试按下左键"""
        print_header("测试: mouse_press_left()")
        print("POST /api/mouse {action: 'press_left'}")

        try:
            await self.ops.mouse_press_left()
            print_success("左键按下成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_mouse_drag(self):
        """测试拖拽"""
        print_header("测试: mouse_drag(x, y)")
        print("POST /api/mouse {action: 'drag'}")

        print_info("提示: 拖拽前需要先调用 mouse_press_left()")
        x = input_int("目标 X 坐标 (0-1000)", 600)
        y = input_int("目标 Y 坐标 (0-1000)", 600)

        try:
            await self.ops.mouse_drag(x, y)
            print_success("拖拽成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_mouse_release_left(self):
        """测试释放左键"""
        print_header("测试: mouse_release_left()")
        print("POST /api/mouse {action: 'release_left'}")

        try:
            await self.ops.mouse_release_left()
            print_success("左键释放成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    # ========================================================================
    # 13. 鼠标位置查询
    # ========================================================================
    async def test_get_mouse_position(self):
        """测试获取鼠标位置"""
        print_header("测试: get_mouse_position()")
        print("GET /api/mouse/position")

        try:
            result = await self.ops.get_mouse_position()
            print_success("请求成功")
            print(f"鼠标位置: X={result.get('x')}, Y={result.get('y')}")
        except Exception as e:
            print_error(f"请求失败: {e}")

    # ========================================================================
    # 14-16. 键盘操作
    # ========================================================================
    async def test_keyboard_type(self):
        """测试输入文本"""
        print_header("测试: keyboard_type(text)")
        print("POST /api/keyboard {action: 'type'}")

        text = input_str("输入文本", "Hello World")

        try:
            await self.ops.keyboard_type(text)
            print_success("文本输入成功")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_keyboard_press(self):
        """测试按键按下"""
        print_header("测试: keyboard_press(keys)")
        print("POST /api/keyboard {action: 'press'}")

        keys_str = input_str("按键（逗号分隔多个）", "ControlLeft,C")
        keys = [k.strip() for k in keys_str.split(",")]

        try:
            await self.ops.keyboard_press(keys)
            print_success(f"按键按下成功: {keys}")
        except Exception as e:
            print_error(f"请求失败: {e}")

    async def test_keyboard_release(self):
        """测试按键释放"""
        print_header("测试: keyboard_release(keys)")
        print("POST /api/keyboard {action: 'release'}")

        keys_str = input_str("按键（逗号分隔多个）", "ControlLeft,C")
        keys = [k.strip() for k in keys_str.split(",")]

        try:
            await self.ops.keyboard_release(keys)
            print_success(f"按键释放成功: {keys}")
        except Exception as e:
            print_error(f"请求失败: {e}")

    # ========================================================================
    # 17-18. 无障碍树
    # ========================================================================
    async def test_accessibility_tree(self):
        """测试获取无障碍树"""
        print_header("测试: accessibility_tree(max_depth)")
        print("GET /api/accessibility")

        max_depth = input_int("最大深度 (1-20)", 3)

        try:
            result = await self.ops.accessibility_tree(max_depth)
            print_success("请求成功")

            tree = result.get("tree", {})
            self._print_tree_node(tree, 0)

        except Exception as e:
            print_error(f"请求失败: {e}")

    def _print_tree_node(self, node: dict, indent: int):
        """递归打印树节点"""
        prefix = "  " * indent
        role = node.get("role", "Unknown")
        name = node.get("name", "")
        bounds = node.get("bounds", {})

        info = f"{role}"
        if name:
            info += f' "{name}"'
        if bounds:
            info += f" [{bounds.get('x')},{bounds.get('y')} {bounds.get('width')}x{bounds.get('height')}]"

        print(f"{prefix}{info}")

        for child in node.get("children", []):
            self._print_tree_node(child, indent + 1)

    async def test_accessibility_focused(self):
        """测试获取焦点元素"""
        print_header("测试: accessibility_focused()")
        print("GET /api/accessibility/focused")

        try:
            result = await self.ops.accessibility_focused()
            print_success("请求成功")

            element = result.get("element", {})
            print(f"Role: {element.get('role')}")
            print(f"Name: {element.get('name')}")
            print(f"Bounds: {element.get('bounds')}")

        except Exception as e:
            print_error(f"请求失败: {e}")

    # ========================================================================
    # 主菜单
    # ========================================================================
    def print_menu(self):
        """打印菜单"""
        print_header("DesktopAtomicOps 交互式测试")
        print("请选择要测试的操作:\n")

        print("【系统】")
        print("  1. health_check()          - GET /api/health")
        print("  4. screen_info()           - GET /api/screen/info")

        print("\n【截图】")
        print("  2. screenshot_post()       - POST /api/screenshot")
        print("  3. screenshot_get()        - GET /api/screenshot")

        print("\n【鼠标】")
        print("  5. mouse_move(x, y)        - 移动鼠标")
        print("  6. mouse_left_click()      - 左键点击")
        print("  7. mouse_right_click()     - 右键点击")
        print("  8. mouse_double_click()    - 双击")
        print("  9. mouse_scroll()          - 滚轮滚动")
        print(" 10. mouse_press_left()      - 按下左键")
        print(" 11. mouse_drag(x, y)        - 拖拽")
        print(" 12. mouse_release_left()    - 释放左键")
        print(" 13. get_mouse_position()    - 获取鼠标位置")

        print("\n【键盘】")
        print(" 14. keyboard_type(text)     - 输入文本")
        print(" 15. keyboard_press(keys)    - 按键按下")
        print(" 16. keyboard_release(keys)  - 按键释放")

        print("\n【无障碍】")
        print(" 17. accessibility_tree()    - 获取元素树")
        print(" 18. accessibility_focused() - 获取焦点元素")

        print("\n【其他】")
        print("  a. 一键测试所有接口")
        print("  q. 退出")

    async def run_test(self, choice: str):
        """执行指定测试"""
        test_map = {
            "1": self.test_health_check,
            "2": self.test_screenshot_post,
            "3": self.test_screenshot_get,
            "4": self.test_screen_info,
            "5": self.test_mouse_move,
            "6": self.test_mouse_left_click,
            "7": self.test_mouse_right_click,
            "8": self.test_mouse_double_click,
            "9": self.test_mouse_scroll,
            "10": self.test_mouse_press_left,
            "11": self.test_mouse_drag,
            "12": self.test_mouse_release_left,
            "13": self.test_get_mouse_position,
            "14": self.test_keyboard_type,
            "15": self.test_keyboard_press,
            "16": self.test_keyboard_release,
            "17": self.test_accessibility_tree,
            "18": self.test_accessibility_focused,
        }

        if choice in test_map:
            await test_map[choice]()
        elif choice == "a":
            await self.run_all_tests()
        else:
            print_error("无效选项")

    async def run_all_tests(self):
        """一键测试所有接口"""
        print_header("一键测试所有接口")

        tests = [
            ("健康检查", self.test_health_check),
            ("屏幕信息", self.test_screen_info),
            ("截图 POST", self.test_screenshot_post),
            ("截图 GET", self.test_screenshot_get),
            ("鼠标位置", self.test_get_mouse_position),
            ("无障碍树", self.test_accessibility_tree),
            ("焦点元素", self.test_accessibility_focused),
        ]

        # 注意：鼠标和键盘操作会实际影响桌面，不包含在自动测试中
        print_info("注意: 鼠标和键盘操作需要手动测试，未包含在自动测试中")

        for name, test_func in tests:
            print(f"\n>>> 测试: {name}")
            try:
                await test_func()
            except Exception as e:
                print_error(f"{name} 测试失败: {e}")

    async def run(self):
        """运行交互式测试"""
        await self.init_client()

        # 先测试连接
        print("\n>>> 正在测试连接...")
        try:
            await self.test_health_check()
        except Exception as e:
            print_error(f"无法连接到 AgentDesk: {e}")
            await self.close()
            return

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
    tester = AtomicOpsTester()
    try:
        await tester.run()
    except KeyboardInterrupt:
        print("\n\n程序被中断")
        await tester.close()
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())