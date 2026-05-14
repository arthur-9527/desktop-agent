# DeskAgent 项目计划 v2

## 项目概述

Linux 客户端调用远程 Windows 上的 AgentDesk 服务 + 本地部署的 UI-TARS 1.5 模型，实现端到端桌面自动化。

### 核心思路

**不搭多层架构，直接以 UI-TARS 1.5 为核心做单模型驱动。** UI-TARS 1.5 已经在 OSWorld 上达到 42.5%（超过 OpenAI CUA 的 36.4% 和 Claude 3.7 的 28%），ScreenSpot-V2 Grounding 准确率 94.2%。它的能力覆盖了视觉理解、任务规划、元素定位三个环节，不再需要拆分。

### 系统架构

```
┌──────────────────────────────┐     ┌──────────────────────────────┐
│   Linux 客户端                 │     │   Windows 远程设备              │
│                              │     │                              │
│  ┌────────────────────────┐ │     │  ┌────────────────────────┐  │
│  │  Agent Loop (Python)    │ │ HTTP│  │  AgentDesk (Electron)   │  │
│  │                        │ │:9877│  │                        │  │
│  │  1. 截图 ←─────────────┼─┼────→│  │  POST /api/screenshot  │  │
│  │  2. UI-TARS 1.5 推理   │ │     │  │  POST /api/mouse       │  │
│  │  3. 解析动作            │ │     │  │  POST /api/keyboard    │  │
│  │  4. 执行动作 ──────────┼─┼────→│  │  GET /api/accessibility │  │
│  │  5. 判断完成 → 循环     │ │     │  └────────────────────────┘  │
│  └────────────────────────┘ │     │                              │
│           │                 │     │                              │
│           ▼                 │     │                              │
│  ┌────────────────────────┐ │     │                              │
│  │  UI-TARS 1.5-7B (vLLM) │ │     │                              │
│  │  localhost:8000/v1      │ │     │                              │
│  └────────────────────────┘ │     │                              │
└──────────────────────────────┘     └──────────────────────────────┘
```

### 为什么选这个架构

| 对比维度 | 多层架构（之前的设计） | UI-TARS 单模型 |
|----------|----------------------|----------------|
| 组件数 | 7（client, state, parser, executor, enricher, atomic_ops, context） | 2（agent loop, AgentDesk client） |
| 模型调用/步 | 2-3 次 | 1 次 |
| Grounding 准确率 | 依赖无障碍树覆盖率 | 94.2%（ScreenSpot-V2） |
| 无障碍树不可用时的表现 | 断崖式下降 | 几乎不受影响 |
| 坐标换算 | 自己维护多层转换 | UI-TARS 内置 scaling factor |
| 实现量 | ~2000 行 | ~300 行 |

### 技术栈

| 层 | 技术 |
|----|------|
| Agent Loop | Python 3.10+ |
| 视觉模型 | UI-TARS 1.5-7B (vLLM 部署, OpenAI 兼容 API) |
| 远程控制 | AgentDesk HTTP API (:9877) |
| 动作解析 | `ui-tars` pip 包 (`parse_action_to_structure_output`) |
| 图像处理 | Pillow（截图 resizing，可选） |

---

## 目录结构

```
/home/test/deskagent/
├── src/
│   ├── __init__.py
│   ├── agent_loop.py          # 核心 Agent Loop
│   ├── agentdesk_client.py    # AgentDesk HTTP API 封装
│   ├── action_executor.py     # 动作翻译（模型输出 → AgentDesk API）
│   ├── prompts.py             # UI-TARS COMPUTER_USE prompt 模板
│   └── config.py              # 配置管理（读取 .env）
├── .env                       # 环境变量
├── .gitignore
├── requirements.txt
└── main.py                    # 入口
```

---

## 阶段一：AgentDesk HTTP Client

### 1.1 封装 API 调用

