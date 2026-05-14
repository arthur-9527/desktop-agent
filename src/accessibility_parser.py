"""无障碍树解析器 - 生成全局动态信息表"""

import platform
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ElementInfo:
    """元素信息"""
    name: str
    role: str
    normalized_x: int
    normalized_y: int
    bounds: dict = field(default_factory=dict)
    extra: str = ""  # 额外信息，如状态


@dataclass
class WindowInfo:
    """窗口信息"""
    name: str
    is_active: bool
    is_visible: bool
    normalized_x: int = 0
    normalized_y: int = 0
    children: list = field(default_factory=list)


@dataclass
class GlobalInfo:
    """全局动态信息"""
    os: str = "Unknown"
    screen_width: int = 1920
    screen_height: int = 1080
    mouse_x: int = 0
    mouse_y: int = 0
    desktop_icons: list = field(default_factory=list)
    taskbar_items: list = field(default_factory=list)
    tray_items: list = field(default_factory=list)
    windows: list = field(default_factory=list)


class AccessibilityParser:
    """解析无障碍树，生成全局动态信息表"""

    # 可交互元素角色
    INTERACTIVE_ROLES = {
        "Button", "Edit", "CheckBox", "RadioButton", "ComboBox",
        "MenuItem", "TabItem", "ListItem", "Hyperlink", "Link"
    }

    # 任务栏/托盘相关关键词
    TASKBAR_KEYWORDS = ["任务栏", "Taskbar", "开始", "搜索", "文件资源管理器"]
    TRAY_KEYWORDS = ["托盘", "Tray", "输入法", "网络", "音量", "时钟", "电池"]

    def __init__(self):
        self.screen_width = 1920
        self.screen_height = 1080

    def _detect_os_from_tree(self, root: dict) -> str:
        """从无障碍树特征识别操作系统

        Args:
            root: 无障碍树根节点

        Returns:
            操作系统名称: Windows / macOS / Linux
        """
        # Windows 特征关键词
        windows_keywords = [
            "任务栏", "开始", "Windows 安全中心", "文件资源管理器",
            "Microsoft Edge", "回收站", "Program Manager",
            "Taskbar", "Start", "Windows Security", "File Explorer"
        ]
        
        # macOS 特征关键词
        macos_keywords = [
            "Dock", "Finder", "Menu Bar", "Spotlight",
            "Safari", "Launchpad", "Mission Control"
        ]
        
        # Linux 特征关键词
        linux_keywords = [
            "GNOME", "KDE", "Plasma", "Dash", "Activities"
        ]
        
        # 统计各系统的特征出现次数
        windows_count = 0
        macos_count = 0
        linux_count = 0
        
        def count_keywords(node):
            nonlocal windows_count, macos_count, linux_count
            if not node:
                return
            
            name = node.get("name", "")
            role = node.get("role", "")
            
            # 检查 Windows 特征
            for kw in windows_keywords:
                if kw.lower() in name.lower():
                    windows_count += 1
            
            # 检查 macOS 特征
            for kw in macos_keywords:
                if kw.lower() in name.lower():
                    macos_count += 1
            
            # 检查 Linux 特征
            for kw in linux_keywords:
                if kw.lower() in name.lower():
                    linux_count += 1
            
            # 递归处理子节点（只遍历前3层，快速判断）
            for child in node.get("children", [])[:10]:
                count_keywords(child)
        
        count_keywords(root)
        
        # 根据特征数量判断
        if windows_count > macos_count and windows_count > linux_count:
            return "Windows"
        elif macos_count > windows_count and macos_count > linux_count:
            return "macOS"
        elif linux_count > 0:
            return "Linux"
        else:
            # 默认根据本地系统判断
            return self._detect_local_os()
    
    def _detect_local_os(self) -> str:
        """检测本地操作系统（作为后备）"""
        system = platform.system()
        if system == "Windows":
            return "Windows"
        elif system == "Darwin":
            return "macOS"
        elif system == "Linux":
            return "Linux"
        else:
            return system or "Unknown"

    def parse(self, tree: dict, mouse_pos: Optional[dict] = None, focused_element: Optional[dict] = None) -> GlobalInfo:
        """解析无障碍树

        Args:
            tree: 无障碍树数据 {"tree": {...}}
            mouse_pos: 鼠标位置 {"x": int, "y": int} 物理坐标
            focused_element: 焦点元素 {"element": {...}}

        Returns:
            GlobalInfo 全局动态信息
        """
        info = GlobalInfo()

        root = tree.get("tree", {}) if tree else {}

        # 0. 从无障碍树识别操作系统
        info.os = self._detect_os_from_tree(root)

        # 1. 从根节点获取物理分辨率
        if root:
            bounds = root.get("bounds", {})
            self.screen_width = bounds.get("width", 1920)
            self.screen_height = bounds.get("height", 1080)
            info.screen_width = self.screen_width
            info.screen_height = self.screen_height

        # 2. 处理鼠标位置（物理坐标转归一化）
        if mouse_pos:
            info.mouse_x = self._normalize_x(mouse_pos.get("x", 0))
            info.mouse_y = self._normalize_y(mouse_pos.get("y", 0))

        # 3. 遍历解析
        self._walk(root, info, focused_element)

        return info

    def _normalize_x(self, x: int) -> int:
        """X 坐标归一化 (0-1000)"""
        return int(x / self.screen_width * 1000)

    def _normalize_y(self, y: int) -> int:
        """Y 坐标归一化 (0-1000)"""
        return int(y / self.screen_height * 1000)

    def _get_center(self, bounds: dict) -> tuple:
        """获取元素中心点

        Args:
            bounds: {x, y, width, height}

        Returns:
            (center_x, center_y)
        """
        x = bounds.get("x", 0)
        y = bounds.get("y", 0)
        w = bounds.get("width", 0)
        h = bounds.get("height", 0)
        return (x + w / 2, y + h / 2)

    def _normalize_bounds(self, bounds: dict) -> tuple:
        """归一化 bounds 的中心点

        Returns:
            (normalized_x, normalized_y)
        """
        cx, cy = self._get_center(bounds)
        return (self._normalize_x(cx), self._normalize_y(cy))

    def _is_visible(self, bounds: dict) -> bool:
        """判断元素是否可见（坐标在屏幕范围内）"""
        x = bounds.get("x", 0)
        y = bounds.get("y", 0)
        # 负数坐标（如 -31991）表示最小化或隐藏
        return x >= -100 and y >= -100

    def _walk(self, node: dict, info: GlobalInfo, focused_element: Optional[dict] = None, depth: int = 0, parent_name: str = ""):
        """递归遍历无障碍树"""
        if not node:
            return

        role = node.get("role", "")
        name = node.get("name", "")
        bounds = node.get("bounds", {})

        # 根据角色分发处理
        if role == "Window":
            self._process_window(node, info, focused_element)
        elif role == "ListItem" and ("Program Manager" in parent_name or "桌面" in parent_name):
            # 桌面图标（在 Program Manager 或 桌面 的子节点中）
            self._process_desktop_icon(node, info)
        elif role == "Pane" and "任务栏" in name:
            self._process_taskbar(node, info)
        elif role == "Button":
            # 判断是任务栏按钮还是托盘按钮
            self._process_button(node, info, depth)

        # 递归处理子节点
        for child in node.get("children", []):
            self._walk(child, info, focused_element, depth + 1, name or parent_name)

    def _process_desktop_icon(self, node: dict, info: GlobalInfo):
        """处理桌面图标"""
        name = node.get("name", "")
        bounds = node.get("bounds", {})
        if name and bounds:
            nx, ny = self._normalize_bounds(bounds)
            info.desktop_icons.append(ElementInfo(
                name=name,
                role="Icon",
                normalized_x=nx,
                normalized_y=ny,
                bounds=bounds
            ))

    def _process_window(self, node: dict, info: GlobalInfo, focused_element: Optional[dict] = None):
        """处理窗口"""
        name = node.get("name", "")
        bounds = node.get("bounds", {})

        if not name:
            return

        # 判断是否可见
        is_visible = self._is_visible(bounds)

        # 判断是否是激活窗口（通过焦点元素判断）
        is_active = False
        if is_visible and focused_element:
            # 检查焦点元素是否在这个窗口内
            focused = focused_element.get("element", {})
            focused_bounds = focused.get("bounds", {})
            if focused_bounds:
                # 检查焦点元素是否在窗口边界内
                fx = focused_bounds.get("x", -1)
                fy = focused_bounds.get("y", -1)
                wx = bounds.get("x", 0)
                wy = bounds.get("y", 0)
                ww = bounds.get("width", 0)
                wh = bounds.get("height", 0)
                # 焦点在窗口内则视为激活
                if wx <= fx <= wx + ww and wy <= fy <= wy + wh:
                    is_active = True
        
        # 如果没有焦点信息，第一个可见窗口视为激活
        if not is_active and is_visible and not any(w.is_active for w in info.windows):
            is_active = True

        nx, ny = self._normalize_bounds(bounds)

        # 提取窗口内的关键子元素（只提取可见窗口的元素）
        children = self._extract_interactive_children(node, depth=0, max_depth=3, window_visible=is_visible)

        window_info = WindowInfo(
            name=name,
            is_active=is_active,
            is_visible=is_visible,
            normalized_x=nx,
            normalized_y=ny,
            children=children
        )
        info.windows.append(window_info)

    def _extract_interactive_children(self, node: dict, depth: int = 0, max_depth: int = 3, window_visible: bool = True) -> list:
        """提取窗口内的可交互子元素
        
        Args:
            node: 当前节点
            depth: 当前深度
            max_depth: 最大深度
            window_visible: 父窗口是否可见
        """
        result = []

        if depth > max_depth:
            return result

        for child in node.get("children", []):
            role = child.get("role", "")
            name = child.get("name", "")
            bounds = child.get("bounds", {})

            if role in self.INTERACTIVE_ROLES and bounds and name:
                # 检查元素本身是否可见（过滤负数坐标）
                if not self._is_visible(bounds):
                    continue  # 跳过不可见/最小化的元素
                
                nx, ny = self._normalize_bounds(bounds)
                result.append(ElementInfo(
                    name=name,
                    role=role,
                    normalized_x=nx,
                    normalized_y=ny,
                    bounds=bounds
                ))

            # 递归
            result.extend(self._extract_interactive_children(child, depth + 1, max_depth, window_visible))

        return result

    def _process_taskbar(self, node: dict, info: GlobalInfo):
        """处理任务栏"""
        # 提取任务栏中的按钮
        for child in node.get("children", []):
            self._extract_taskbar_items(child, info, depth=0)

    def _extract_taskbar_items(self, node: dict, info: GlobalInfo, depth: int = 0):
        """提取任务栏项"""
        if depth > 5:
            return

        role = node.get("role", "")
        name = node.get("name", "")
        bounds = node.get("bounds", {})

        if role == "Button" and name and bounds:
            nx, ny = self._normalize_bounds(bounds)
            info.taskbar_items.append(ElementInfo(
                name=name,
                role=role,
                normalized_x=nx,
                normalized_y=ny,
                bounds=bounds
            ))

        # 检查是否是托盘项
        if any(kw in name for kw in self.TRAY_KEYWORDS):
            if bounds:
                nx, ny = self._normalize_bounds(bounds)
                info.tray_items.append(ElementInfo(
                    name=name,
                    role=role,
                    normalized_x=nx,
                    normalized_y=ny,
                    bounds=bounds,
                    extra=self._extract_tray_status(name)
                ))

        for child in node.get("children", []):
            self._extract_taskbar_items(child, info, depth + 1)

    def _process_button(self, node: dict, info: GlobalInfo, depth: int):
        """处理按钮（判断所属区域）"""
        name = node.get("name", "")
        bounds = node.get("bounds", {})

        if not name or not bounds:
            return

        # 检查是否是托盘相关按钮
        if any(kw in name for kw in self.TRAY_KEYWORDS):
            nx, ny = self._normalize_bounds(bounds)
            # 避免重复添加
            if not any(t.name == name for t in info.tray_items):
                info.tray_items.append(ElementInfo(
                    name=name,
                    role="Button",
                    normalized_x=nx,
                    normalized_y=ny,
                    bounds=bounds,
                    extra=self._extract_tray_status(name)
                ))

    def _extract_tray_status(self, name: str) -> str:
        """从托盘项名称提取状态"""
        if "中文" in name:
            return "中文模式"
        elif "英文" in name:
            return "英文模式"
        elif "音量" in name:
            # 提取百分比
            import re
            match = re.search(r'(\d+)%', name)
            if match:
                return f"音量 {match.group(1)}%"
            return "音量"
        elif "网络" in name or "已连接" in name:
            return "已连接"
        return ""

    def format_info_table(self, info: GlobalInfo) -> str:
        """格式化为可读的信息表

        Args:
            info: 全局动态信息

        Returns:
            格式化的文本
        """
        lines = ["## 全局动态信息表", ""]

        # 系统信息
        lines.append("### 系统环境")
        lines.append(f"- 操作系统: {info.os}")
        lines.append(f"- 屏幕分辨率: {info.screen_width}x{info.screen_height}")
        lines.append(f"- 鼠标位置: ({info.mouse_x}, {info.mouse_y}) [归一化坐标]")
        lines.append("")

        # 桌面图标
        if info.desktop_icons:
            lines.append("### 桌面图标")
            lines.append("| 名称 | 坐标 |")
            lines.append("|------|------|")
            for icon in info.desktop_icons[:20]:  # 最多 20 个
                lines.append(f"| {icon.name} | ({icon.normalized_x}, {icon.normalized_y}) |")
            lines.append("")

        # 任务栏
        if info.taskbar_items:
            lines.append("### 任务栏")
            lines.append("| 按钮 | 坐标 |")
            lines.append("|------|------|")
            for item in info.taskbar_items[:15]:
                lines.append(f"| {item.name} | ({item.normalized_x}, {item.normalized_y}) |")
            lines.append("")

        # 系统托盘
        if info.tray_items:
            lines.append("### 系统托盘")
            lines.append("| 应用 | 坐标 | 状态 |")
            lines.append("|------|------|------|")
            for item in info.tray_items[:10]:
                status = item.extra or "-"
                lines.append(f"| {item.name} | ({item.normalized_x}, {item.normalized_y}) | {status} |")
            lines.append("")

        # 当前窗口
        if info.windows:
            lines.append("### 当前窗口")
            for win in info.windows:
                status = "[激活]" if win.is_active else "[后台]"
                visible = "可见" if win.is_visible else "最小化"
                lines.append(f"#### {status} {win.name}")
                lines.append(f"状态: {visible}")
                if win.is_visible and win.children:
                    lines.append("关键元素:")
                    for child in win.children[:10]:  # 每个窗口最多 10 个
                        lines.append(f"  - [{child.role}] {child.name} ({child.normalized_x}, {child.normalized_y})")
                lines.append("")

        return "\n".join(lines)


def create_info_table(
    tree: dict,
    mouse_pos: Optional[dict] = None,
    focused_element: Optional[dict] = None
) -> str:
    """创建全局动态信息表（便捷函数）

    Args:
        tree: 无障碍树
        mouse_pos: 鼠标位置（物理坐标）
        focused_element: 焦点元素

    Returns:
        格式化的信息表文本
    """
    parser = AccessibilityParser()
    info = parser.parse(tree, mouse_pos, focused_element)
    return parser.format_info_table(info)