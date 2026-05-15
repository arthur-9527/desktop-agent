"""DesktopActions - 鼠标和键盘动作封装

将原子操作组合成高层动作，每次移动鼠标后验证位置。
成功返回 "执行成功"，失败返回 "执行失败: {原因}"
"""


from typing import Optional, List, Union

try:
    from .atomic_ops import DesktopAtomicOps  # 包导入
except ImportError:
    from atomic_ops import DesktopAtomicOps  # 直接运行


class DesktopActions:
    """桌面动作封装类

    提供 6 个高层动作：
    - 鼠标: left_click, right_click, double_click, scroll, drag
    - 键盘: hotkey

    所有涉及鼠标移动的操作都会验证位置。
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9877,
        token: str = "admin123",
        timeout: float = 30.0,
    ):
        """初始化动作封装

        Args:
            host: AgentDesk 服务主机
            port: HTTP 端口
            token: 认证令牌
            timeout: 请求超时
        """
        self.ops = DesktopAtomicOps(host=host, port=port, token=token, timeout=timeout)
        self._screen_info: Optional[dict] = None

    async def _get_screen_info(self) -> dict:
        """获取并缓存屏幕信息"""
        if self._screen_info is None:
            self._screen_info = await self.ops.screen_info()
        return self._screen_info

    def _normalize_to_physical(self, x: int, y: int) -> tuple:
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

    def _position_match(self, actual: dict, expected: tuple, tolerance: int = 5) -> bool:
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

    async def _move_and_verify(self, x: int, y: int) -> str:
        """移动鼠标并验证位置

        Args:
            x: 归一化 X 坐标 (0-1000)
            y: 归一化 Y 坐标 (0-1000)

        Returns:
            "执行成功" 或抛出异常
        """
        # 先获取屏幕信息用于坐标转换
        await self._get_screen_info()

        # 移动鼠标
        await self.ops.mouse_move(x, y)

        # 读取实际位置
        actual_pos = await self.ops.get_mouse_position()

        # 计算期望的物理坐标
        expected_pos = self._normalize_to_physical(x, y)

        # 验证位置
        if not self._position_match(actual_pos, expected_pos):
            raise RuntimeError(
                f"鼠标位置验证失败: 期望({expected_pos[0]}, {expected_pos[1]}), "
                f"实际({actual_pos['x']}, {actual_pos['y']})"
            )

        return "执行成功"

    # ========================================================================
    # 鼠标动作
    # ========================================================================

    async def mouse_left_click(self, x: int, y: int) -> str:
        """左键点击

        Args:
            x: 归一化 X 坐标 (0-1000)
            y: 归一化 Y 坐标 (0-1000)

        Returns:
            "执行成功" 或 "执行失败: {原因}"
        """
        try:
            await self._move_and_verify(x, y)
            await self.ops.mouse_left_click()
            return "执行成功"
        except Exception as e:
            return f"执行失败: {e}"

    async def mouse_right_click(self, x: int, y: int) -> str:
        """右键点击

        Args:
            x: 归一化 X 坐标 (0-1000)
            y: 归一化 Y 坐标 (0-1000)

        Returns:
            "执行成功" 或 "执行失败: {原因}"
        """
        try:
            await self._move_and_verify(x, y)
            await self.ops.mouse_right_click()
            return "执行成功"
        except Exception as e:
            return f"执行失败: {e}"

    async def mouse_double_click(self, x: int, y: int) -> str:
        """双击

        Args:
            x: 归一化 X 坐标 (0-1000)
            y: 归一化 Y 坐标 (0-1000)

        Returns:
            "执行成功" 或 "执行失败: {原因}"
        """
        try:
            await self._move_and_verify(x, y)
            await self.ops.mouse_double_click()
            return "执行成功"
        except Exception as e:
            return f"执行失败: {e}"

    async def mouse_scroll(
        self,
        direction: str,
        amount: int = 1,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> str:
        """滚轮滚动

        Args:
            direction: 方向 "up", "down", "left", "right"
            amount: 滚动量
            x: 可选的归一化 X 坐标 (0-1000)
            y: 可选的归一化 Y 坐标 (0-1000)

        Returns:
            "执行成功" 或 "执行失败: {原因}"
        """
        try:
            if x is not None and y is not None:
                await self._move_and_verify(x, y)
            await self.ops.mouse_scroll(direction, amount)
            return "执行成功"
        except Exception as e:
            return f"执行失败: {e}"

    async def mouse_drag(self, x1: int, y1: int, x2: int, y2: int) -> str:
        """拖拽

        Args:
            x1: 起点归一化 X 坐标 (0-1000)
            y1: 起点归一化 Y 坐标 (0-1000)
            x2: 终点归一化 X 坐标 (0-1000)
            y2: 终点归一化 Y 坐标 (0-1000)

        Returns:
            "执行成功" 或 "执行失败: {原因}"
        """
        try:
            # 1. 移动到起点并验证
            await self._move_and_verify(x1, y1)

            # 2. 按下左键
            await self.ops.mouse_press_left()

            # 3. 拖拽到终点（使用 drag 原子操作）
            await self.ops.mouse_drag(x2, y2)

            # 4. 验证终点位置
            await self._get_screen_info()
            actual_pos = await self.ops.get_mouse_position()
            expected_pos = self._normalize_to_physical(x2, y2)

            if not self._position_match(actual_pos, expected_pos):
                raise RuntimeError(
                    f"拖拽终点验证失败: 期望({expected_pos[0]}, {expected_pos[1]}), "
                    f"实际({actual_pos['x']}, {actual_pos['y']})"
                )

            # 5. 释放左键
            await self.ops.mouse_release_left()

            return "执行成功"
        except Exception as e:
            return f"执行失败: {e}"

    # ========================================================================
    # 键盘动作
    # ========================================================================

    async def keyboard_hotkey(self, *keys: str) -> str:
        """快捷键

        Args:
            *keys: 按键名称，如 "ControlLeft", "C"

        Returns:
            "执行成功" 或 "执行失败: {原因}"
        """
        try:
            key_list = list(keys)
            await self.ops.keyboard_press(key_list)
            await self.ops.keyboard_release(key_list)
            return "执行成功"
        except Exception as e:
            return f"执行失败: {e}"

    # ========================================================================
    # 资源管理
    # ========================================================================

    async def close(self):
        """关闭连接"""
        await self.ops.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()