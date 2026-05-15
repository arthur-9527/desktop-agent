"""系统快捷键参考表

根据远程主机操作系统自动注入对应的快捷键列表
"""


# ============================================================================
# Windows 快捷键
# ============================================================================

WINDOWS_SHORTCUTS = """## Windows 常用快捷键

| 快捷键 | 功能 |
|--------|------|
| **系统 & 桌面** | |
| Win | 开始菜单 |
| Win+D | 显示/隐藏桌面 |
| Win+M | 最小化所有窗口 |
| Win+Shift+M | 还原最小化的窗口 |
| Win+L | 锁定屏幕 |
| Win+R | 运行对话框 |
| Win+E | 文件资源管理器 |
| Win+I | 设置 |
| Win+S | 搜索 |
| Win+A | 操作中心 |
| Win+K | 连接设备(投影/蓝牙) |
| Win+P | 投影模式 |
| Win+X | 快速链接菜单 |
| Win+V | 剪贴板历史 |
| Win+. | Emoji 面板 |
| Win+; | Emoji 面板(同上) |
| Win+Pause | 系统属性 |
| Win+PrtSc | 截图并自动保存 |
| PrtSc | 全屏截图到剪贴板 |
| Alt+PrtSc | 当前窗口截图到剪贴板 |
| Win+Shift+S | 区域截图(Snip & Sketch) |
| **窗口管理** | |
| Alt+Tab | 切换窗口 |
| Win+Tab | 任务视图,平铺展示全部已开启程序，用于切换窗口 |
| Alt+F4 | 关闭窗口/程序 |
| Win+↑ | 最大化窗口 |
| Win+↓ | 还原/最小化窗口 |
| Win+← | 窗口贴左半屏 |
| Win+→ | 窗口贴右半屏 |
| Win+Shift+← | 移动窗口到左侧显示器 |
| Win+Shift+→ | 移动窗口到右侧显示器 |
| Win+Home | 最小化非活动窗口 |
| Win+T | 循环切换任务栏程序 |
| Win+数字键 | 打开/切换任务栏对应程序 |
| Win+Shift+数字键 | 新开任务栏对应程序实例 |
| **虚拟桌面** | |
| Win+Ctrl+D | 新建虚拟桌面 |
| Win+Ctrl+← | 切换到左侧虚拟桌面 |
| Win+Ctrl+→ | 切换到右侧虚拟桌面 |
| Win+Ctrl+F4 | 关闭当前虚拟桌面 |
| **文件资源管理器** | |
| Alt+← | 后退 |
| Alt+→ | 前进 |
| Alt+↑ | 上一级目录 |
| F2 | 重命名 |
| F3 | 搜索 |
| F4 | 定位到地址栏 |
| F5 | 刷新 |
| F11 | 全屏 |
| Delete | 删除到回收站 |
| Shift+Delete | 永久删除(不进回收站) |
| Ctrl+Shift+N | 新建文件夹 |
| Alt+Enter | 查看属性 |
| **任务管理器 & 系统** | |
| Ctrl+Shift+Esc | 任务管理器 |
| Ctrl+Alt+Delete | 安全选项界面 |
| Win+Ctrl+Shift+B | 重置显卡驱动 |
| **输入法 & 语言** | |
| Win+Space | 切换输入法 |
| Ctrl+Space | 切换中英文(部分输入法) |
| Shift | 切换中英文(部分输入法) |
| **通用编辑** | |
| Ctrl+C | 复制 |
| Ctrl+X | 剪切 |
| Ctrl+V | 粘贴 |
| Ctrl+A | 全选 |
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Ctrl+S | 保存 |
| Ctrl+F | 查找 |
| Ctrl+H | 查找并替换 |
| Ctrl+N | 新建 |
| Ctrl+O | 打开 |
| Ctrl+P | 打印 |
| Ctrl+W | 关闭当前标签/文档 |
| **浏览器** | |
| Ctrl+T | 新标签页 |
| Ctrl+W | 关闭标签页 |
| Ctrl+Shift+T | 恢复关闭的标签页 |
| Ctrl+L | 定位到地址栏 |
| Ctrl+Tab | 切换到下一标签页 |
| Ctrl+Shift+Tab | 切换到上一标签页 |
| Ctrl+R / F5 | 刷新页面 |
| Ctrl+Shift+R | 强制刷新(跳过缓存) |
| Ctrl++ | 放大页面 |
| Ctrl+- | 缩小页面 |
| Ctrl+0 | 重置缩放 |
| Ctrl+D | 收藏当前页 |
| Ctrl+H | 历史记录 |
| Ctrl+J | 下载记录 |
| Ctrl+Shift+N | 新建隐私窗口 |
| F12 | 开发者工具 |
| **辅助功能** | |
| Win+U | 辅助功能设置 |
| Win++ | 放大镜放大 |
| Win+- | 放大镜缩小 |
| Win+Esc | 关闭放大镜 |
| **文本光标操作** | |
| Home | 行首 |
| End | 行尾 |
| Ctrl+Home | 文档开头 |
| Ctrl+End | 文档末尾 |
| Ctrl+← | 向左跳一个单词 |
| Ctrl+→ | 向右跳一个单词 |
| Shift+← / → | 选中字符 |
| Ctrl+Shift+← / → | 选中单词 |
| Shift+Home / End | 选中到行首/行尾 |
"""


