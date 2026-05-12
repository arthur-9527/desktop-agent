# DeskAgent 详细执行计划 v2

## 项目概述

DeskAgent 是一个基于 LLM 的远程桌面智能 Agent。通过 AgentDesk HTTP API 控制远程桌面，结合无障碍树（Accessibility Tree）和桌面截图，实现自然语言驱动的桌面自动化操作。

### 两阶段架构

- **阶段一（分析阶段）**：收集无障碍树和截图 → 通用模型分析桌面状态 → 输出结构化分析结果和执行计划
- **阶段二（执行阶段）**：按计划逐步执行 → 每步截图 → 视觉模型验证 → 必要时引入 Accessibility 辅助决策

---

## 一、借鉴来源

| 来源 | 借鉴点 | 应用位置 |
|------|--------|---------|
| UI-TARS-desktop | CLI 工程架构、Agent 生命周期、Action Parser 设计 | `cli/`、`agent/phase2_executor.py`、`agent/action_parser.py` |
| Anthropic Computer Use | System Prompt 分层结构（Environment / ActionSpace / Rules / OutputFormat） | `prompts/base.py` |
| OmniParser (Microsoft) | 截图 → 结构化 UI 元素地图，补充无障碍树盲区（窗口内部元素） | `agent/phase1_analyzer.py` 输出 `interactive_map` |
| Open Interpreter | 预定义快捷键技能表，避免 LLM 凭空回忆快捷键 | `prompts/shortcuts.py` |
| Screen Agent (Screenpipe) | 动作前后像素 diff 检测，减少无效 LLM 调用 | `utils/image_diff.py`、`agent/phase2_executor.py` |
| AgentDesk | HTTP API、无障碍树、归一化坐标、网格截图 | `operator/agentdesk_operator.py` |

---

## 二、文件结构

```
deskagent/
├── main.py                          # CLI 入口
├── cli/
│   ├── __init__.py
│   └── commands.py                  # CLI 命令定义（参考 UI-TARS cli/commands.ts）
├── agent/
│   ├── __init__.py
│   ├── global_state.py              # 全局桌面状态结构体
│   ├── phase1_analyzer.py           # 阶段一：信息收集 + 通用模型分析
│   ├── phase2_executor.py           # 阶段二：逐步执行循环 + 模型路由
│   └── action_parser.py             # LLM 输出解析（Thought/Action → 结构化动作）
├── operator/
│   ├── __init__.py
│   ├── base.py                      # Operator 抽象基类
│   └── agentdesk_operator.py        # AgentDesk HTTP API 封装
├── prompts/
│   ├── __init__.py
│   ├── base.py                      # 分层 Prompt 模板函数（Environment/ActionSpace/Rules/OutputFormat）
│   ├── shortcuts.py                 # 平台快捷键技能表
│   ├── phase1_system.py             # 阶段一系统提示词
│   ├── phase1_user.py               # 阶段一用户消息模板
│   ├── phase2_execute.py            # 阶段二执行提示词（视觉模型用）
│   ├── phase2_check.py              # 阶段二完成确认提示词（视觉模型用）
│   └── phase2_decision.py           # 阶段二决策提示词（通用模型用，配合 Accessibility）
├── utils/
│   ├── __init__.py
│   ├── config.py                    # .env 配置加载
│   ├── tree_pruner.py               # 无障碍树裁剪算法
│   ├── tree_fetcher.py              # 无障碍树获取
│   ├── coordinate.py                # 坐标转换（截图/物理 ↔ API 0-1000 归一化）
│   └── image_diff.py                # 截图差异检测
└── memory/                          # Claude Code memory 目录（已存在）
```

---

## 三、全局桌面状态 (`agent/global_state.py`)

阶段一分析完成后填充，阶段二操作过程中按需更新。系统托盘、任务栏、桌面图标在单次会话中一般不变。