```python
# src/agentdesk_client.py

import httpx
from typing import Optional

class AgentDeskClient:
    """AgentDesk HTTP API 客户端"""

    def __init__(self, host: str, port: int = 9877, token: str = "admin123"):
        self.base_url = f"http://{host}:{port}"
        self.auth = {"Authorization": f"Bearer {token}"}
        self._client = httpx.AsyncClient(timeout=10)

    # ---- 截图 ----

    async def screenshot(self, quality: int = 60,
                         max_width: int = 1366, max_height: int = 768,
                         show_grid: bool = False) -> dict:
        """截图，返回 {"base64": ..., "width": ..., "height": ...}"""
        resp = await self._client.post(
            f"{self.base_url}/api/screenshot",
            json={"quality": quality, "maxWidth": max_width,
                  "maxHeight": max_height, "showGrid": show_grid},
            headers=self.auth,
        )
        data = resp.json()
        return {"base64": data["data"], "width": data["width"], "height": data["height"]}

    # ---- 屏幕信息 ----

    async def screen_info(self) -> dict:
        resp = await self._client.get(f"{self.base_url}/api/screen/info", headers=self.auth)
        return resp.json()  # {"width": 1920, "height": 1080, "scaleFactor": 1.5}

    # ---- 鼠标 ----

    async def mouse_move(self, x: int, y: int):
        """x, y: 0-1000 归一化坐标"""
        await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "move", "x": x, "y": y},
            headers=self.auth,
        )

    async def mouse_click(self, button: str = "left", x: int = None, y: int = None):
        action_map = {"left": "left_click", "right": "right_click", "double": "double_click"}
        body = {"action": action_map[button]}
        if x is not None and y is not None:
            body["x"], body["y"] = x, y
        await self._client.post(
            f"{self.base_url}/api/mouse",
            json=body, headers=self.auth,
        )

    async def mouse_down(self):
        await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "press_left"},
            headers=self.auth,
        )

    async def mouse_up(self):
        await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "release_left"},
            headers=self.auth,
        )

    async def mouse_drag(self, x: int, y: int):
        """拖拽到目标位置（需先 mouse_down）"""
        await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "drag", "x": x, "y": y},
            headers=self.auth,
        )

    async def mouse_scroll(self, direction: str, amount: int = 1):
        await self._client.post(
            f"{self.base_url}/api/mouse",
            json={"action": "scroll", "direction": direction, "amount": amount},
            headers=self.auth,
        )

    # ---- 键盘 ----

    async def keyboard_type(self, text: str):
        await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "type", "text": text},
            headers=self.auth,
        )

    async def keyboard_hotkey(self, *keys: str):
        """发送快捷键。先 press 再 release。"""
        await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "press", "keys": list(keys)},
            headers=self.auth,
        )
        await self._client.post(
            f"{self.base_url}/api/keyboard",
            json={"action": "release", "keys": list(keys)},
            headers=self.auth,
        )

    # ---- 无障碍树（可选） ----

    async def accessibility_tree(self, max_depth: int = 5):
        resp = await self._client.get(
            f"{self.base_url}/api/accessibility",
            params={"maxDepth": max_depth},
            headers=self.auth,
        )
        return resp.json()

    async def health_check(self) -> bool:
        resp = await self._client.get(f"{self.base_url}/api/health")
        return resp.json().get("status") == "ok"
```

### 1.2 requirements.txt

```
httpx>=0.25.0
openai>=1.0.0           # OpenAI 兼容 API 客户端（调 UI-TARS）
ui-tars>=0.5.1          # 官方动作解析包 + prompt 模板
python-dotenv>=1.0.0
Pillow>=10.0.0
```

---

## 阶段二：动作解析与执行

### 2.1 坐标系统（关键）

**UI-TARS 1.5 直接输出 0-1000 归一化坐标**，与 AgentDesk 坐标系一致，无需换算。

验证结果：模型输出 `click(start_box='(500, 500)')` → `parse_action_to_structure_output(factor=1, model_type='UI-TARS-1.5-7B')` → `[500.0, 500.0]`，可直接发给 AgentDesk。

```
UI-TARS 输出 0-1000 归一化坐标
   ↓  无需转换，直接透传
AgentDesk 0-1000 归一化坐标
   ↓  AgentDesk 内部: x = screenWidth * scaleFactor * (nx / 1000)
物理像素执行
```

两种特殊情况的换算：

| 数据来源 | 坐标空间 | 换算公式 |
|---------|---------|---------|
| UI-TARS 输出 | 0-1000 归一化 | 直接使用，无需转换 |
| 无障碍树 bounds | 物理像素（树根 `Pane` 的 bounds 宽高） | `px * 1000 / physical_w` |
| 截图手动定位 | 截图像素 | `px * 1000 / SCREENSHOT_MAX_WIDTH` |

**物理分辨率从哪来？** 无障碍树根节点的 bounds 宽高才是真正的物理分辨率（如 `桌面 1 @(2560x1440)`）。`GET /api/screen/info` 返回的是 Windows 逻辑分辨率，不用于坐标换算。

