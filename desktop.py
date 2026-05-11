"""
AgentDesk HTTP API 客户端封装
用于远程控制远程桌面
"""
import base64
import io
import logging
from io import BytesIO
from typing import Optional
import requests
from PIL import Image

from config import (
    AGENTDESK_HOST,
    AGENTDESK_PORT,
    AGENTDESK_TOKEN,
    SCREENSHOT_QUALITY,
    SCREENSHOT_MAX_WIDTH,
    SCREENSHOT_MAX_HEIGHT,
)

logger = logging.getLogger(__name__)


class DesktopController:
    """AgentDesk 远程控制客户端"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        token: str = None,
    ):
        self.host = host or AGENTDESK_HOST
        self.port = port or AGENTDESK_PORT
        self.token = token or AGENTDESK_TOKEN
        self.base_url = f"http://{self.host}:{self.port}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
        }
        self._screen_info = None
        # 远程机器真实分辨率（从无障碍树提取，优先级高于 API）
        self._remote_screen_info = None

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault("headers", {}).update(self.headers)
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url}, error: {e}")
            raise

    def _make_post_request(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """发送 POST 请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"POST request failed: {url}, error: {e}")
            raise

    def _make_get_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """发送 GET 请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GET request failed: {url}, error: {e}")
            raise

    # ============ 截图相关 ============

    def screenshot(
        self,
        quality: int = None,
        max_width: int = None,
        max_height: int = None,
    ) -> dict:
        """
        获取远程桌面截图
        返回: {
            "data": "base64-jpeg-data",
            "width": int,
            "height": int,
            "timestamp": int
        }
        """
        data = {
            "quality": quality or SCREENSHOT_QUALITY,
            "maxWidth": max_width or SCREENSHOT_MAX_WIDTH,
            "maxHeight": max_height or SCREENSHOT_MAX_HEIGHT,
        }
        result = self._make_post_request("/api/screenshot", data=data)
        return result

    def screenshot_to_image(
        self,
        quality: int = None,
        max_width: int = None,
        max_height: int = None,
    ) -> Image.Image:
        """
        获取远程桌面截图，返回 PIL.Image 对象
        """
        result = self.screenshot(quality, max_width, max_height)
        if "data" not in result:
            raise ValueError("Screenshot data is missing")
        img_data = base64.b64decode(result["data"])
        return Image.open(BytesIO(img_data))

    # ============ 屏幕信息 ============

    def get_screen_info(self) -> dict:
        """
        获取屏幕信息
        返回: {"width": int, "height": int, "scaleFactor": float}
        """
        if self._screen_info is not None:
            return self._screen_info
        result = self._make_get_request("/api/screen/info")
        self._screen_info = result
        return result

    # ============ 鼠标操作 ============

    def mouse_move(self, x: int, y: int):
        """
        移动鼠标到指定位置 (归一化坐标 0-1000)
        """
        self._make_post_request("/api/mouse", data={"action": "move", "x": x, "y": y})

    def mouse_left_click(self, x: int = None, y: int = None):
        """左键点击"""
        data = {"action": "left_click"}
        if x is not None and y is not None:
            data["x"] = x
            data["y"] = y
        self._make_post_request("/api/mouse", data=data)

    def mouse_right_click(self, x: int = None, y: int = None):
        """右键点击"""
        data = {"action": "right_click"}
        if x is not None and y is not None:
            data["x"] = x
            data["y"] = y
        self._make_post_request("/api/mouse", data=data)

    def mouse_double_click(self, x: int = None, y: int = None):
        """双击"""
        data = {"action": "double_click"}
        if x is not None and y is not None:
            data["x"] = x
            data["y"] = y
        self._make_post_request("/api/mouse", data=data)

    def mouse_scroll(self, direction: str = "up", amount: int = 1):
        """滚动 (归一化坐标)"""
        self._make_post_request(
            "/api/mouse",
            data={"action": "scroll", "direction": direction, "amount": amount},
        )

    def get_mouse_position(self) -> dict:
        """获取鼠标位置"""
        return self._make_get_request("/api/mouse/position")

    # ============ 键盘操作 ============

    def keyboard_type(self, text: str):
        """输入文本"""
        self._make_post_request(
            "/api/keyboard", data={"action": "type", "text": text}
        )

    def keyboard_hotkey(self, keys: list):
        """
        执行快捷键 - 支持组合键和单键
        按文档方式实现：先 press 所有键，短暂延迟，再 release 所有键
        keys: ["LeftWin", "D"] 表示 Win+D
        key: "Enter" 表示按 Enter 键
        """
        if not keys:
            raise ValueError("keys 不能为空")

        # 按下所有键
        self._make_post_request(
            "/api/keyboard", data={"action": "press", "keys": keys}
        )

        # 短暂延迟（50ms）
        import time
        time.sleep(0.05)

        # 释放所有键
        self._make_post_request(
            "/api/keyboard", data={"action": "release", "keys": keys}
        )

    def keyboard_press(self, key: str):
        """按键按下"""
        self._make_post_request(
            "/api/keyboard", data={"action": "press", "keys": [key]}
        )

    def keyboard_release(self, key: str):
        """按键释放"""
        self._make_post_request(
            "/api/keyboard", data={"action": "release", "keys": [key]}
        )

    # ============ Accessibility ============

    def get_accessibility_tree(self, max_depth: int = 3) -> dict:
        """
        获取无障碍元素树
        返回: {"tree": AccessibilityNode}
        """
        return self._make_get_request(
            "/api/accessibility", params={"maxDepth": max_depth}
        )

    def get_focused_element(self) -> dict:
        """获取当前焦点元素"""
        return self._make_get_request("/api/accessibility/focused")

    # ============ 坐标转换 ============

    def physical_to_normalized(self, phys_x: int, phys_y: int) -> tuple:
        """
        将物理坐标转换为归一化坐标 (0-1000)
        优先使用远程机器真实分辨率
        """
        # 优先使用远程机器分辨率（从无障碍树提取）
        if self._remote_screen_info:
            width = self._remote_screen_info["width"]
            height = self._remote_screen_info["height"]
        else:
            screen = self.get_screen_info()
            width = screen["width"]
            height = screen["height"]
            logger.warning(
                f"未设置远程屏幕信息，使用 API 返回值 {width}x{height}，"
                "坐标转换可能不准确"
            )

        normalized_x = int(phys_x / width * 1000)
        normalized_y = int(phys_y / height * 1000)
        return min(normalized_x, 1000), min(normalized_y, 1000)

    def normalized_to_physical(self, norm_x: int, norm_y: int) -> tuple:
        """
        将归一化坐标 (0-1000) 转换为物理坐标
        优先使用远程机器真实分辨率
        """
        # 优先使用远程机器分辨率（从无障碍树提取）
        if self._remote_screen_info:
            width = self._remote_screen_info["width"]
            height = self._remote_screen_info["height"]
        else:
            screen = self.get_screen_info()
            width = screen["width"]
            height = screen["height"]

        phys_x = int(width * norm_x / 1000)
        phys_y = int(height * norm_y / 1000)
        return phys_x, phys_y

    # ============ 快捷操作 ============

    def show_desktop(self):
        """显示桌面 (Win+D)"""
        self.keyboard_hotkey(["LeftWin", "D"])

    def minimize_all(self):
        """最小化所有窗口 (Win+M)"""
        self.keyboard_hotkey(["LeftWin", "M"])

    def undo(self):
        """撤销 (Ctrl+Z)"""
        self.keyboard_hotkey(["ControlLeft", "Z"])

    def copy(self):
        """复制 (Ctrl+C)"""
        self.keyboard_hotkey(["ControlLeft", "C"])

    def paste(self):
        """粘贴 (Ctrl+V)"""
        self.keyboard_hotkey(["ControlLeft", "V"])

    def cut(self):
        """剪切 (Ctrl+X)"""
        self.keyboard_hotkey(["ControlLeft", "X"])

    def select_all(self):
        """全选 (Ctrl+A)"""
        self.keyboard_hotkey(["ControlLeft", "A"])

    # ============ 健康检查 ============

    def health_check(self) -> dict:
        """健康检查"""
        return self._make_get_request("/api/health")

    def is_available(self) -> bool:
        """检查 AgentDesk 是否可用"""
        try:
            self.health_check()
            return True
        except Exception:
            return False

    # ============ 远程屏幕信息（用于坐标转换） ============

    def set_remote_screen_info(self, width: int, height: int, os_type: str = None):
        """
        设置从无障碍树提取的远程机器真实分辨率
        优先级高于 get_screen_info API，用于准确的坐标转换
        """
        self._remote_screen_info = {
            "width": width,
            "height": height,
            "os": os_type,
        }
        logger.info(f"已设置远程屏幕信息: {width}x{height} ({os_type})")

    def is_available(self) -> bool:
        """检查 AgentDesk 是否可用"""
        try:
            self.health_check()
            return True
        except Exception:
            return False