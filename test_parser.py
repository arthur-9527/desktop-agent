"""测试全局动态信息表生成"""

import json
import re
from src.accessibility_parser import AccessibilityParser, create_info_table


def parse_accessibility_md(filepath: str) -> dict:
    """解析 Accessibility.md 格式的无障碍树文本为字典"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取树部分
    lines = content.split('\n')
    tree_lines = []
    in_tree = False
    for line in lines:
        if '## 根节点' in line:
            in_tree = True
        if in_tree:
            if line.startswith('## 统计信息'):
                break
            tree_lines.append(line)

    # 解析为字典结构
    def parse_line(line: str, depth: int) -> dict:
        """解析单行"""
        # 匹配: ├── [Button] 名称 (50x50@2172,1258)
        match = re.match(r'^(\s*[├└│─]+)\s*\[(\w+)\]\s*(.+?)\s*(?:\((\d+)x(\d+)@(-?\d+),(-?\d+)\))?$', line)
        if match:
            role = match.group(2)
            name = match.group(3).strip()
            if match.group(4):  # 有bounds
                bounds = {
                    "width": int(match.group(4)),
                    "height": int(match.group(5)),
                    "x": int(match.group(6)),
                    "y": int(match.group(7))
                }
            else:
                bounds = {}
            return {"role": role, "name": name, "bounds": bounds, "children": []}
        return None

    # 简化：构建一个扁平的结构
    # 实际测试中我们可以直接使用模拟数据
    root = {
        "role": "Pane",
        "name": "桌面 1",
        "bounds": {"x": 0, "y": 0, "width": 2560, "height": 1440},
        "children": []
    }

    # 提取桌面图标
    desktop_icons = []
    for line in tree_lines:
        if '[ListItem]' in line:
            match = re.search(r'\[ListItem\]\s*(.+?)\s*\((\d+)x(\d+)@(\d+),(\d+)\)', line)
            if match:
                desktop_icons.append({
                    "role": "ListItem",
                    "name": match.group(1).strip(),
                    "bounds": {
                        "width": int(match.group(2)),
                        "height": int(match.group(3)),
                        "x": int(match.group(4)),
                        "y": int(match.group(5))
                    },
                    "children": []
                })

    # 提取窗口
    windows = []
    for line in tree_lines:
        if '[Window]' in line:
            match = re.search(r'\[Window\]\s*(.+?)\s*\((\d+)x(\d+)@(-?\d+),(-?\d+)\)', line)
            if match:
                windows.append({
                    "role": "Window",
                    "name": match.group(1).strip(),
                    "bounds": {
                        "width": int(match.group(2)),
                        "height": int(match.group(3)),
                        "x": int(match.group(4)),
                        "y": int(match.group(5))
                    },
                    "children": []
                })

    # 提取任务栏按钮
    taskbar_buttons = []
    in_taskbar = False
    for line in tree_lines:
        if '任务栏' in line:
            in_taskbar = True
        if in_taskbar and '[Button]' in line:
            match = re.search(r'\[Button\]\s*(.+?)\s*\((\d+)x(\d+)@(\d+),(\d+)\)', line)
            if match:
                taskbar_buttons.append({
                    "role": "Button",
                    "name": match.group(1).strip(),
                    "bounds": {
                        "width": int(match.group(2)),
                        "height": int(match.group(3)),
                        "x": int(match.group(4)),
                        "y": int(match.group(5))
                    },
                    "children": []
                })

    root["children"] = desktop_icons + windows + taskbar_buttons

    return {"tree": root}


def build_mock_tree() -> dict:
    """基于 Accessibility.md 构建模拟无障碍树"""
    return {
        "tree": {
            "role": "Pane",
            "name": "桌面 1",
            "bounds": {"x": 0, "y": 0, "width": 2560, "height": 1440},
            "children": [
                # 系统托盘溢出窗口
                {
                    "role": "Pane",
                    "name": "系统托盘溢出窗口",
                    "bounds": {"x": 2151, "y": 1237, "width": 293, "height": 143},
                    "children": [
                        {"role": "Button", "name": "Agent Desk", "bounds": {"x": 2172, "y": 1258, "width": 50, "height": 50}},
                        {"role": "Button", "name": "NVIDIA 设置", "bounds": {"x": 2222, "y": 1258, "width": 50, "height": 50}},
                        {"role": "Button", "name": "火绒安全软件", "bounds": {"x": 2272, "y": 1258, "width": 50, "height": 50}},
                        {"role": "Button", "name": "Clash Verge", "bounds": {"x": 2322, "y": 1258, "width": 50, "height": 50}},
                    ]
                },
                # 任务栏
                {
                    "role": "Pane",
                    "name": "任务栏",
                    "bounds": {"x": 0, "y": 1380, "width": 2560, "height": 60},
                    "children": [
                        {"role": "Button", "name": "开始", "bounds": {"x": 1002, "y": 1380, "width": 56, "height": 60}},
                        {"role": "Button", "name": "搜索", "bounds": {"x": 1061, "y": 1390, "width": 275, "height": 40}},
                        {"role": "Button", "name": "任务视图", "bounds": {"x": 1338, "y": 1380, "width": 55, "height": 60}},
                        {"role": "Button", "name": "文件资源管理器 已固定", "bounds": {"x": 1393, "y": 1380, "width": 55, "height": 60}},
                        {"role": "Button", "name": "Visual Studio Code - 1 个运行窗口", "bounds": {"x": 1448, "y": 1380, "width": 55, "height": 60}},
                        {"role": "Button", "name": "Google Chrome - 1 个运行窗口", "bounds": {"x": 1503, "y": 1380, "width": 55, "height": 60}},
                        {"role": "Button", "name": "托盘输入指示器 中文模式", "bounds": {"x": 2317, "y": 1380, "width": 40, "height": 60}},
                        {"role": "Button", "name": "网络 Center 已连接", "bounds": {"x": 2357, "y": 1380, "width": 35, "height": 60}},
                        {"role": "Button", "name": "音量 扬声器: 36%", "bounds": {"x": 2392, "y": 1380, "width": 35, "height": 60}},
                        {"role": "Button", "name": "时钟 10:00", "bounds": {"x": 2427, "y": 1380, "width": 83, "height": 60}},
                    ]
                },
                # VS Code 窗口（激活）
                {
                    "role": "Window",
                    "name": "agentdesk说明文档.md - deskagent - Visual Studio Code",
                    "bounds": {"x": -9, "y": -9, "width": 2578, "height": 1398},
                    "children": [
                        {"role": "Button", "name": "Minimize", "bounds": {"x": 2388, "y": 0, "width": 57, "height": 43}},
                        {"role": "Button", "name": "Maximize", "bounds": {"x": 2445, "y": 0, "width": 58, "height": 43}},
                        {"role": "Button", "name": "Close", "bounds": {"x": 2502, "y": 0, "width": 58, "height": 43}},
                        {"role": "Edit", "name": "文件搜索", "bounds": {"x": 100, "y": 100, "width": 200, "height": 30}},
                    ]
                },
                # Chrome 窗口（后台最小化）
                {
                    "role": "Window",
                    "name": "llama-swap - Google Chrome",
                    "bounds": {"x": -31991, "y": -32000, "width": 2560, "height": 1380},
                    "children": [
                        {"role": "Button", "name": "最小化", "bounds": {"x": -32163, "y": -31999, "width": 57, "height": 49}},
                        {"role": "Button", "name": "关闭", "bounds": {"x": -32049, "y": -31999, "width": 58, "height": 49}},
                    ]
                },
                # 桌面图标（在 List 下）
                {
                    "role": "Pane",
                    "name": "Program Manager",
                    "bounds": {"x": 0, "y": 0, "width": 2560, "height": 1440},
                    "children": [
                        {
                            "role": "Pane",
                            "name": "",
                            "bounds": {"x": 0, "y": 0, "width": 2560, "height": 1440},
                            "children": [
                                {
                                    "role": "List",
                                    "name": "桌面",
                                    "bounds": {"x": 0, "y": 0, "width": 2560, "height": 1440},
                                    "children": [
                                        {"role": "ListItem", "name": "回收站", "bounds": {"x": 0, "y": 5, "width": 92, "height": 87}},
                                        {"role": "ListItem", "name": "Clash Verge", "bounds": {"x": 0, "y": 249, "width": 92, "height": 87}},
                                        {"role": "ListItem", "name": "Google Chrome", "bounds": {"x": 0, "y": 493, "width": 92, "height": 107}},
                                        {"role": "ListItem", "name": "Visual Studio Code", "bounds": {"x": 279, "y": 981, "width": 92, "height": 107}},
                                        {"role": "ListItem", "name": "微信", "bounds": {"x": 0, "y": 981, "width": 92, "height": 87}},
                                        {"role": "ListItem", "name": "Steam", "bounds": {"x": 93, "y": 371, "width": 92, "height": 87}},
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }


def main():
    print("=" * 60)
    print("全局动态信息表生成测试")
    print("=" * 60)

    # 使用模拟数据
    tree = build_mock_tree()

    # 模拟鼠标位置
    mouse_pos = {"x": 1280, "y": 720}  # 屏幕中心

    # 模拟焦点元素
    focused = {"element": {"role": "Edit", "name": "文件搜索"}}

    # 创建解析器
    parser = AccessibilityParser()

    # 解析
    info = parser.parse(tree, mouse_pos, focused)

    # 打印结构化信息
    print(f"\n屏幕分辨率: {info.screen_width}x{info.screen_height}")
    print(f"鼠标位置: ({info.mouse_x}, {info.mouse_y})")
    print(f"桌面图标数量: {len(info.desktop_icons)}")
    print(f"任务栏项数量: {len(info.taskbar_items)}")
    print(f"托盘项数量: {len(info.tray_items)}")
    print(f"窗口数量: {len(info.windows)}")

    # 生成信息表
    print("\n" + "=" * 60)
    print("生成的全局动态信息表:")
    print("=" * 60)
    info_table = parser.format_info_table(info)
    print(info_table)


if __name__ == "__main__":
    main()