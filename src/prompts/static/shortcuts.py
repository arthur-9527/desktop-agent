"""系统快捷键参考表

根据远程主机操作系统自动注入对应的快捷键列表
"""


# ============================================================================
# Windows 快捷键
# ============================================================================

WINDOWS_SHORTCUTS = """
## Windows 系统快捷键参考

### 窗口管理
| 快捷键 | 功能 |
|--------|------|
| Win | 打开/关闭开始菜单 |
| Win+D | 显示桌面/恢复窗口 |
| Win+M | 最小化所有窗口 |
| Win+Shift+M | 还原最小化的窗口 |
| Win+Tab | 打开任务视图 |
| Alt+Tab | 切换窗口 |
| Alt+F4 | 关闭当前窗口 |
| Ctrl+W | 关闭当前标签页/窗口 |
| Win+←/→ | 窗口靠左/靠右 |
| Win+↑ | 最大化窗口 |
| Win+↓ | 最小化窗口 |

### 系统操作
| 快捷键 | 功能 |
|--------|------|
| Win+R | 打开运行对话框 |
| Win+E | 打开文件资源管理器 |
| Win+I | 打开设置 |
| Win+L | 锁定计算机 |
| Win+X | 打开快速链接菜单 |
| Ctrl+Shift+Esc | 打开任务管理器 |
| Win+Pause | 打开系统属性 |
| Win+Space | 切换输入法 |
| Win+Ctrl+D | 创建虚拟桌面 |
| Win+Ctrl+←/→ | 切换虚拟桌面 |

### 编辑操作
| 快捷键 | 功能 |
|--------|------|
| Ctrl+C | 复制 |
| Ctrl+X | 剪切 |
| Ctrl+V | 粘贴 |
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Ctrl+A | 全选 |
| Ctrl+F | 查找 |
| Ctrl+H | 替换 |
| Ctrl+S | 保存 |
| Ctrl+P | 打印 |
| Ctrl+N | 新建 |
| Ctrl+O | 打开 |

### 浏览器常用
| 快捷键 | 功能 |
|--------|------|
| Ctrl+T | 新建标签页 |
| Ctrl+W | 关闭标签页 |
| Ctrl+Tab | 切换到下一个标签页 |
| Ctrl+Shift+Tab | 切换到上一个标签页 |
| Ctrl+L | 选中地址栏 |
| Ctrl+D | 添加书签 |
| F5 | 刷新 |
| Ctrl+F5 | 强制刷新 |
| Ctrl+Shift+N | 打开无痕窗口 |
"""


# ============================================================================
# macOS 快捷键
# ============================================================================

MACOS_SHORTCUTS = """
## macOS 系统快捷键参考

### 窗口管理
| 快捷键 | 功能 |
|--------|------|
| Cmd+Tab | 切换应用程序 |
| Cmd+` | 同一应用内切换窗口 |
| Cmd+W | 关闭当前窗口 |
| Cmd+Q | 退出当前应用 |
| Cmd+M | 最小化窗口 |
| Cmd+H | 隐藏当前应用 |
| Cmd+Option+H | 隐藏其他应用 |
| Cmd+Option+Esc | 强制退出应用 |
| F11 | 显示桌面 |
| Ctrl+↑ | 打开 Mission Control |
| Ctrl+↓ | 显示当前应用所有窗口 |

### 系统操作
| 快捷键 | 功能 |
|--------|------|
| Cmd+Space | 打开 Spotlight 搜索 |
| Cmd+Tab | 切换应用 |
| Cmd+, | 打开应用偏好设置 |
| Cmd+Option+Power | 睡眠 |
| Cmd+Ctrl+Q | 锁定屏幕 |
| Cmd+Shift+3 | 截取整个屏幕 |
| Cmd+Shift+4 | 截取选定区域 |
| Cmd+Shift+5 | 打开截屏工具栏 |

### 编辑操作
| 快捷键 | 功能 |
|--------|------|
| Cmd+C | 复制 |
| Cmd+X | 剪切 |
| Cmd+V | 粘贴 |
| Cmd+Z | 撤销 |
| Cmd+Shift+Z | 重做 |
| Cmd+A | 全选 |
| Cmd+F | 查找 |
| Cmd+G | 查找下一个 |
| Cmd+S | 保存 |
| Cmd+Shift+S | 另存为 |
| Cmd+P | 打印 |
| Cmd+N | 新建 |

### 浏览器常用
| 快捷键 | 功能 |
|--------|------|
| Cmd+T | 新建标签页 |
| Cmd+W | 关闭标签页 |
| Cmd+R | 刷新 |
| Cmd+Shift+R | 强制刷新 |
| Cmd+L | 选中地址栏 |
| Cmd+D | 添加书签 |
| Cmd+Option+←/→ | 切换标签页 |
"""


# ============================================================================
# Linux 快捷键（GNOME/KDE）
# ============================================================================

LINUX_SHORTCUTS = """
## Linux 系统快捷键参考（GNOME/KDE）

### 窗口管理
| 快捷键 | 功能 |
|--------|------|
| Alt+Tab | 切换窗口 |
| Alt+Esc | 直接切换窗口（无动画） |
| Super | 打开活动概览（GNOME）/ 启动器（KDE） |
| Super+D | 显示桌面 |
| Super+M | 消息托盘（GNOME） |
| Alt+F4 | 关闭窗口 |
| Alt+F10 | 最大化/还原窗口 |
| Alt+F9 | 最小化窗口 |
| Super+↑ | 最大化窗口 |
| Super+↓ | 还原/最小化窗口 |
| Super+←/→ | 窗口贴靠左/右 |

### 系统操作
| 快捷键 | 功能 |
|--------|------|
| Ctrl+Alt+T | 打开终端 |
| Alt+F2 | 运行命令 |
| Super+L | 锁定屏幕 |
| Ctrl+Alt+Del | 系统菜单/任务管理器 |
| PrtSc | 截图 |
| Alt+PrtSc | 截取当前窗口 |
| Ctrl+Alt+↑/↓/←/→ | 切换工作区（GNOME） |
| Ctrl+F1-F4 | 切换虚拟桌面（KDE） |

### 编辑操作
| 快捷键 | 功能 |
|--------|------|
| Ctrl+C | 复制 |
| Ctrl+X | 剪切 |
| Ctrl+V | 粘贴 |
| Ctrl+Z | 撤销 |
| Ctrl+Shift+Z | 重做 |
| Ctrl+A | 全选 |
| Ctrl+F | 查找 |
| Ctrl+H | 替换 |
| Ctrl+S | 保存 |
| Ctrl+P | 打印 |
| Ctrl+N | 新建 |
| Ctrl+O | 打开 |

### 终端常用
| 快捷键 | 功能 |
|--------|------|
| Ctrl+C | 终止当前命令 |
| Ctrl+Z | 挂起当前命令 |
| Ctrl+D | 关闭终端/EOF |
| Ctrl+L | 清屏 |
| Ctrl+A | 光标移到行首 |
| Ctrl+E | 光标移到行尾 |
| Ctrl+U | 清除光标前所有字符 |
| Ctrl+K | 清除光标后所有字符 |
| Tab | 自动补全 |
| ↑/↓ | 历史命令 |
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