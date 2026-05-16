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
#### [聚焦] Visual Studio Code
状态: 可见
关键元素 (4个):
  - [Button] Minimize (932, 16)
  - [Button] Maximize (955, 16)
  - [Button] Close (977, 16)

#### Google Chrome
状态: 可见
文本信息 (3个):
  - [Text] 搜索或输入网址 (400, 50)
  - [Text] 新建标签页 (200, 100)
  - [Text] 书签 (600, 100)
关键元素 (8个):
  - [Button] 前进 (350, 50)
  - [Button] 刷新 (380, 50)
  - [Button] 后退 (320, 50)
  - [Edit] 地址栏 (400, 50)
  - [Button] 主页 (410, 50)

#### [后台] 计算器
状态: 最小化
```

## 关键元素提取规则

全局信息表通过 `_extract_interactive_children` 方法提取窗口内的关键元素，提取规则如下：

1. **角色过滤**：只提取以下角色类型的元素：
   - `Button` - 按钮
   - `Edit` - 输入框
   - `CheckBox` - 复选框
   - `RadioButton` - 单选按钮
   - `ComboBox` - 下拉框
   - `MenuItem` - 菜单项
   - `TabItem` - 标签项
   - `ListItem` - 列表项
   - `Hyperlink` - 超链接
   - `Link` - 链接
   - `Text` - 文本

2. **可见性过滤**：只提取可见的元素（坐标不在负数区域）

3. **名称过滤**：只提取有名称的元素

4. **深度限制**：只提取深度 ≤ 6 的元素

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
    is_focused: bool      # 是否聚焦（当前键盘焦点所在窗口）
    is_visible: bool
    normalized_x: int
    normalized_y: int
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
```

### 窗口可见性判断

窗口坐标为负数（如 `-31991`）表示最小化或隐藏：

```python
def _is_visible(self, bounds: dict) -> bool:
    x = bounds.get("x", 0)
    y = bounds.get("y", 0)
    return x >= -100 and y >= -100
```

### 窗口状态判断

窗口有两种状态属性：

- **可见 (is_visible)**: 窗口在桌面上展开（非最小化）
- **聚焦 (is_focused)**: 当前键盘焦点所在的窗口，只有一个

通过 `GET /api/accessibility/focused` 获取焦点元素，然后判断其所属窗口：

```python
# 聚焦状态：焦点元素在窗口边界内
if is_visible and focused_element:
    focused_bounds = focused_element.get("bounds", {})
    if wx <= focused_x <= wx + ww and wy <= focused_y <= wy + wh:
        is_focused = True
```

信息表中显示格式：
- `[聚焦]` - 当前键盘焦点所在的窗口
- 无标签 - 展开但未聚焦的窗口
- `[后台]` - 最小化的窗口

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