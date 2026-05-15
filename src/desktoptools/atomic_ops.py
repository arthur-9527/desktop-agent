"""AgentDesk HTTP API 原子操作封装

每个方法严格对应 1 个 HTTP 调用，不做任何组合封装。
"""


import httpx
from typing import Optional, List, Union


class DesktopAtomicOps:
    """AgentDesk HTTP API 原子操作类

    提供与 HTTP API 1:1 对应的 18 个原子操作。
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9877,
        token: str = "admin123",
        timeout: float = 30.0,
    ):
        """初始化原子操作客户端

        Args:
            host: AgentDesk 服务主机地址
            port: HTTP API 端口
            token: 认证令牌
            timeout: 请求超时时间（秒）
        """
        self.base_url = f"http://{host}:{port}"
        self.headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.AsyncClient(timeout=timeout)

    # =========================================================================
    # 1. 健康检查
    # =========================================================================

    async def health_check(self) -> dict:
        """GET /api/health - 检查服务健康状态

        Returns:
            {"status": "ok", "wsPort": 9876, "httpPort": 9877}
        """
        resp = await self._client.get(f"{self.base_url}/api/health")
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # 2-3. 截图 (2个方法)
    # =========================================================================

    async def screenshot_post(
        self,
        quality: int = 80,
        max_width: int = 1366,
        max_height: int = 768,
        show_grid: bool = False,
        grid_level: Optional[int] = None,
        grid_color: Optional[str] = None,
        grid_alpha: Optional[float] = None,
        sub_grid_alpha: Optional[float] = None,
        grid_line_width: Optional[int] = None,
    ) -> dict:
        """POST /api/screenshot - 截图并返回 base64 JSON

        Args:
            quality: JPEG 压缩质量 (0-100)
            max_width: 最大宽度
            max_height: 最大高度
            show_grid: 是否叠加网格
            grid_level: 网格层级 (32/64/128)
            grid_color: 网格颜色 RGB 格式，如 "255,0,0"
            grid_alpha: 大格子透明度 (0-1)
            sub_grid_alpha: 小格子透明度 (0-1)
            grid_line_width: 网格线宽（像素）

        Returns:
            {
                "data": "base64-jpeg-data...",
                "width": 1024,
                "height": 768,
                "timestamp": 1234567890
            }
            或 show_grid=true 时:
            {
                "frameData": {...},
                "gridInfo": {...}
            }
        """
        body = {
            "quality": quality,
            "maxWidth": max_width,
            "maxHeight": max_height,
            "showGrid": show_grid,
        }
        if grid_level is not None:
            body["gridLevel"] = grid_level
        if grid_color is not None:
            body["gridColor"] = grid_color
        if grid_alpha is not None:
            body["gridAlpha"] = grid_alpha
        if sub_grid_alpha is not None:
            body["subGridAlpha"] = sub_grid_alpha
        if grid_line_width is not None:
            body["gridLineWidth"] = grid_line_width

        resp = await self._client.post(
            f"{self.base_url}/api/screenshot",
            json=body,
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def screenshot_get(
        self,
        quality: int = 80,
        max_width: int = 1366,
        max_height: int = 768,
        show_grid: bool = False,
        grid_level: Optional[int] = None,
        grid_color: Optional[str] = None,
        grid_alpha: Optional[float] = None,
        sub_grid_alpha: Optional[float] = None,
        grid_line_width: Optional[int] = None,
    ) -> bytes:
        """GET /api/screenshot - 截图并直接返回 JPEG 二进制数据

        Args:
            quality: JPEG 压缩质量 (0-100)
            max_width: 最大宽度
            max_height: 最大高度
            show_grid: 是否叠加网格
            grid_level: 网格层级 (32/64/128)
            grid_color: 网格颜色 RGB 格式，如 "255,0,0"
            grid_alpha: 大格子透明度 (0-1)
            sub_grid_alpha: 小格子透明度 (0-1)
            grid_line_width: 网格线宽（像素）

        Returns:
            JPEG 图片二进制数据
        """
        params = {
            "quality": quality,
            "maxWidth": max_width,
            "maxHeight": max_height,
            "showGrid": show_grid,
        }
        if grid_level is not None:
            params["gridLevel"] = grid_level
        if grid_color is not None:
            params["gridColor"] = grid_color
        if grid_alpha is not None:
            params["gridAlpha"] = grid_alpha
        if sub_grid_alpha is not None:
            params["subGridAlpha"] = sub_grid_alpha
        if grid_line_width is not None:
            params["gridLineWidth"] = grid_line_width

        resp = await self._client.get(
            f"{self.base_url}/api/screenshot",
            params=params,
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.content

    # =========================================================================
    # 4. 屏幕信息
    # =========================================================================

    async def screen_info(self) -> dict:
        """GET /api/screen/info - 获取屏幕信息

        Returns:
            {"width": 1920, "height": 1080, "scaleFactor": 1.5}
        """
        resp = await self._client.get(
            f"{self.base_url}/api/screen/info",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # 5-12. 鼠标操作 (8个方法)
    # =========================================================================

    async def mouse_move(self, x: int, y: int) -> None:
        """POST /api/mouse - 移动鼠标到指定位置

        Args:
            x: 归一化 X 坐标 (0-1000)
            y: 归一化 Y 坐标 (0-1000)
        """
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "move", "x": x, "y": y},
            headers=self.headers,
        )
        resp.raise_for_status()

    async def mouse_left_click(
        self, x: Optional[int] = None, y: Optional[int] = None
    ) -> None:
        """POST /api/mouse - 左键点击

        Args:
            x: 可选的归一化 X 坐标 (0-1000)
            y: 可选的归一化 Y 坐标 (0-1000)
        """
        body: dict = {"action": "left_click"}
        if x is not None and y is not None:
            body["x"] = x
            body["y"] = y
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json=body,
            headers=self.headers,
        )
        resp.raise_for_status()

    async def mouse_right_click(
        self, x: Optional[int] = None, y: Optional[int] = None
    ) -> None:
        """POST /api/mouse - 右键点击

        Args:
            x: 可选的归一化 X 坐标 (0-1000)
            y: 可选的归一化 Y 坐标 (0-1000)
        """
        body: dict = {"action": "right_click"}
        if x is not None and y is not None:
            body["x"] = x
            body["y"] = y
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json=body,
            headers=self.headers,
        )
        resp.raise_for_status()

    async def mouse_double_click(self) -> None:
        """POST /api/mouse - 双击"""
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "double_click"},
            headers=self.headers,
        )
        resp.raise_for_status()

    async def mouse_scroll(self, direction: str, amount: int = 1) -> None:
        """POST /api/mouse - 滚轮滚动

        Args:
            direction: 滚动方向 ("up", "down", "left", "right")
            amount: 滚动量
        """
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "scroll", "direction": direction, "amount": amount},
            headers=self.headers,
        )
        resp.raise_for_status()

    async def mouse_press_left(self) -> None:
        """POST /api/mouse - 按下左键（拖拽开始）"""
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "press_left"},
            headers=self.headers,
        )
        resp.raise_for_status()

    async def mouse_drag(self, x: int, y: int) -> None:
        """POST /api/mouse - 拖拽到目标位置

        Args:
            x: 归一化 X 坐标 (0-1000)
            y: 归一化 Y 坐标 (0-1000)

        Note:
            需先调用 mouse_press_left() 按下左键
        """
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "drag", "x": x, "y": y},
            headers=self.headers,
        )
        resp.raise_for_status()

    async def mouse_release_left(self) -> None:
        """POST /api/mouse - 释放左键（拖拽结束）"""
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "release_left"},
            headers=self.headers,
        )
        resp.raise_for_status()

    # =========================================================================
    # 13. 鼠标位置查询
    # =========================================================================

    async def get_mouse_position(self) -> dict:
        """GET /api/mouse/position - 获取鼠标当前位置

        Returns:
            {"x": 1234, "y": 567}
        """
        resp = await self._client.get(
            f"{self.base_url}/api/mouse/position",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # 14-16. 键盘操作 (3个方法)
    # =========================================================================

    async def keyboard_type(self, text: str) -> None:
        """POST /api/keyboard - 输入文本

        Args:
            text: 要输入的文本
        """
        resp = await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "type", "text": text},
            headers=self.headers,
        )
        resp.raise_for_status()

    async def keyboard_press(self, keys: Union[str, List[str]]) -> None:
        """POST /api/keyboard - 按键按下

        Args:
            keys: 按键名称或按键列表，如 "ControlLeft" 或 ["ControlLeft", "C"]
        """
        if isinstance(keys, str):
            keys = [keys]
        resp = await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "press", "keys": keys},
            headers=self.headers,
        )
        resp.raise_for_status()

    async def keyboard_release(self, keys: Union[str, List[str]]) -> None:
        """POST /api/keyboard - 按键释放

        Args:
            keys: 按键名称或按键列表，如 "ControlLeft" 或 ["ControlLeft", "C"]
        """
        if isinstance(keys, str):
            keys = [keys]
        resp = await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "release", "keys": keys},
            headers=self.headers,
        )
        resp.raise_for_status()

    # =========================================================================
    # 17-18. 无障碍树 (2个方法)
    # =========================================================================

    async def accessibility_tree(self, max_depth: int = 3) -> dict:
        """GET /api/accessibility - 获取完整无障碍元素树

        Args:
            max_depth: 最大递归深度 (1-20)

        Returns:
            {
                "tree": {
                    "role": "Pane",
                    "name": "桌面 1",
                    "bounds": {"x": 0, "y": 0, "width": 2560, "height": 1440},
                    "children": [...]
                }
            }
        """
        resp = await self._client.get(
            f"{self.base_url}/api/accessibility",
            params={"maxDepth": max_depth},
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def accessibility_focused(self) -> dict:
        """GET /api/accessibility/focused - 获取当前焦点元素

        Returns:
            {
                "element": {
                    "role": "Edit",
                    "name": "Message input",
                    "bounds": {"x": 1735, "y": 1236, "width": 804, "height": 50}
                }
            }
        """
        resp = await self._client.get(
            f"{self.base_url}/api/accessibility/focused",
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # 资源管理
    # =========================================================================

    async def close(self) -> None:
        """关闭 HTTP 客户端连接"""
        await self._client.aclose()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()