```python
@dataclass
class SystemTrayIcon:
    name: str                        # 如 "Clash Verge"
    description: str                 # 如 "Clash Verge 2.4.7 系统代理: off TUN: on"
    bounds: tuple[int,int,int,int]   # (x, y, width, height) 物理坐标
    index: int

@dataclass
class TaskbarIcon:
    name: str                        # 如 "Visual Studio Code"
    description: str                 # 如 "1 个运行窗口"
    bounds: tuple[int,int,int,int]
    position: str                    # "left" | "center" | "right"
    is_pinned: bool

@dataclass
class DesktopIcon:
    name: str                        # 如 "Google Chrome"
    bounds: tuple[int,int,int,int]
    row: int
    col: int

@dataclass
class MainWindow:
    title: str                       # 窗口标题
    program: str                     # 程序名（从无障碍树推断）
    bounds: tuple[int,int,int,int]
    is_focused: bool
    sub_window_count: int

@dataclass
class SystemState:
    input_method: str                # "中文" | "English"
    network_connected: bool
    network_name: str
    volume_level: int
    notification_count: int
    datetime: str

@dataclass
class InteractiveElement:
    """桌面交互地图中的元素（融合无障碍树 + 视觉识别）"""
    element: str                     # 元素描述，如 "开始按钮"
    type: str                        # button / edit / checkbox / ...
    bounds_screenshot: tuple | None  # 截图坐标
    bounds_physical: tuple | None    # 物理坐标
    source: str                      # "accessibility" | "vision"
    action_hint: str                 # 推荐操作方式

@dataclass
class DesktopState:
    platform: str                    # "windows" | "mac" | "linux"
    physical_resolution: tuple[int, int]
    screenshot_resolution: tuple[int, int]
    windows: list[MainWindow]
    taskbar_icons: list[TaskbarIcon]
    system_tray_icons: list[SystemTrayIcon]
    desktop_icons: list[DesktopIcon]
    system_state: SystemState
    interactive_map: list[InteractiveElement]  # 桌面交互地图
    raw_accessibility_tree: dict | None        # 原始树引用
```

---

## 四、阶段一：分析阶段 (`agent/phase1_analyzer.py`)

### 流程

```
1. GET /api/accessibility?maxDepth=10
   └── 提取平台和物理分辨率
   └── 识别根节点 children 中的四个区域：
       ├── [Pane] 系统托盘溢出窗口 → 完整保留
       ├── [Pane] 任务栏          → 完整保留
       ├── [Pane] Program Manager  → 完整保留
       └── [Window] 节点列表       → 裁剪后保留

2. 裁剪无障碍树 (tree_pruner.py)
   └── 系统托盘、任务栏、Program Manager：完整保留，不做任何裁剪
   └── [Window] 节点：仅保留有 bounds+name 或有意义 role 的分支

3. POST /api/screenshot {quality: 60, maxWidth: 1366, maxHeight: 768}
   └── 记录截图实际分辨率

4. 调用通用模型 (GENERAL_MODEL)
   └── 输入：截图 + 裁剪后无障碍树 + 系统信息 + 用户指令
   └── 输出：结构化 JSON（桌面分析 + 执行计划 + 交互地图）

5. 填充 DesktopState 全局结构体
   └── plan 步骤列表传递给阶段二
```

### 调用模型：始终使用通用模型 (qwopus-35b)

### 阶段一 LLM 输出 Schema

