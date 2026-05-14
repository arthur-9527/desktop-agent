"""AgentDesk HTTP API 客户端封装"""

import httpx
from typing import Optional


class AgentDeskClient:
    """AgentDesk HTTP API 客户端"""

    def __init__(self, host: str, port: int = 9877, token: str = "admin123"):
        self.base_url = f"http://{host}:{port}"
        self.auth = {"Authorization": f"Bearer {token}"}
        self._client = httpx.AsyncClient(timeout=10)

    # ---- 截图 ----

    async def screenshot(
        self,
        quality: int = 60,
        max_width: int = 1366,
        max_height: int = 768,
        show_grid: bool = False
    ) -> dict:
        """截图，返回 {"base64": ..., "width": ..., "height": ..., "grid_info": {...}}"""
        resp = await self._client.post(
            f"{self.base_url}/api/screenshot",
            json={
                "quality": quality,
                "maxWidth": max_width,
                "maxHeight": max_height,
                "showGrid": show_grid
            },
            headers=self.auth,
        )
        resp.raise_for_status()
        result = resp.json()
        
        # 兼容两种返回格式
        if "frameData" in result:
            # showGrid=true 时的格式
            frame_data = result["frameData"]
            grid_info = result.get("gridInfo", {})
        else:
            # showGrid=false 时的格式
            frame_data = result
            grid_info = None
        
        return {
            "base64": frame_data["data"],
            "width": frame_data["width"],
            "height": frame_data["height"],
            "grid_info": grid_info  # None 或 {"horizontalCount": 64, "verticalCount": 64, ...}
        }

    # ---- 屏幕信息 ----

    async def screen_info(self) -> dict:
        """获取屏幕信息"""
        resp = await self._client.get(
            f"{self.base_url}/api/screen/info",
            headers=self.auth
        )
        resp.raise_for_status()
        return resp.json()  # {"width": 1920, "height": 1080, "scaleFactor": 1.5}

    # ---- 鼠标 ----

    async def mouse_move(self, x: int, y: int):
        """移动鼠标，x, y: 0-1000 归一化坐标"""
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "move", "x": x, "y": y},
            headers=self.auth,
        )
        resp.raise_for_status()

    async def mouse_click(
        self,
        button: str = "left",
        x: Optional[int] = None,
        y: Optional[int] = None
    ):
        """点击鼠标

        Args:
            button: 按钮类型 "left", "right", "double"
            x, y: 可选的 0-1000 归一化坐标
        """
        action_map = {
            "left": "left_click",
            "right": "right_click",
            "double": "double_click"
        }
        body = {"action": action_map[button]}
        if x is not None and y is not None:
            body["x"], body["y"] = x, y
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json=body,
            headers=self.auth,
        )
        resp.raise_for_status()

    async def mouse_down(self):
        """按下鼠标左键"""
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "press_left"},
            headers=self.auth,
        )
        resp.raise_for_status()

    async def mouse_up(self):
        """释放鼠标左键"""
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "release_left"},
            headers=self.auth,
        )
        resp.raise_for_status()

    async def mouse_drag(self, x: int, y: int):
        """拖拽到目标位置（需先 mouse_down）"""
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "drag", "x": x, "y": y},
            headers=self.auth,
        )
        resp.raise_for_status()

    async def mouse_scroll(self, direction: str, amount: int = 1):
        """滚动鼠标

        Args:
            direction: 方向 "up", "down", "left", "right"
            amount: 滚动量
        """
        resp = await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "scroll", "direction": direction, "amount": amount},
            headers=self.auth,
        )
        resp.raise_for_status()

    # ---- 键盘 ----

    async def keyboard_type(self, text: str):
        """输入文本"""
        resp = await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "type", "text": text},
            headers=self.auth,
        )
        resp.raise_for_status()

    async def keyboard_hotkey(self, *keys: str):
        """发送快捷键，先 press 再 release"""
        resp = await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "press", "keys": list(keys)},
            headers=self.auth,
        )
        resp.raise_for_status()
        resp = await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "release", "keys": list(keys)},
            headers=self.auth,
        )
        resp.raise_for_status()

    async def keyboard_key_down(self, key: str):
        """按下按键"""
        resp = await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "press", "keys": [key]},
            headers=self.auth,
        )
        resp.raise_for_status()

    async def keyboard_key_up(self, key: str):
        """释放按键"""
        resp = await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "release", "keys": [key]},
            headers=self.auth,
        )
        resp.raise_for_status()

    # ---- 无障碍树 ----

    async def accessibility_tree(self, max_depth: int = 10) -> dict:
        """获取无障碍树

        Args:
            max_depth: 最大递归深度，默认 10

        Returns:
            {"tree": {...}}
        """
        resp = await self._client.get(
            f"{self.base_url}/api/accessibility",
            params={"maxDepth": max_depth},
            headers=self.auth,
        )
        resp.raise_for_status()
        return resp.json()

    async def accessibility_focused(self) -> dict:
        """获取当前焦点元素

        Returns:
            {"element": {"role": ..., "name": ..., "bounds": {...}}}
        """
        resp = await self._client.get(
            f"{self.base_url}/api/accessibility/focused",
            headers=self.auth,
        )
        resp.raise_for_status()
        return resp.json()

    async def mouse_position(self) -> dict:
        """获取鼠标位置（物理坐标）

        Returns:
            {"x": int, "y": int}
        """
        resp = await self._client.get(
            f"{self.base_url}/api/mouse/position",
            headers=self.auth,
        )
        resp.raise_for_status()
        return resp.json()

    # ---- 健康检查 ----

    async def health_check(self) -> bool:
        """检查 AgentDesk 服务是否可用"""
        try:
            resp = await self._client.get(f"{self.base_url}/api/health")
            resp.raise_for_status()
            return resp.json().get("status") == "ok"
        except Exception:
            return False

    async def close(self):
        """关闭客户端连接"""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()