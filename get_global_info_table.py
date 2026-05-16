#!/usr/bin/env python3
"""获取当前状态的全局信息表"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.desktoptools.client import DesktopClient
from src.accessibility_parser import AccessibilityParser, GlobalInfo


def _format_info_table_full(info: GlobalInfo) -> str:
    """格式化为可读的信息表（无数量限制）"""
    lines = ["## 全局动态信息表", ""]

    # 系统信息
    lines.append("### 系统环境")
    lines.append(f"- 操作系统: {info.os}")
    lines.append(f"- 屏幕分辨率: {info.screen_width}x{info.screen_height}")
    lines.append(f"- 鼠标位置: ({info.mouse_x}, {info.mouse_y}) [归一化坐标]")
    lines.append("")

    # 桌面图标（无限制）
    if info.desktop_icons:
        lines.append("### 桌面图标")
        lines.append("| 名称 | 坐标 |")
        lines.append("|------|------|")
        for icon in info.desktop_icons:  # 不限制数量
            lines.append(f"| {icon.name} | ({icon.normalized_x}, {icon.normalized_y}) |")
        lines.append("")

    # 任务栏（无限制）
    if info.taskbar_items:
        lines.append("### 任务栏")
        lines.append("| 按钮 | 坐标 |")
        lines.append("|------|------|")
        for item in info.taskbar_items:  # 不限制数量
            lines.append(f"| {item.name} | ({item.normalized_x}, {item.normalized_y}) |")
        lines.append("")

    # 系统托盘（无限制）
    if info.tray_items:
        lines.append("### 系统托盘")
        lines.append("| 应用 | 坐标 | 状态 |")
        lines.append("|------|------|------|")
        for item in info.tray_items:  # 不限制数量
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
                # 按角色分类：先显示 Text，再显示其他
                text_items = [c for c in win.children if c.role == "Text"]
                other_items = [c for c in win.children if c.role != "Text"]

                if text_items:
                    lines.append(f"文本信息 ({len(text_items)}个):")
                    for child in text_items:  # 不限制数量
                        lines.append(f"  - [Text] {child.name} ({child.normalized_x}, {child.normalized_y})")

                if other_items:
                    lines.append(f"关键元素 ({len(other_items)}个):")
                    for child in other_items:  # 不限制数量
                        lines.append(f"  - [{child.role}] {child.name} ({child.normalized_x}, {child.normalized_y})")
            lines.append("")

    return "\n".join(lines)


async def main():
    # 从环境变量获取 AgentDesk 连接配置
    host = os.getenv("AGENTDESK_HOST", "192.168.9.110")
    port = int(os.getenv("AGENTDESK_PORT", "9877"))
    token = os.getenv("AGENTDESK_TOKEN", "admin123")
    timeout = float(os.getenv("AGENTDESK_TIMEOUT", "10.0"))

    print(f"连接 AgentDesk 服务: {host}:{port}")
    print("=" * 60)

    # 创建客户端
    client = DesktopClient(host=host, port=port, token=token, timeout=timeout)

    try:
        # 健康检查
        health_ok = await client.health_check()
        if not health_ok:
            print("❌ AgentDesk 服务不可用")
            return

        print("✅ AgentDesk 服务正常")
        print()

        # 获取屏幕信息
        screen_info = await client.screen_info()
        print(f"屏幕信息: {screen_info}")
        print()

        # 获取无障碍树
        print("正在获取无障碍树...")
        tree = await client.accessibility_tree(max_depth=10)
        print("✅ 无障碍树获取成功")

        # 获取鼠标位置
        print("正在获取鼠标位置...")
        mouse_pos = await client.mouse_position()
        print(f"✅ 鼠标位置: {mouse_pos}")

        # 获取焦点元素
        print("正在获取焦点元素...")
        focused = await client.accessibility_focused()
        focused_element = focused.get("element") if focused else None
        print("✅ 焦点元素获取成功")

        print()
        print("=" * 60)
        print()

        # 解析生成全局信息表
        parser = AccessibilityParser()
        global_info = parser.parse(tree, mouse_pos, focused_element)

        # 输出（使用去掉数量限制的全额格式化）
        info_table_full = _format_info_table_full(global_info)
        print(info_table_full)

        # 同时输出结构化数据
        print()
        print("=" * 60)
        print("结构化数据摘要:")
        print("=" * 60)
        print(f"操作系统: {global_info.os}")
        print(f"屏幕分辨率: {global_info.screen_width}x{global_info.screen_height}")
        print(f"鼠标位置(归一化): ({global_info.mouse_x}, {global_info.mouse_y})")
        print(f"桌面图标数量: {len(global_info.desktop_icons)}")
        print(f"任务栏按钮数量: {len(global_info.taskbar_items)}")
        print(f"系统托盘项目数量: {len(global_info.tray_items)}")
        print(f"窗口数量: {len(global_info.windows)}")

        if global_info.windows:
            print()
            print("窗口列表:")
            for win in global_info.windows:
                status = "[聚焦]" if win.is_focused else ("[后台]" if not win.is_visible else "")
                visible = "可见" if win.is_visible else "最小化"
                print(f"  - {status} {win.name} (状态: {visible}, 元素: {len(win.children)}个)")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())