```json
{
  "windows": [
    {
      "title": "...",
      "program": "...",
      "bounds": {"x": 0, "y": 0, "width": 1920, "height": 1080},
      "is_focused": true,
      "sub_window_count": 3,
      "child_windows": ["..."]
    }
  ],
  "taskbar_icons": [
    {
      "name": "Visual Studio Code",
      "description": "1 个运行窗口",
      "position": "center",
      "is_pinned": true
    }
  ],
  "system_tray_icons": [
    {
      "name": "Clash Verge",
      "description": "系统代理: off",
      "index": 3
    }
  ],
  "desktop_icons": [
    {
      "name": "Google Chrome",
      "position": {"x": 0, "y": 493}
    }
  ],
  "system_state": {
    "input_method": "中文",
    "network_connected": false,
    "network_name": "SakuraiTunnel",
    "volume_level": 36,
    "notification_count": 2,
    "datetime": "2026-05-12 10:00"
  },
  "interactive_map": [
    {
      "element": "开始按钮",
      "type": "button",
      "bounds_screenshot": {"x": 501, "y": 690, "width": 28, "height": 30},
      "bounds_physical": {"x": 1002, "y": 1380, "width": 56, "height": 60},
      "source": "accessibility",
      "action_hint": "hotkey:leftwin 或 click:501,690"
    }
  ],
  "plan": [
    {
      "step": 1,
      "action": "hotkey",
      "params": {"keys": ["leftwin"]},
      "target_description": "打开开始菜单",
      "reason": "Win 键是最快捷的启动方式"
    },
    {
      "step": 2,
      "action": "type",
      "params": {"text": "Chrome\\n"},
      "target_description": "搜索并启动 Chrome",
      "reason": "在开始菜单搜索框输入并回车"
    }
  ]
}
```

关键设计：plan 只包含高层步骤，不预填坐标。坐标在阶段二执行时根据截图/Accessibility 即时确定。

---

## 五、无障碍树裁剪算法 (`utils/tree_pruner.py`)

### 规则

| 节点类型 | 处理方式 |
|---------|---------|
| 系统托盘 (SystemTray) | **完整保留**，不做任何裁剪 |
| 任务栏 (Taskbar) | **完整保留**，不做任何裁剪 |
| Program Manager | **完整保留**，不做任何裁剪 |
| [Window] 节点 | **逐层裁剪**，仅保留有实际意义的分支 |

### Window 节点的保留条件

```python
def _has_meaningful_content(node: dict) -> bool:
    role = node.get("role", "")
    name = node.get("name", "").strip()
    bounds = node.get("bounds", {})

    # 有坐标 + 有名称 → 保留
    if bounds and name:
        return True

    # 有坐标 + 有意义 role → 保留
    MEANINGFUL_ROLES = {
        "Button", "Edit", "Text", "CheckBox", "ComboBox",
        "ListItem", "TabItem", "Hyperlink", "MenuItem",
        "Image", "Document", "ToolBar", "Tab", "List"
    }
    if bounds and role in MEANINGFUL_ROLES:
        return True

    # 有 children → 可能有深层有效节点，保留骨架
    if node.get("children"):
        return True

    return False
```

预期将 ~42000 节点裁剪到 ~200-500 节点。

---

## 六、阶段二：执行阶段 (`agent/phase2_executor.py`)

### 模型路由规则

```
                     ┌─────────────┐
                     │ 执行一个step  │
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │   截图       │
                     └──────┬──────┘
                            │
                     ┌──────▼──────────┐
                     │ 像素diff > 阈值? │ ◄── 来自 Screen Agent 借鉴
                     └──────┬──────────┘
                            │
                   ┌────────┼────────┐
                  否        │        是
                   │  ┌─────▼──────┐
             直接重试 │ 视觉模型判断 │
                   │  │步骤是否完成 │
                   │  └─────┬──────┘
                   │        │
                   │  ┌─────┼──────────┐
                   │ 完成 未完成   无法判断
                   │  │    │         │
                   │  │    │    ┌────┴──────────┐
                   │  │    │    │ 需要哪种辅助？  │
                   │  │    │    └────┬──────────┘
                   │  │    │         │
                   │  │    │   ┌─────┼──────────┐
                   │  │    │   │               │
                   │  │    │ 窗口内     桌面结构/状态
                   │  │    │ 坐标定位     判断
                   │  │    │   │               │
                   │  │    │ 带网格      Accessibility
                   │  │    │ 截图        + 通用模型
                   │  │    │ + 视觉模型  决策
                   │  │    │
              ┌────▼──┐    │
              │通用模型│    │
              │最终确认│    │
              └────┬──┘    │
                   │       │
                 退出   继续循环
```