```python
# src/action_executor.py

from ui_tars.action_parser import parse_action_to_structure_output

class ActionExecutor:
    def __init__(self, client: AgentDeskClient):
        self.client = client

    def parse(self, model_output: str) -> dict:
        """UI-TARS 输出 0-1000 归一化坐标，factor=1 直接透传"""
        return parse_action_to_structure_output(
            model_output,
            factor=1,
            origin_resized_height=768,
            origin_resized_width=1366,
            model_type="UI-TARS-1.5-7B",
        )

    async def execute(self, parsed: dict):
        """执行单个动作。坐标已是 0-1000 归一化，直接给 AgentDesk。"""
        action_type = parsed["action_type"]
        inputs = parsed.get("action_inputs", {})

        if action_type == "click":
            x, y = self._get_coords(inputs)
            await self.client.mouse_click(x=int(x), y=int(y))

        elif action_type == "left_double":
            x, y = self._get_coords(inputs)
            await self.client.mouse_click(button="double", x=int(x), y=int(y))

        elif action_type == "right_single":
            x, y = self._get_coords(inputs)
            await self.client.mouse_click(button="right", x=int(x), y=int(y))

        elif action_type == "drag":
            x1, y1 = self._get_coords(inputs, key="start_box")
            x2, y2 = self._get_coords(inputs, key="end_box")
            # press_left → drag → release_left（三步）
            await self.client.mouse_down()
            await self.client.mouse_drag(int(x2), int(y2))
            await self.client.mouse_up()

        elif action_type == "scroll":
            await self.client.mouse_scroll(
                direction=inputs.get("direction", "down"),
                amount=1,
            )

        elif action_type == "type":
            await self.client.keyboard_type(inputs["content"])

        elif action_type == "hotkey":
            keys = inputs["key"].split()  # 官方格式: "ctrl c"
            await self.client.keyboard_hotkey(*keys)

        elif action_type == "wait":
            import asyncio
            await asyncio.sleep(5)

    def _get_coords(self, inputs: dict, key: str = "start_box") -> tuple[float, float]:
        """从解析后的 action_inputs 提取坐标（已是 0-1000 归一化）"""
        coords_str = inputs.get(key, "[500, 500]")
        nums = [float(x) for x in coords_str.strip("[]").split(",")]
        return (nums[0], nums[1])
```
```

### 2.2 Prompt 模板

直接使用 `ui-tars` 官方包的 COMPUTER_USE_DOUBAO 模板，不自己造。

```python
# src/prompts.py
from ui_tars.prompt import COMPUTER_USE_DOUBAO

# 官方 prompt 已定义完整的 action space：
#   click(point='<point>x1 y1</point>')
#   left_double(point='<point>x1 y1</point>')
#   right_single(point='<point>x1 y1</point>')
#   drag(start_point='<point>x1 y1</point>', end_point='<point>x2 y2</point>')
#   hotkey(key='ctrl c')
#   type(content='xxx')          # 换行用 \n，提交表单在末尾加 \n
#   scroll(point='<point>x1 y1</point>', direction='down or up or right or left')
#   wait()                       # 等待 5s 后截图检查变化
#   finished(content='xxx')
#
# prompt 中 {language} 和 {instruction} 为占位符，运行时替换。
```

与模型训练时的 prompt 完全对齐，避免自造格式导致解析偏差。

---

## 阶段三：Agent Loop

### 3.1 核心循环

```python
# src/agent_loop.py

import asyncio
from openai import AsyncOpenAI
from ui_tars.prompt import COMPUTER_USE_DOUBAO
from .agentdesk_client import AgentDeskClient
from .action_executor import ActionExecutor

