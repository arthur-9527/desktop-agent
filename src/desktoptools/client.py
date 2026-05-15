"""DesktopClient - AgentDesk HTTP API 统一门面类

作为远程桌面操作的唯一入口，提供原子操作方法和屏幕信息缓存功能。
"""

from typing import Optional, List, Tuple
from .atomic_ops import DesktopAtomicOps


class DesktopClient:
    """AgentDesk HTTP API 统一客户端

    提供便捷的桌面操作方法，内部封装原子操作并支持屏幕信息缓存。

    Attributes:
        ops: DesktopAtomicOps 实例，提供 18 个 HTTP 原子操作
    """

    def __init__(
        self,
        host: str,
        port: int = 9877,
        token: str = "admin123",
        timeout: float = 10.0,
    ):
        """初始化桌面客户端

        Args:
            host: AgentDesk 服务主机地址
            port: HTTP API 端口
            token: 认证令牌
            timeout: 请求超时时间（秒）
        """
        self.host = host
        self.port = port
        self.token = token
        self.timeout = timeout

        # 创建原子操作实例
        self.ops = DesktopAtomicOps(host=host, port=port, token=token, timeout=timeout)
        
        # 屏幕信息缓存（用于坐标转换）
        self._screen_info: Optional[dict] = None

    # ---- 屏幕信息缓存 ----

    async def _get_screen_info(self) -> dict:
        """获取并缓存屏幕信息"""
        if self._screen_info is None:
            self._screen_info = await self.ops.screen_info()
        return self._screen_info

    def _normalize_to_physical(self, x: int, y: int) -> Tuple[int, int]:
        """将归一化坐标 (0-1000) 转换为物理坐标

        Args:
            x: 归一化 X (0-1000)
            y: 归一化 Y (0-1000)

        Returns:
            (physical_x, physical_y)
        """
        info = self._screen_info or {"width": 1920, "height": 1080, "scaleFactor": 1.0}
        width = info.get("width", 1920)
        height = info.get("height", 1080)
        scale = info.get("scaleFactor", 1.0)

        # 归一化坐标转物理坐标
        phys_x = int(width * scale * (x / 1000))
        phys_y = int(height * scale * (y / 1000))
        return (phys_x, phys_y)

    def _position_match(
        self, actual: dict, expected: Tuple[int, int], tolerance: int = 5
    ) -> bool:
        """检查实际位置是否与期望位置匹配

        Args:
            actual: 实际位置 {"x": int, "y": int}
            expected: 期望位置 (x, y)
            tolerance: 容差像素

        Returns:
            是否在容差范围内
        """
        actual_x = actual.get("x", 0)
        actual_y = actual.get("y", 0)
        expected_x, expected_y = expected

        return (
            abs(actual_x - expected_x) <= tolerance
            and abs(actual_y - expected_y) <= tolerance
        )

    # ---- 截图 ----

    async def screenshot(
        self,
        quality: int = 60,
        max_width: int = 1366,
        max_height: int = 768,
        show_grid: bool = False,
        grid_level: int = 64,
    ) -> dict:
        """截图，返回标准化格式

        Args:
            quality: JPEG 压缩质量 (0-100)
            max_width: 最大宽度
            max_height: 最大高度
            show_grid: 是否叠加网格
            grid_level: 网格层级 (32/64/128)

        Returns:
            {
                "base64": "base64-encoded-jpeg",
                "width": int,
                "height": int,
                "grid_info": {...} or None
            }
        """
        result = await self.ops.screenshot_post(
            quality=quality,
            max_width=max_width,
            max_height=max_height,
            show_grid=show_grid,
            grid_level=grid_level if show_grid else None,
        )

        # 兼容两种返回格式
        if "frameData" in result:
            # showGrid=true 时的格式
            frame_data = result["frameData"]
            grid_info = result.get("gridInfo")
        else:
            # showGrid=false 时的格式
            frame_data = result
            grid_info = None

        return {
            "base64": frame_data.get("data"),
            "width": frame_data.get("width"),
            "height": frame_data.get("height"),
            "grid_info": grid_info,  # None 或 {"horizontalCount": 64, "verticalCount": 64, ...}
        }

    # ---- 屏幕信息 ----

    async def screen_info(self) -> dict:
        """获取屏幕信息

        Returns:
            {"width": 1920, "height": 1080, "scaleFactor": 1.5}
        """
        return await self.ops.screen_info()

    # ---- 鼠标 ----

    async def mouse_move(self, x: int, y: int):
        """移动鼠标，x, y: 0-1000 归一化坐标

        Args:
            x: 归一化 X 坐标 (0-1000)
            y: 归一化 Y 坐标 (0-1000)
        """
        await self.ops.mouse_move(x, y)

    async def mouse_click(
        self,
        button: str = "left",
        x: Optional[int] = None,
        y: Optional[int] = None,
    ):
        """点击鼠标

        Args:
            button: 按钮类型 "left", "right", "double"
            x, y: 可选的 0-1000 归一化坐标
        """
        if button == "left":
            await self.ops.mouse_left_click(x, y)
        elif button == "right":
            await self.ops.mouse_right_click(x, y)
        elif button == "double":
            # double_click 不支持坐标参数
            if x is not None and y is not None:
                await self.ops.mouse_move(x, y)
            await self.ops.mouse_double_click()
        else:
            raise ValueError(f"不支持的按钮类型: {button}")

    async def mouse_down(self):
        """按下鼠标左键（拖拽开始）"""
        await self.ops.mouse_press_left()

    async def mouse_up(self):
        """释放鼠标左键（拖拽结束）"""
        await self.ops.mouse_release_left()

    async def mouse_drag(self, x: int, y: int):
        """拖拽到目标位置（需先 mouse_down）

        Args:
            x: 归一化 X 坐标 (0-1000)
            y: 归一化 Y 坐标 (0-1000)
        """
        await self.ops.mouse_drag(x, y)

    async def mouse_scroll(self, direction: str, amount: int = 1):
        """滚动鼠标

        Args:
            direction: 方向 "up", "down", "left", "right"
            amount: 滚动量
        """
        await self.ops.mouse_scroll(direction, amount)

    # ---- 键盘 ----

    async def keyboard_type(self, text: str):
        """输入文本

        Args:
            text: 要输入的文本
        """
        await self.ops.keyboard_type(text)

    async def keyboard_hotkey(self, *keys: str):
        """发送快捷键（先 press 再 release）

        Args:
            *keys: 按键名称，如 "ControlLeft", "C"
        """
        key_list = list(keys)
        await self.ops.keyboard_press(key_list)
        await self.ops.keyboard_release(key_list)

    async def keyboard_key_down(self, key: str):
        """按下按键

        Args:
            key: 按键名称，如 "ControlLeft"
        """
        await self.ops.keyboard_press([key])

    async def keyboard_key_up(self, key: str):
        """释放按键

        Args:
            key: 按键名称，如 "ControlLeft"
        """
        await self.ops.keyboard_release([key])

    # ---- 无障碍树 ----

    async def accessibility_tree(self, max_depth: int = 10) -> dict:
        """获取无障碍树

        Args:
            max_depth: 最大递归深度，默认 10

        Returns:
            {"tree": {...}}
        """
        return await self.ops.accessibility_tree(max_depth)

    async def accessibility_focused(self) -> dict:
        """获取当前焦点元素

        Returns:
            {"element": {"role": ..., "name": ..., "bounds": {...}}}
        """
        return await self.ops.accessibility_focused()

    async def mouse_position(self) -> dict:
        """获取鼠标位置（物理坐标）

        Returns:
            {"x": int, "y": int}
        """
        return await self.ops.get_mouse_position()

    # ---- 健康检查 ----

    async def health_check(self) -> bool:
        """检查 AgentDesk 服务是否可用

        Returns:
            True 如果服务可用，False 否则
        """
        try:
            result = await self.ops.health_check()
            return result.get("status") == "ok"
        except Exception:
            return False

    # ---- 资源管理 ----

    async def close(self):
        """关闭客户端连接"""
        await self.ops.close()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()