**模型调用路由总结：**

| 场景 | 模型 | 说明 |
|------|------|------|
| 阶段一分析 | 通用模型 (qwopus-35b) | 需要强推理 + JSON 输出 |
| 阶段二步骤判断（仅截图） | 视觉模型 (ui-tars) | 专为 GUI 视觉定位优化 |
| 阶段二需要窗口内坐标 | 视觉模型 (ui-tars) | 带网格截图定位 |
| 阶段二需要桌面结构/状态决策 | 通用模型 (qwopus-35b) | 配合 Accessibility Tree |
| 阶段二最终确认 | 通用模型 (qwopus-35b) | 综合判断能力更强 |

### 核心循环逻辑

```python
async def execute_plan(plan: list[dict], state: DesktopState):
    prev_screenshot = None

    for step in plan:
        step_done = False
        retry_count = 0

        while not step_done and retry_count < MAX_RETRIES:
            # 1. 执行 action
            await operator.execute(step)
            await asyncio.sleep(LOOP_INTERVAL_MS / 1000)

            # 2. 截图 + 像素 diff 快速检测
            current = await operator.screenshot(quality=20, max_width=1024, max_height=768)
            if prev_screenshot and image_diff(prev_screenshot, current) < THRESHOLD:
                retry_count += 1
                continue  # 画面无变化，直接重试，不消耗 LLM token

            prev_screenshot = current

            # 3. 视觉模型判断
            response = await vision_model.chat(
                system=PHASE2_CHECK_PROMPT,
                user=f"步骤目标: {step['target_description']}\n判断是否完成。",
                images=[current]
            )

            if response["status"] == "completed":
                step_done = True

            elif response["status"] == "in_progress":
                step = response["next_action"]
                retry_count = 0

            elif response["status"] == "need_more_info":
                step = await _handle_need_more_info(
                    response, step, current, state
                )

            retry_count += 1

        if not step_done:
            logger.warning(f"步骤 {step} 超过最大重试次数，跳过")

    # 4. 最终确认
    final = await operator.screenshot()
    result = await general_model.chat(
        system="判断用户指令是否已完成。回答 yes/no/partial。",
        images=[final]
    )
```

---

## 七、Operator 接口 (`operator/agentdesk_operator.py`)

封装 AgentDesk HTTP API，所有坐标使用 0-1000 归一化坐标。

```python
class AgentDeskOperator:
    # 截图
    async def screenshot(self, quality=60, max_width=1366, max_height=768,
                         show_grid=False) -> ScreenshotResult: ...

    # 屏幕信息
    async def get_screen_info(self) -> ScreenInfo: ...

    # 无障碍树
    async def get_accessibility(self, max_depth=10) -> dict: ...
    async def get_focused_element(self) -> dict: ...

    # 鼠标 (x, y 均为 0-1000 归一化坐标)
    async def mouse_move(self, x: int, y: int) -> None: ...
    async def mouse_click(self, x: int = None, y: int = None,
                          button="left", double=False) -> None: ...
    async def mouse_scroll(self, direction: str, amount: int = 1) -> None: ...
    async def get_mouse_position(self) -> tuple[int, int]: ...

    # 键盘
    async def keyboard_type(self, text: str) -> None: ...
    async def keyboard_hotkey(self, keys: list[str]) -> None: ...
```

---

## 八、坐标换算 (`utils/coordinate.py`)

```python
def screenshot_to_api(sx: int, sy: int, sw: int, sh: int) -> tuple[int, int]:
    """截图坐标 → API 归一化坐标 (0-1000)"""
    return (sx / sw * 1000, sy / sh * 1000)

def accessibility_to_api(ax: int, ay: int, pw: int, ph: int) -> tuple[int, int]:
    """物理坐标 → API 归一化坐标 (0-1000)"""
    return (ax / pw * 1000, ay / ph * 1000)
```

