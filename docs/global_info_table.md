# 全局动态信息表

## 概述

全局动态信息表是将无障碍树压缩为结构化文本信息，提供给 LLM 作为上下文参考。相比直接传入完整无障碍树，信息表具有以下优势：

| 维度 | 完整无障碍树 | 全局动态信息表 |
|------|-------------|---------------|
| Token 消耗 | 高（数万节点） | 低（几十行文本） |
| 信息密度 | 低（大量无用节点） | 高（只保留关键元素） |
| 可读性 | 差（需解析树结构） | 好（分类清晰） |
| AI 理解难度 | 高 | 低 |

## 信息表结构

```yaml
## 全局动态信息表

### 系统环境
- 操作系统: Windows
- 屏幕分辨率: 2560x1440
- 鼠标位置: (512, 384) [归一化坐标]

### 桌面图标
| 名称 | 坐标 |
|------|------|
| 回收站 | (18, 30) |
| Google Chrome | (100, 200) |

### 任务栏
| 按钮 | 坐标 |
|------|------|
| 开始 | (391, 957) |
| 搜索 | (413, 957) |
| 文件资源管理器 | (545, 957) |

### 系统托盘
| 应用 | 坐标 | 状态 |
|------|------|------|
| 输入法 | (905, 957) | 中文模式 |
| 网络 | (922, 957) | 已连接 |
| 音量 | (935, 957) | 36% |

### 当前窗口
#### [激活] Visual Studio Code
状态: 可见
关键元素:
  - [Button] Minimize (932, 16)
  - [Button] Close (977, 16)
  - [Edit] 文件搜索 (400, 200)

#### [后台] Chrome
状态: 最小化
```

## 坐标归一化规则

所有坐标使用 **0-1000 归一化坐标**，基于元素中心点计算：

```python
# 物理分辨率从无障碍树根节点获取
screen_width = root.bounds.width   # 如 2560
screen_height = root.bounds.height # 如 1440

# 元素中心点
center_x = bounds.x + bounds.width / 2
center_y = bounds.y + bounds.height / 2

# 归一化
normalized_x = int(center_x / screen_width * 1000)
normalized_y = int(center_y / screen_height * 1000)
```

## 更新策略

全局动态信息表在以下时机更新：

1. **任务开始时** - 初始化信息表
2. **每次操作后** - 截图前更新信息表

更新过程是纯代码逻辑，**不经过 LLM**，处理速度极快（< 300ms）。

## API 使用

### 直接使用解析器

```python
from src.accessibility_parser import create_info_table

# 获取无障碍树
tree = await client.accessibility_tree(max_depth=10)
mouse_pos = await client.mouse_position()
focused = await client.accessibility_focused()

# 生成信息表
info_table = create_info_table(tree, mouse_pos, focused)
print(info_table)
```

### 使用解析器类

```python
from src.accessibility_parser import AccessibilityParser

parser = AccessibilityParser()
info = parser.parse(tree, mouse_pos, focused)

# 访问结构化数据
print(f"屏幕分辨率: {info.screen_width}x{info.screen_height}")
print(f"桌面图标数量: {len(info.desktop_icons)}")
print(f"窗口数量: {len(info.windows)}")

# 格式化为文本
text = parser.format_info_table(info)
```

## 实现细节

### 数据结构

```python
@dataclass
class ElementInfo:
    """元素信息"""
    name: str
    role: str
    normalized_x: int
    normalized_y: int
    bounds: dict
    extra: str  # 额外信息

@dataclass
class WindowInfo:
    """窗口信息"""
    name: str
    is_active: bool
    is_visible: bool
    normalized_x: int
    normalized_y: int
    children: list[ElementInfo]

@dataclass
class GlobalInfo:
    """全局动态信息"""
    os: str
    screen_width: int
    screen_height: int
    mouse_x: int
    mouse_y: int
    desktop_icons: list[ElementInfo]
    taskbar_items: list[ElementInfo]
    tray_items: list[ElementInfo]
    windows: list[WindowInfo]
```

### 窗口可见性判断

窗口坐标为负数（如 `-31991`）表示最小化或隐藏：

```python
def _is_visible(self, bounds: dict) -> bool:
    x = bounds.get("x", 0)
    y = bounds.get("y", 0)
    return x >= -100 and y >= -100
```

### 激活窗口判断

通过 `GET /api/accessibility/focused` 获取焦点元素，然后反推所属窗口：

```python
# TODO: 实现焦点元素到窗口的映射
# 当前简化：第一个可见窗口视为激活窗口
```

## 与 Agent Loop 集成

```python
# agent_loop.py
async def run(self, task: str):
    # 初始获取
    info_table = await self._get_global_info_table()
    system_prompt = build_system_prompt(task) + f"\n\n{info_table}"

    for step in range(self.max_steps):
        # 截图
        screenshot = await self.client.screenshot(show_grid=True)

        # 更新信息表
        info_table = await self._get_global_info_table()

        # 构建消息
        user_text = f"继续执行任务。\n\n{info_table}"
        # ... 发送给 LLM
```

## 性能

- 无障碍树获取：~50-200ms（取决于系统）
- Python 解析遍历：~10-50ms（4万节点）
- 总耗时：< 300ms