# ============================================================================
# macOS 快捷键
# ============================================================================

MACOS_SHORTCUTS = """## macOS 常用快捷键

| 快捷键 | 功能 |
|--------|------|
| Cmd+Tab | 切换应用 |
| Cmd+W/Q | 关闭窗口/退出应用 |
| Cmd+Space | Spotlight 搜索 |
| Cmd+, | 偏好设置 |
| Cmd+Shift+3/4 | 截屏(全屏/区域) |
| Cmd+C/X/V/A | 复制/剪切/粘贴/全选 |
| Cmd+Z/Shift+Z | 撤销/重做 |
| Cmd+S/F/N/P | 保存/查找/新建/打印 |
| Cmd+T/W/L/R | 新标签/关标签/地址栏/刷新(浏览器) |
"""


# ============================================================================
# Linux 快捷键（GNOME/KDE）
# ============================================================================

LINUX_SHORTCUTS = """## Linux 常用快捷键

| 快捷键 | 功能 |
|--------|------|
| Alt+Tab | 切换窗口 |
| Super | 活动概览/启动器 |
| Super+D | 显示桌面 |
| Alt+F4 | 关闭窗口 |
| Ctrl+Alt+T | 打开终端 |
| Alt+F2 | 运行命令 |
| Super+L | 锁定屏幕 |
| Ctrl+C/X/V/A | 复制/剪切/粘贴/全选 |
| Ctrl+Z/Shift+Z | 撤销/重做 |
| Ctrl+S/F/N/O/P | 保存/查找/新建/打开/打印 |
| Ctrl+T/W/L | 新标签/关标签/地址栏(浏览器) |
"""


# ============================================================================
# 导出函数
# ============================================================================

def get_shortcuts(os_type: str) -> str:
    """根据操作系统类型获取对应的快捷键参考表
    
    Args:
        os_type: 操作系统类型 Windows / macOS / Linux
        
    Returns:
        格式化后的快捷键参考表文本
    """
    shortcuts_map = {
        "Windows": WINDOWS_SHORTCUTS,
        "macOS": MACOS_SHORTCUTS,
        "Linux": LINUX_SHORTCUTS,
    }
    
    # 默认返回 Windows
    return shortcuts_map.get(os_type, WINDOWS_SHORTCUTS)


__all__ = ["get_shortcuts", "WINDOWS_SHORTCUTS", "MACOS_SHORTCUTS", "LINUX_SHORTCUTS"]