---

## 九、Prompt 设计

### 分层结构（借鉴 Anthropic Computer Use）

```
<ENVIRONMENT>    → 告诉模型它面对什么环境（平台、分辨率）
<ACTION_SPACE>   → 所有可用动作和参数格式
<SHORTCUT_TABLE> → 常用快捷键速查表
<RULES>          → 操作约束和最佳实践
<OUTPUT_FORMAT>  → 严格的输出格式
```

### Prompt 文件分工

| 文件 | 用途 | 调用模型 |
|------|------|---------|
| `base.py` | 分层 prompt 模板函数 | 共享 |
| `shortcuts.py` | Windows 快捷键技能表 | 注入到各 prompt |
| `phase1_system.py` | 阶段一分析专家的角色定义 + JSON 输出格式 | 通用模型 |
| `phase1_user.py` | 拼装截图 + 无障碍树 + 用户指令 | 通用模型 |
| `phase2_execute.py` | 判断状态、给出下一步 action（含坐标） | 视觉模型 |
| `phase2_check.py` | 判断某步骤是否已完成（二分类） | 视觉模型 |
| `phase2_decision.py` | 配合 Accessibility 做结构化决策 | 通用模型 |

### 快捷键技能表示例（`prompts/shortcuts.py`）

```python
WINDOWS_SHORTCUTS = [
    {"action": "显示桌面",        "keys": ["LeftWin", "D"]},
    {"action": "打开开始菜单",     "keys": ["LeftWin"]},
    {"action": "打开运行对话框",   "keys": ["LeftWin", "R"]},
    {"action": "切换窗口",        "keys": ["AltLeft", "Tab"]},
    {"action": "关闭当前窗口",     "keys": ["AltLeft", "F4"]},
    {"action": "打开任务管理器",   "keys": ["ControlLeft", "ShiftLeft", "Escape"]},
    {"action": "打开文件管理器",   "keys": ["LeftWin", "E"]},
    {"action": "打开搜索",        "keys": ["LeftWin", "S"]},
    {"action": "打开设置",        "keys": ["LeftWin", "I"]},
    {"action": "锁定屏幕",        "keys": ["LeftWin", "L"]},
    {"action": "截图工具",        "keys": ["LeftWin", "ShiftLeft", "S"]},
    {"action": "最小化窗口",      "keys": ["LeftWin", "ArrowDown"]},
    {"action": "最大化窗口",      "keys": ["LeftWin", "ArrowUp"]},
    {"action": "窗口贴左半屏",     "keys": ["LeftWin", "ArrowLeft"]},
    {"action": "窗口贴右半屏",     "keys": ["LeftWin", "ArrowRight"]},
    {"action": "全选",            "keys": ["ControlLeft", "A"]},
    {"action": "复制",            "keys": ["ControlLeft", "C"]},
    {"action": "粘贴",            "keys": ["ControlLeft", "V"]},
    {"action": "剪切",            "keys": ["ControlLeft", "X"]},
    {"action": "撤销",            "keys": ["ControlLeft", "Z"]},
    {"action": "保存",            "keys": ["ControlLeft", "S"]},
    {"action": "回车确认",         "keys": ["Enter"]},
    {"action": "取消/退出",        "keys": ["Escape"]},
]
```

### Action 空间定义

```python
ACTION_SPACE = """
click(point='<point>x y</point>')          # 鼠标左键点击截图坐标
left_double(point='<point>x y</point>')     # 双击
right_single(point='<point>x y</point>')    # 右键点击
drag(start_point='<point>x1 y1</point>', end_point='<point>x2 y2</point>')
hotkey(key='leftwin r')                     # 组合键，小写空格分隔
type(content='xxx')                         # 输入文本，\\n 表示回车
scroll(point='<point>x y</point>', direction='up|down')
wait()                                      # 等待 2 秒后观察变化
finished(content='xxx')                     # 任务完成，附带回执
"""
```