class DeskAgent:
    """UI-TARS 驱动的桌面 Agent"""

    def __init__(self,
                 agentdesk: AgentDeskClient,
                 model: AsyncOpenAI,
                 model_name: str = "UI-TARS-1.5-7B",
                 max_steps: int = 25):
        self.client = agentdesk
        self.model = model
        self.model_name = model_name
        self.max_steps = max_steps
        self.action_executor = None   # 获取物理屏幕尺寸后初始化

    async def run(self, task: str) -> dict:
        """执行任务，返回 {"success": bool, "message": str, "steps": int}"""

        self.action_executor = ActionExecutor(self.client)
        tree_hint = await self._get_accessibility_hint()

        # 构建 system prompt（替换官方模板占位符）
        system_prompt = COMPUTER_USE_DOUBAO.format(
            language="Chinese",
            instruction=task
        )
        if tree_hint:
            system_prompt += f"\n\n[无障碍树参考]\n{tree_hint}"

        messages = [{"role": "system", "content": system_prompt}]

        for step in range(self.max_steps):
            # 1. 截图（带网格，帮助 UI-TARS 精确 Grounding）
            screenshot = await self.client.screenshot(show_grid=True)

            # 2. 调 UI-TARS
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{screenshot['base64']}"
                    }},
                    {"type": "text", "text": "继续执行任务。" if step > 0 else ""},
                ]
            })

            response = await self.model.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=1024,
            )

            raw_output = response.choices[0].message.content
            messages.append({"role": "assistant", "content": raw_output})
            print(f"\n{'=' * 50}")
            print(f"Step {step + 1}: {raw_output[:200]}...")

            # 3. 解析动作（官方解析器，自动处理坐标转换）
            parsed = self.action_executor.parse(raw_output)

            # 4. 判断结束
            if parsed["action_type"] == "finished":
                return {
                    "success": True,
                    "message": parsed.get("action_inputs", {}).get("content", "Done"),
                    "steps": step + 1,
                }

            # 5. 执行
            await self.action_executor.execute(parsed)
            await asyncio.sleep(0.5)

        return {"success": False, "message": "达到最大步数限制", "steps": self.max_steps}

    async def _get_accessibility_hint(self) -> str:
        """获取无障碍树，压缩为简短文本提示（可选，失败不影响）"""
        try:
            tree = await self.client.accessibility_tree(max_depth=3)
            return self._format_tree(tree)
        except Exception:
            return ""

    def _format_tree(self, tree: dict) -> str:
        if not tree or "tree" not in tree:
            return ""
        lines = []

        def walk(node, depth=0):
            role = node.get("role", "?")
            name = node.get("name", "")
            bounds = node.get("bounds", {})
            if role in ("Button", "Edit", "MenuItem", "Hyperlink",
                         "ListItem", "CheckBox", "TabItem"):
                line = f"{'  ' * depth}[{role}] {name}"
                if bounds:
                    line += f" @({bounds.get('x',0)},{bounds.get('y',0)})"
                lines.append(line)
            for child in node.get("children", []):
                walk(child, depth + 1)

        walk(tree["tree"])
        return "\n".join(lines[:50])
```

### 3.2 主入口

```python
# main.py

import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from src.agentdesk_client import AgentDeskClient
from src.agent_loop import DeskAgent
from src.config import get_config

load_dotenv()

