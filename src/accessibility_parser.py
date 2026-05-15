"""无障碍树解析器 - 生成全局动态信息表"""

import platform
from typing import Optional, List, Dict
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
    is_focused: bool      # 是否聚焦（当前键盘焦点所在窗口）
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
        """处理窗口
        
        概念说明：
        - is_focused: 当前键盘焦点所在的窗口，只有一个
        - is_visible: 窗口是否可见（非最小化）
        """
        name = node.get("name", "")
        bounds = node.get("bounds", {})

        if not name:
            return

        # 判断是否可见（展开在桌面上）
        is_visible = self._is_visible(bounds)

        # 聚焦状态：当前键盘焦点所在的窗口
        is_focused = False
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
                # 焦点在窗口内则视为聚焦
                if wx <= fx <= wx + ww and wy <= fy <= wy + wh:
                    is_focused = True
        
        # 如果没有焦点信息，第一个可见窗口视为聚焦
        if not is_focused and is_visible and not any(w.is_focused for w in info.windows):
            is_focused = True

        nx, ny = self._normalize_bounds(bounds)

        # 提取窗口内的关键子元素（只提取可见窗口的元素）
        children = self._extract_interactive_children(node, depth=0, max_depth=3, window_visible=is_visible)

        window_info = WindowInfo(
            name=name,
            is_focused=is_focused,
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
                # 构建状态标签：只有聚焦和后台两种状态
                if not win.is_visible:
                    status = "[后台]"
                elif win.is_focused:
                    status = "[聚焦]"
                else:
                    status = ""
                
                visible = "可见" if win.is_visible else "最小化"
                lines.append(f"#### {status} {win.name}".strip())
                lines.append(f"状态: {visible}")
                if win.is_visible and win.children:
                    lines.append("关键元素:")
                    for child in win.children[:10]:  # 每个窗口最多 10 个
                        lines.append(f"  - [{child.role}] {child.name} ({child.normalized_x}, {child.normalized_y})")
                lines.append("")

        return "\n".join(lines)


@dataclass
class ElementChange:
    """单条元素变更记录（带上下文）"""
    change_type: str           # "added" / "removed" / "modified"
    element_path: str          # 完整路径 "Desktop > Window:X > Edit:Y"
    element_role: str          # "Edit", "CheckBox" 等
    element_name: str          # 元素名称
    details: str               # 具体变化描述，如 "value: '' → 'hello'"
    parent_info: str = ""      # 父节点 "Pane '文本编辑区'"
    sibling_info: str = ""     # 兄弟摘要 "Button:保存, Button:另存为"
    child_info: str = ""       # 子级摘要（仅新增容器类）
    
    def to_string(self) -> str:
        """格式化为可读字符串"""
        parts = [f"[{self.change_type}] {self.element_role} '{self.element_name}' {self.details}"]
        parts.append(f"  路径: {self.element_path}")
        if self.parent_info:
            parts.append(f"  父级: {self.parent_info}")
        if self.sibling_info:
            parts.append(f"  同级: {self.sibling_info}")
        if self.child_info:
            parts.append(f"  子级: {self.child_info}")
        return "\n".join(parts)


@dataclass
class DiffResult:
    """树对比结果（全面比较）"""
    changed: bool = False
    changes: List[ElementChange] = field(default_factory=list)
    
    # 向后兼容的分组属性
    @property
    def window_changes(self) -> List[str]:
        """兼容旧代码：返回窗口相关变更"""
        return [c.to_string() for c in self.changes 
                if c.element_role == "Window" or "Window:" in c.element_path]
    
    @property
    def focus_changes(self) -> List[str]:
        """兼容旧代码：返回焦点相关变更"""
        return [c.to_string() for c in self.changes 
                if "focus" in c.details.lower() or "focused" in c.details.lower()]
    
    @property
    def dialog_changes(self) -> List[str]:
        """兼容旧代码：返回弹窗相关变更"""
        return [c.to_string() for c in self.changes 
                if c.element_role in {"Dialog", "Alert"}]
    
    @property
    def element_changes(self) -> List[str]:
        """兼容旧代码：返回所有元素变更"""
        return [c.to_string() for c in self.changes 
                if c.element_role not in {"Window", "Dialog", "Alert"}]
    
    def summary(self) -> str:
        """生成变化摘要"""
        if not self.changed or not self.changes:
            return "无变化"
        
        parts = []
        if self.changes:
            parts.append(f"共 {len(self.changes)} 处变更")
            # 按类型统计
            added = sum(1 for c in self.changes if c.change_type == "added")
            removed = sum(1 for c in self.changes if c.change_type == "removed")
            modified = sum(1 for c in self.changes if c.change_type == "modified")
            stats = []
            if added: stats.append(f"新增 {added}")
            if removed: stats.append(f"删除 {removed}")
            if modified: stats.append(f"修改 {modified}")
            if stats:
                parts.append(f"({' | '.join(stats)})")
        
        return "; ".join(parts) if parts else "有变化"
    
    def format_for_llm(self, max_items: int = 10) -> str:
        """格式化为 LLM 友好的逐条变更列表
        
        Args:
            max_items: 最多显示的变更条数
            
        Returns:
            格式化的变更描述文本
        """
        if not self.changed or not self.changes:
            return "界面无变化"
        
        lines = [f"界面变化检测（共 {len(self.changes)} 处变更）:"]
        lines.append("")
        
        for i, change in enumerate(self.changes[:max_items], 1):
            lines.append(f"{i}. {change.to_string()}")
            lines.append("")
        
        if len(self.changes) > max_items:
            lines.append(f"... 还有 {len(self.changes) - max_items} 处变更未显示")
        
        return "\n".join(lines)


def diff_trees(before: dict, after: dict, max_depth: int = 15) -> DiffResult:
    """对比两份无障碍树，检测变化（全面比较）
    
    使用路径匹配逐元素对比，检测：
    - 新增/删除的元素
    - 属性变化（name, value, bounds, state）
    - 带上下文信息（父级、兄弟、子级）
    
    纯代码执行，不调用 LLM。
    
    Args:
        before: 操作前的无障碍树 {"tree": {...}}
        after: 操作后的无障碍树 {"tree": {...}}
        max_depth: 最大遍历深度
        
    Returns:
        DiffResult 变化检测结果
    """
    result = DiffResult()
    
    before_root = before.get("tree", {}) if before else {}
    after_root = after.get("tree", {}) if after else {}
    
    if not before_root or not after_root:
        return result
    
    # 提取两棵树的完整元素映射（路径 -> 节点）
    before_elements = _extract_elements_with_path(before_root, max_depth)
    after_elements = _extract_elements_with_path(after_root, max_depth)
    
    # 获取所有路径集合
    before_paths = set(before_elements.keys())
    after_paths = set(after_elements.keys())
    
    # 1. 检测新增元素
    added_paths = after_paths - before_paths
    for path in sorted(added_paths):
        node = after_elements[path]
        change = _create_element_change(
            change_type="added",
            path=path,
            node=node,
            context=_get_context_info(path, after_elements)
        )
        result.changes.append(change)
    
    # 2. 检测删除元素
    removed_paths = before_paths - after_paths
    for path in sorted(removed_paths):
        node = before_elements[path]
        change = _create_element_change(
            change_type="removed",
            path=path,
            node=node,
            context=_get_context_info(path, before_elements)
        )
        result.changes.append(change)
    
    # 3. 检测修改的元素（路径相同但属性不同）
    common_paths = before_paths & after_paths
    for path in sorted(common_paths):
        before_node = before_elements[path]
        after_node = after_elements[path]
        
        changes = _compare_node_properties(before_node, after_node)
        if changes:
            context = _get_context_info(path, after_elements)
            for change_detail in changes:
                result.changes.append(ElementChange(
                    change_type="modified",
                    element_path=path,
                    element_role=after_node.get("role", "Unknown"),
                    element_name=after_node.get("name", ""),
                    details=change_detail,
                    parent_info=context.get("parent", ""),
                    sibling_info=context.get("siblings", ""),
                    child_info=""  # 修改不显示子级（避免信息过载）
                ))
    
    # 判断是否发生变化
    result.changed = len(result.changes) > 0
    
    return result


def _extract_elements_with_path(root: dict, max_depth: int = 15) -> Dict[str, dict]:
    """提取所有元素及其路径
    
    Args:
        root: 树根节点
        max_depth: 最大遍历深度
        
    Returns:
        路径到节点的映射字典
    """
    result = {}
    
    def walk(node, parent_path: str = "Desktop", depth: int = 0):
        if not node or depth > max_depth:
            return
        
        role = node.get("role", "Unknown")
        name = node.get("name", "")
        # 构建路径签名（包含 role 和 name 用于唯一标识）
        path_segment = f"{role}:{name}" if name else role
        current_path = f"{parent_path} > {path_segment}" if parent_path else path_segment
        
        # 存储节点（包含路径信息便于上下文提取）
        result[current_path] = node
        
        # 递归处理子节点
        for child in node.get("children", []):
            walk(child, current_path, depth + 1)
    
    walk(root)
    return result


def _get_context_info(path: str, elements: Dict[str, dict]) -> Dict[str, str]:
    """获取元素的上下文信息（父级、兄弟、子级）
    
    Args:
        path: 元素完整路径
        elements: 所有元素映射
        
    Returns:
        包含 parent, siblings, children 的字典
    """
    context = {"parent": "", "siblings": "", "children": ""}
    
    # 解析路径获取父路径
    parts = path.split(" > ")
    if len(parts) < 2:
        return context
    
    current_role_name = parts[-1]
    current_role = current_role_name.split(":")[0]
    parent_path = " > ".join(parts[:-1])
    
    # 获取父级信息
    if parent_path in elements:
        parent_node = elements[parent_path]
        parent_role = parent_node.get("role", "Unknown")
        parent_name = parent_node.get("name", "")
        context["parent"] = f"{parent_role} '{parent_name}'" if parent_name else parent_role
    
    # 获取兄弟信息（同父的其他子节点）
    sibling_parts = []
    for p, node in elements.items():
        if p.startswith(parent_path + " > ") and p != path:
            # 这是父节点的直接子节点
            relative = p[len(parent_path + " > "):]
            if " > " not in relative:  # 直接子节点
                role = node.get("role", "Unknown")
                name = node.get("name", "")
                if name:
                    sibling_parts.append(f"{role}:{name}")
                else:
                    sibling_parts.append(role)
    
    # 限制兄弟数量，避免信息过载
    if sibling_parts:
        if len(sibling_parts) > 5:
            context["siblings"] = ", ".join(sibling_parts[:5]) + f" ...等{sibling_parts[5:]}个"
        else:
            context["siblings"] = ", ".join(sibling_parts)
    
    # 获取子级信息（仅对新增的元素）
    if path in elements:
        current_node = elements[path]
        child_parts = []
        for child in current_node.get("children", [])[:3]:  # 最多3个子级
            child_role = child.get("role", "Unknown")
            child_name = child.get("name", "")
            if child_name:
                child_parts.append(f"{child_role}:{child_name}")
            else:
                child_parts.append(child_role)
        
        if child_parts:
            context["children"] = ", ".join(child_parts)
            remaining = len(current_node.get("children", [])) - 3
            if remaining > 0:
                context["children"] += f" ...等{remaining}个子元素"
    
    return context


def _create_element_change(
    change_type: str,
    path: str,
    node: dict,
    context: Dict[str, str]
) -> ElementChange:
    """创建 ElementChange 对象
    
    Args:
        change_type: 变更类型
        path: 元素路径
        node: 节点数据
        context: 上下文信息
        
    Returns:
        ElementChange 对象
    """
    role = node.get("role", "Unknown")
    name = node.get("name", "")
    
    # 构建详情描述
    if change_type == "added":
        details = f"bounds: {node.get('bounds', {})}"
    elif change_type == "removed":
        details = "元素已删除"
    else:
        details = ""
    
    return ElementChange(
        change_type=change_type,
        element_path=path,
        element_role=role,
        element_name=name,
        details=details,
        parent_info=context.get("parent", ""),
        sibling_info=context.get("siblings", ""),
        child_info=context.get("children", "") if change_type == "added" else ""
    )


def _compare_node_properties(before: dict, after: dict) -> List[str]:
    """比较两个节点的属性，返回变化详情列表
    
    Args:
        before: 操作前节点
        after: 操作后节点
        
    Returns:
        变化描述列表，无变化返回空列表
    """
    changes = []
    
    # 1. 比较 name
    before_name = before.get("name", "")
    after_name = after.get("name", "")
    if before_name != after_name:
        changes.append(f'name: "{before_name}" → "{after_name}"')
    
    # 2. 比较 value（输入框、复选框等）
    before_value = before.get("value", "")
    after_value = after.get("value", "")
    if before_value != after_value:
        # 截断过长的值
        b_val = str(before_value)[:30] + "..." if len(str(before_value)) > 30 else str(before_value)
        a_val = str(after_value)[:30] + "..." if len(str(after_value)) > 30 else str(after_value)
        changes.append(f'value: "{b_val}" → "{a_val}"')
    
    # 3. 比较 bounds（位置/大小）
    before_bounds = before.get("bounds", {})
    after_bounds = after.get("bounds", {})
    if before_bounds != after_bounds:
        # 只记录有意义的变化（位置或大小变化超过5像素）
        b_x = before_bounds.get("x", 0)
        b_y = before_bounds.get("y", 0)
        b_w = before_bounds.get("width", 0)
        b_h = before_bounds.get("height", 0)
        a_x = after_bounds.get("x", 0)
        a_y = after_bounds.get("y", 0)
        a_w = after_bounds.get("width", 0)
        a_h = after_bounds.get("height", 0)
        
        # 判断是否为窗口移动/缩放
        if abs(a_x - b_x) > 5 or abs(a_y - b_y) > 5:
            changes.append(f"position: ({b_x},{b_y}) → ({a_x},{a_y})")
        if abs(a_w - b_w) > 5 or abs(a_h - b_h) > 5:
            changes.append(f"size: {b_w}x{b_h} → {a_w}x{a_h}")
    
    # 4. 比较 state（状态字段）
    before_state = before.get("state", {})
    after_state = after.get("state", {})
    if isinstance(before_state, dict) and isinstance(after_state, dict):
        # 提取关键状态
        state_keys = ["checked", "enabled", "focused", "selected", "expanded", "collapsed"]
        for key in state_keys:
            b_val = before_state.get(key)
            a_val = after_state.get(key)
            if b_val != a_val and (b_val is not None or a_val is not None):
                changes.append(f"state.{key}: {b_val} → {a_val}")
    
    # 5. 比较 description（描述文本）
    before_desc = before.get("description", "")
    after_desc = after.get("description", "")
    if before_desc != after_desc:
        changes.append(f'description: "{before_desc}" → "{after_desc}"')
    
    # 6. 比较 accessibility_id（用于追踪元素唯一性）
    before_id = before.get("accessibility_id", "")
    after_id = after.get("accessibility_id", "")
    if before_id != after_id and (before_id or after_id):
        changes.append(f"id: {before_id} → {after_id}")
    
    return changes


def _extract_windows(root: dict) -> List[dict]:
    """从无障碍树中提取所有窗口
    
    Args:
        root: 树根节点
    
    Returns:
        窗口列表，每个窗口包含 name, bounds, is_visible, is_focused
    """
    windows = []
    
    def walk(node, depth=0):
        if not node or depth > 15:
            return
        
        role = node.get("role", "")
        name = node.get("name", "")
        bounds = node.get("bounds", {})
        
        if role == "Window" and name:
            # 判断是否可见
            x = bounds.get("x", 0)
            y = bounds.get("y", 0)
            is_visible = x >= -100 and y >= -100
            
            windows.append({
                "name": name,
                "bounds": bounds,
                "is_visible": is_visible,
                "is_focused": False  # 需要外部判断
            })
        
        for child in node.get("children", []):
            walk(child, depth + 1)
    
    walk(root)
    
    # 标记第一个可见窗口为聚焦（简化逻辑）
    for w in windows:
        if w["is_visible"]:
            w["is_focused"] = True
            break
    
    return windows


def _find_elements_by_role(root: dict, roles: set) -> List[dict]:
    """按角色查找元素
    
    Args:
        root: 树根节点
        roles: 角色集合，如 {"Button", "Edit"}
    
    Returns:
        匹配的元素列表
    """
    elements = []
    
    def walk(node, depth=0):
        if not node or depth > 20:
            return
        
        role = node.get("role", "")
        if role in roles:
            elements.append(node)
        
        for child in node.get("children", []):
            walk(child, depth + 1)
    
    walk(root)
    return elements


def diff_focused(focused_before: dict, focused_after: dict):
    """对比聚焦元素变化，生成可读的差异描述

    对应 diff_a11y.py 中 compare_focused() 的思路，
    将聚焦变化作为独立维度提供给 LLM 做综合判断。

    Args:
        focused_before: 操作前的聚焦元素 {"element": {...}}
        focused_after: 操作后的聚焦元素 {"element": {...}}

    Returns:
        (diff_text, has_changed) — 聚焦变化的可读描述 + 是否有变化
    """
    elem_before = (focused_before or {}).get("element") or {}
    elem_after = (focused_after or {}).get("element") or {}

    if not elem_before and not elem_after:
        return ("（无聚焦元素信息）", False)

    if not elem_before:
        return (f"操作前无聚焦元素 → 操作后: [{elem_after.get('role', '?')}] {elem_after.get('name', '')}", True)

    if not elem_after:
        return (f"操作前: [{elem_before.get('role', '?')}] {elem_before.get('name', '')} → 操作后无聚焦元素", True)

    lines = []
    has_changed = False

    role_before = elem_before.get("role", "?")
    role_after = elem_after.get("role", "?")
    name_before = elem_before.get("name", "")
    name_after = elem_after.get("name", "")

    if role_before != role_after or name_before != name_after:
        lines.append(f"聚焦元素变化: [{role_before}] '{name_before}' → [{role_after}] '{name_after}'")
        has_changed = True
    else:
        lines.append(f"聚焦元素: [{role_before}] '{name_before}'")

    # Bounds
    bounds_before = elem_before.get("bounds", {})
    bounds_after = elem_after.get("bounds", {})
    if bounds_before != bounds_after:
        lines.append(f"  位置: {bounds_before} → {bounds_after}")
        has_changed = True

    # State
    state_before = elem_before.get("state", {})
    state_after = elem_after.get("state", {})
    if isinstance(state_before, dict) and isinstance(state_after, dict):
        for key in ["focused", "checked", "selected", "expanded"]:
            b = state_before.get(key)
            a = state_after.get(key)
            if b != a and (b is not None or a is not None):
                lines.append(f"  state.{key}: {b} → {a}")
                has_changed = True

    # Value
    value_before = elem_before.get("value", "")
    value_after = elem_after.get("value", "")
    if value_before != value_after:
        b_val = str(value_before)[:50]
        a_val = str(value_after)[:50]
        lines.append(f"  value: '{b_val}' → '{a_val}'")
        has_changed = True

    return ("\n".join(lines), has_changed)


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