---

## 十、截图差异检测 (`utils/image_diff.py`)

借鉴 Screen Agent 的思路，在阶段二每步操作后先做像素级 diff，无变化则直接重试，避免无效 LLM 调用。

```python
def image_diff(before: bytes, after: bytes, threshold=0.01) -> float:
    """
    比较两张截图的结构相似度。
    返回 0.0 ~ 1.0，值越小表示差异越大。
    使用 SSIM 或简化的像素直方图对比。
    """
    ...

# 使用
if image_diff(prev, current) < 0.95:
    # 差异不够大，动作可能无效 → 直接重试
    return ActionResult.NO_CHANGE
```

---

## 十一、与参考项目的对应关系

| 参考项目 | 借鉴点 | 代码位置 |
|---------|--------|---------|
| UI-TARS-desktop | CLI 架构（cac/commander 模式） | `cli/commands.py` |
| UI-TARS-desktop | Agent 生命周期（beforeLoop → execute → afterLoop → screenshot） | `agent/phase2_executor.py` |
| UI-TARS-desktop | Action Parser（Thought/Action 正则解析 + 自定义 parser 注册） | `agent/action_parser.py` |
| UI-TARS-desktop | Prompt 独立文件管理 | `prompts/` |
| UI-TARS-desktop | Operator 抽象（nut-js/adb/browser） | `operator/base.py` |
| Anthropic Computer Use | Prompt 分层结构 | `prompts/base.py` |
| OmniParser | 截图 → 可交互元素地图 | `agent/phase1_analyzer.py` 的 `interactive_map` |
| Open Interpreter | 快捷键技能表 | `prompts/shortcuts.py` |
| Screen Agent | 动作前后像素 diff | `utils/image_diff.py` |
| AgentDesk | HTTP API、无障碍树、归一化坐标、网格截图 | `operator/agentdesk_operator.py` |

---

## 十二、关键设计决策

1. **阶段一和阶段二之间只传递 plan 步骤列表**。系统托盘/任务栏/桌面图标等信息存入 `DesktopState` 全局结构体，操作变化后更新。
2. **plan 不预填坐标**。坐标由阶段二执行时根据截图或 Accessibility 即时确定。
3. **Linux 平台无障碍不支持**。Linux 远程桌面阶段一只能依赖纯视觉分析。
4. **所有 prompt 独立存放于 `prompts/` 目录**，不做硬编码。
5. **像素 diff 不是强依赖**。如果 SSIM 计算过重，可先用缩略图像素直方图快速比较，甚至可以跳过此优化直接调 LLM。

---

## 十三、开发顺序

| 序号 | 模块 | 产出 |
|------|------|------|
| 1 | `utils/config.py` | .env 配置加载 |
| 2 | `operator/agentdesk_operator.py` | AgentDesk HTTP API 完整封装 |
| 3 | `utils/coordinate.py` | 坐标转换函数 |
| 4 | `utils/tree_pruner.py` | 无障碍树裁剪 |
| 5 | `utils/image_diff.py` | 截图差异检测 |
| 6 | `prompts/base.py` + `prompts/shortcuts.py` | Prompt 模板和快捷键表 |
| 7 | `prompts/phase1_*.py` | 阶段一提示词 |
| 8 | `agent/global_state.py` | 全局桌面状态结构体 |
| 9 | `agent/phase1_analyzer.py` | 阶段一完整流程 |
| 10 | `agent/action_parser.py` | LLM 输出解析 |
| 11 | `prompts/phase2_*.py` | 阶段二提示词 |
| 12 | `agent/phase2_executor.py` | 阶段二执行循环 + 模型路由 |
| 13 | `cli/commands.py` + `main.py` | CLI 入口 |