async def main():
    config = get_config()

    # AgentDesk 客户端
    client = AgentDeskClient(
        host=config.agentdesk_host,
        port=config.agentdesk_port,
        token=config.agentdesk_token,
    )

    # UI-TARS 1.5 模型客户端
    model = AsyncOpenAI(
        base_url=config.vision_base_url,
        api_key=config.vision_api_key,
    )

    # Agent
    agent = DeskAgent(
        agentdesk=client,
        model=model,
        model_name=config.vision_model,
        max_steps=config.max_iterations,
    )

    # 健康检查
    if not await client.health_check():
        print("AgentDesk 连接失败")
        return

    screen = await client.screen_info()
    print(f"屏幕: {screen['width']}x{screen['height']} (scale: {screen['scaleFactor']})")

    # 执行任务
    task = input("请输入任务: ")
    result = await agent.run(task)
    print(f"\n结果: {'成功' if result['success'] else '失败'}")
    print(f"步骤: {result['steps']}")
    print(f"信息: {result['message']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 3.3 配置

```python
# src/config.py

import os
from dataclasses import dataclass

@dataclass
class Config:
    # AgentDesk
    agentdesk_host: str = os.getenv("AGENTDESK_HOST", "localhost")
    agentdesk_port: int = int(os.getenv("AGENTDESK_PORT", "9877"))
    agentdesk_token: str = os.getenv("AGENTDESK_TOKEN", "admin123")

    # UI-TARS 模型
    vision_base_url: str = os.getenv("VISION_BASE_URL", "http://localhost:8000/v1")
    vision_api_key: str = os.getenv("VISION_API_KEY", "sk-dummy")
    vision_model: str = os.getenv("VISION_MODEL", "UI-TARS-1.5-7B")

    # 执行参数
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "25"))
    screenshot_quality: int = int(os.getenv("SCREENSHOT_QUALITY", "60"))
    screenshot_max_width: int = int(os.getenv("SCREENSHOT_MAX_WIDTH", "1366"))
    screenshot_max_height: int = int(os.getenv("SCREENSHOT_MAX_HEIGHT", "768"))

def get_config() -> Config:
    return Config()
```

```env
# .env
AGENTDESK_HOST=192.168.1.100
AGENTDESK_PORT=9877
AGENTDESK_TOKEN=admin123

VISION_BASE_URL=http://localhost:8000/v1
VISION_API_KEY=sk-dummy
VISION_MODEL=UI-TARS-1.5-7B

MAX_ITERATIONS=25
SCREENSHOT_QUALITY=60
SCREENSHOT_MAX_WIDTH=1366
SCREENSHOT_MAX_HEIGHT=768
```

---

## 阶段四：验证与调优

### 4.1 健康检查脚本

```bash
# 检查 AgentDesk 是否在线
curl http://192.168.1.100:9877/api/health

# 检查 UI-TARS 模型是否在线
curl http://localhost:8000/v1/models
```

### 4.2 单步调试模式

在 `agent_loop.py` 中增加调试开关，每一步执行前等待用户确认：

```python
class DeskAgent:
    def __init__(self, ..., debug: bool = False):
        self.debug = debug

    async def run(self, task: str) -> dict:
        ...
        for step in range(self.max_steps):
            ...
            if self.debug:
                input("按 Enter 执行此步骤...")
            await self.action_executor.execute(parsed, ...)
```

### 4.3 测试用例

按难度递增：

| 优先级 | 测试任务 | 预期步数 | 验证标准 |
|--------|---------|---------|---------|
| P0 | 打开开始菜单 | 1-2 | 开始菜单出现 |
| P0 | 打开记事本 | 3-4 | 记事本窗口打开 |
| P1 | 在记事本输入 "Hello World" | 4-5 | 文本正确输入 |
| P1 | 记事本保存到桌面，文件名为 test.txt | 6-8 | 桌面出现 test.txt |
| P2 | 打开 Chrome，搜索 "github" | 5-7 | 搜索结果显示 |
| P2 | 调整系统音量为 50% | 3-4 | 音量滑块在 50% 位置 |

---

## 预计时间

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| 阶段一 | AgentDesk HTTP Client | 0.5 天 |
| 阶段二 | 动作解析与坐标换算 | 0.5 天 |
| 阶段三 | Agent Loop + 主入口 | 0.5 天 |
| 阶段四 | 调试与验证 | 1 天 |
| **总计** | | **2.5 天** |

---

## 附录 A：坐标系统

**UI-TARS 1.5 直接输出 0-1000 归一化坐标，与 AgentDesk 坐标系一致，无需换算。**

```
UI-TARS 输出 (0-1000 归一化坐标)
   ↓  直接透传，无需转换
AgentDesk 接收 (0-1000)
   ↓  AgentDesk 内部: x = screenWidth * scaleFactor * (nx / 1000)
物理像素执行
```

| 坐标空间 | 范围 | 示例 |
|---------|------|------|
| UI-TARS 输出 | 0-1000 | (500, 500) = 屏幕中心 |
| AgentDesk 归一化 | 0-1000 | (500, 500) |
| AgentDesk 内部换算后 | 物理像素 | 根据 screenWidth × scaleFactor 计算 |

**无障碍树坐标换算（仅当无障碍树作为辅助提示时）：**

无障碍树 bounds 是物理像素，需转 0-1000：
- 物理分辨率 = 树根节点 `Pane` 的 bounds 宽高（如 2560×1440）
- `nx = bounds.x * 1000 / tree_root_bounds.width`

**为什么不用 `/api/screen/info` 的宽高？** 因为该接口返回的是 Windows 逻辑分辨率（受 DPI 缩放影响），不是物理像素。无障碍树根的 bounds 才是真正的物理分辨率。

## 附录 B：AgentDesk API 速查

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/screenshot` | POST | 截图 `{quality, maxWidth, maxHeight, showGrid}` |
| `/api/screen/info` | GET | 屏幕信息 |
| `/api/mouse` | POST | 鼠标 `{action, x, y}` |
| `/api/keyboard` | POST | 键盘 `{action, text/keys}` |
| `/api/accessibility` | GET | 无障碍树 `?maxDepth=N` |

## 附录 C：常用快捷键

| 操作 | 按键 |
|------|------|
| 显示桌面 | LeftWin + D |
| 打开开始菜单 | LeftWin |
| 复制 | ControlLeft + C |
| 粘贴 | ControlLeft + V |
| 切换窗口 | AltLeft + Tab |
| 关闭窗口 | AltLeft + F4 |
| 任务管理器 | ControlLeft + ShiftLeft + Escape |

---

## 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-05-14 | v2.0 | 以 UI-TARS 1.5 单模型为核心的简化架构，去掉多层状态表设计 |
| 2026-05-13 | v1.0 | 初始多层架构计划 |
