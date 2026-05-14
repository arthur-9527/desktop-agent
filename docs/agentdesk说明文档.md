# AgentDesk 技能说明文档

## 项目概述

**AgentDesk** 是一个基于 Electron 的局域网远程桌面控制代理程序，通过 **双通信架构** 提供远程屏幕捕获、鼠标控制和键盘输入功能。

### 核心功能
- **屏幕捕获**：实时捕获桌面画面，支持单帧截图和持续视频流
- **鼠标控制**：远程移动、点击、拖拽、滚轮操作
- **键盘控制**：远程输入文本、按键组合
- **无障碍元素树**：通过 Windows UIAutomation / macOS AXUIElement API 获取界面元素结构，提升定位精度
- **安全认证**：基于密码的 WebSocket 连接认证 + Bearer Token HTTP 认证
- **系统托盘**：无窗口后台运行，通过托盘图标管理

---

## 双通信架构

### 架构概览

```
┌──────────────────────────────────────────────────────────┐
│                       Agent Desk                          │
│                                                           │
│  ┌─────────────┐    ┌──────────────┐                    │
│  │ HTTP Server │    │ WS Server    │                    │
│  │ :9877       │    │ :9876        │                    │
│  │             │    │              │                    │
│  │ /api/health │    │ auth         │                    │
│  │ /api/screenshot │    │ capture_frame │                    │
│  │ /api/mouse  │    │ start_stream │                    │
│  │ /api/keyboard │    │ stream       │                    │
│  │ /api/accessibility│   │              │                    │
│  └──────┬──────┘    └──────────────┘                    │
│         │                                                │
│  ┌──────┴──────────────────────────────────────┐        │
│  │  Accessibility Native Addon (C++ N-API)      │        │
│  │  Windows: UIAutomation Core API              │        │
│  │  macOS: AXUIElement API                      │        │
│  └──────────────────────────────────────────────┘        │
│                                                           │
│  ┌──────────────────────────────────────┐                │
│  │  nut-js (Mouse/Keyboard Automation)   │                │
│  └──────────────────────────────────────┘                │
│                                                           │
│  ┌──────────────────────────────────────┐                │
│  │  desktopCapturer (Screen Capture)    │                │
│  └──────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────┘
```

**设计原则：**
- **HTTP API** — 适合按需操作（截图、点击、输入、获取元素树），请求-响应模式
- **WebSocket** — 适合持续流传输（实时桌面监控、视频流）
- **Accessibility Native Addon** — C++ N-API 插件直接调用系统 API，同步返回元素树

---

## HTTP API 文档

### 认证方式

所有 API 端点（除 `/api/health`）使用 Bearer Token 认证：

```
Authorization: Bearer admin123
```

### 截图 API

#### POST /api/screenshot — 返回 base64 JSON

```bash
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/screenshot \
  -d '{"quality": 20, "maxWidth": 1024, "maxHeight": 768}'
```

**响应：**
```json
{
  "data": "base64-jpeg-data...",
  "width": 1024,
  "height": 768,
  "timestamp": 1234567890
}
```

**参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| quality | number | 20 | JPEG 压缩质量 (0-100) |
| maxWidth | number | 1024 | 最大宽度 |
| maxHeight | number | 768 | 最大高度 |

#### GET /api/screenshot — 直接返回 JPEG 图片

```bash
curl -H "Authorization: Bearer admin123" \
  -o screenshot.jpg \
  http://localhost:9877/api/screenshot?quality=20&maxWidth=1024&maxHeight=768
```

**响应：** JPEG 图片二进制数据

#### 截图参数（GET/POST 均支持）

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| quality | number | 80 | JPEG 压缩质量 (0-100) |
| maxWidth | number | 1366 | 最大宽度 |
| maxHeight | number | 768 | 最大高度 |
| **showGrid** | boolean | false | **叠加精细化网格** |
| **gridLevel** | 32\|64\|128 | 自动检测 | 网格层级（按分辨率自动选择） |
| gridColor | string | 255,0,0 | 网格颜色（RGB 格式） |
| gridAlpha | number | 0.6 | 大格子透明度（0-1） |
| subGridAlpha | number | 0.2 | 小格子虚线透明度（0-1） |
| gridLineWidth | number | 2 | 网格线宽（像素） |

**网格层级系统（分辨率自适应）：**

| 层级 | 适用分辨率 | 大格子布局 | 小格细分 | 总子格数 |
|------|-----------|-----------|---------|---------|
| **32** | ≤1280px 宽 | 4列×2行=8格 | 4×4=16小格 | 128 |
| **64** | 1281-1920px | 4列×4行=16格 | 4×4=16小格 | 256 |
| **128** | >1920px | 8列×4行=32格 | 4×4=16小格 | 512 |

**叠加网格示例：**

```bash
# 自动检测层级（根据分辨率）
curl -H "Authorization: Bearer admin123" \
  -o screenshot_auto.jpg \
  http://localhost:9877/api/screenshot?showGrid=true

# 强制指定 64 层级
curl -H "Authorization: Bearer admin123" \
  -o screenshot_64.jpg \
  "http://localhost:9877/api/screenshot?showGrid=true&gridLevel=64"

# 自定义网格样式
curl -H "Authorization: Bearer admin123" \
  -o screenshot_custom.jpg \
  "http://localhost:9877/api/screenshot?showGrid=true&gridLevel=128&gridColor=0,255,0&gridAlpha=0.8&subGridAlpha=0.3"
```

**网格效果（以 64 层级为例）：**

```
┌──────────┬──────────┬──────────┬──────────┐  ← 大格子（粗实线，2px）
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │  ← 小格子（虚线，1px）
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │     每个大格内 4×4 细分
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
├──────────┼──────────┼──────────┼──────────┤
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
├──────────┼──────────┼──────────┼──────────┤
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
├──────────┼──────────┼──────────┼──────────┤
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
│ · · · ·  │ · · · ·  │ · · · ·  │ · · · ·  │
└──────────┴──────────┴──────────┴──────────┘
```

**网格说明：**

| 层级 | 样式 | 线宽 | 颜色 | 作用 |
|------|------|------|------|------|
| 大格子边框 | 粗实线 | 2px | rgba(255,0,0,0.6) | 宏观分区定位 |
| 小格子虚线 | 虚线（4px线段+4px间隙） | 1px | rgba(255,0,0,0.2) | 微观精确定位 |

**精度分析（以 1920x1080 屏幕，128 层级为例）：**

- 大格子尺寸：约 240×270 像素
- 小格子尺寸：约 60×67 像素
- 定位精度：±30 像素（截图中）→ 映射回原始屏幕约 ±45 像素

**为什么分层级更好？**

1. **自适应分辨率**：低分辨率屏幕不过密，高分辨率屏幕不稀疏
2. **层次清晰**：大格子实线 + 小格子虚线，视觉层次分明
3. **AI 友好**：16 宫格规律性强，便于视觉模型理解网格编号
4. **灵活可控**：支持自动检测或手动指定层级

### 屏幕信息 API

#### GET /api/screen/info

```bash
curl -H "Authorization: Bearer admin123" \
  http://localhost:9877/api/screen/info
```

**响应：**
```json
{
  "width": 1920,
  "height": 1080,
  "scaleFactor": 1.5
}
```

### 鼠标 API

#### POST /api/mouse

```bash
# 移动鼠标到屏幕中心（归一化坐标 0-1000）
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "move", "x": 500, "y": 500}'

# 左键点击
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "left_click"}'

# 左键点击指定位置
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "left_click", "x": 500, "y": 500}'

# 右键点击
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "right_click"}'

# 双击
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "double_click"}'

# 滚动
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "scroll", "direction": "up", "amount": 1}'

# 拖拽操作（需要分三步：按下左键 -> 拖拽到目标位置 -> 释放左键）
# 步骤1: 按下左键
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "press_left"}'

# 步骤2: 拖拽到目标位置（可多次调用实现连续拖拽）
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "drag", "x": 500, "y": 500}'

# 步骤3: 释放左键
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/mouse \
  -d '{"action": "release_left"}'
```

**请求体：**
| 字段 | 类型 | 说明 |
|------|------|------|
| action | string | move / left_click / right_click / double_click / scroll / drag / press_left / release_left |
| x | number | 归一化 X 坐标 (0-1000)，move/left_click/drag 需要 |
| y | number | 归一化 Y 坐标 (0-1000)，move/left_click/drag 需要 |
| direction | string | up / down，scroll 需要 |
| amount | number | 滚动量，scroll 需要 |

#### GET /api/mouse/position

```bash
curl -H "Authorization: Bearer admin123" \
  http://localhost:9877/api/mouse/position
```

**响应：**
```json
{
  "x": 1234,
  "y": 567
}
```

### 键盘 API

#### POST /api/keyboard

```bash
# 输入文本
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/keyboard \
  -d '{"action": "type", "text": "hello"}'

# 按键按下
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/keyboard \
  -d '{"action": "press", "keys": ["LeftWin"]}'

# 按键释放
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/keyboard \
  -d '{"action": "release", "keys": ["LeftWin"]}'
```

**请求体：**
| 字段 | 类型 | 说明 |
|------|------|------|
| action | string | type / press / release |
| text | string | 要输入的文本，type 需要 |
| keys | string[] | 按键数组，press/release 需要 |

### 无障碍元素树 API

通过 C++ 原生插件调用系统 Accessibility API，获取当前桌面的 UI 元素结构树，与截图配合使用可大幅提升 AI 定位精度。

#### GET /api/accessibility — 获取完整元素树

```bash
curl -H "Authorization: Bearer admin123" \
  http://localhost:9877/api/accessibility?maxDepth=3
```

**参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| maxDepth | number | 3 | 最大递归深度 (1-20) |

**响应：**
```json
{
  "tree": {
    "role": "Pane",
    "name": "桌面 1",
    "bounds": { "x": 0, "y": 0, "width": 2560, "height": 1440 },
    "children": [
      {
        "role": "Window",
        "name": "Visual Studio Code",
        "bounds": { "x": -9, "y": -9, "width": 2578, "height": 1398 },
        "children": [...]
      }
    ]
  }
}
```

#### GET /api/accessibility/focused — 获取当前焦点元素

```bash
curl -H "Authorization: Bearer admin123" \
  http://localhost:9877/api/accessibility/focused
```

**响应：**
```json
{
  "element": {
    "role": "Edit",
    "name": "Message input",
    "bounds": { "x": 1735, "y": 1236, "width": 804, "height": 50 },
    "children": [...]
  }
}
```

#### 元素节点结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `role` | string | 元素角色（Window, Button, Edit, Text, Pane 等） |
| `name` | string | 元素名称/文本内容 |
| `bounds` | object | 元素位置和大小 `{x, y, width, height}` |
| `children` | AccessibilityNode[] | 子元素数组（递归，仅当有子元素时存在） |

**Role 对照表：**

| role | 说明 |
|------|------|
| Window | 窗口 |
| Pane | 面板/容器 |
| Button | 按钮 |
| Edit | 输入框 |
| Text | 文本 |
| CheckBox | 复选框 |
| Menu / MenuItem | 菜单/菜单项 |
| List / ListItem | 列表/列表项 |
| Tree / TreeItem | 树/树节点 |
| ComboBox | 下拉框 |
| Hyperlink | 链接 |
| Image | 图片 |
| Tab / TabItem | 标签页/标签 |
| Unknown | 未知类型 |

#### 客户端辅助方法

```typescript
// 按 role 查找元素
findElementsByRole(tree, role, name?)

// 按坐标查找元素（从外到内）
findElementsAtPoint(tree, x, y)
```

### 健康检查

#### GET /api/health

```bash
curl http://localhost:9877/api/health
```

**响应：**
```json
{
  "status": "ok",
  "wsPort": 9876,
  "httpPort": 9877
}
```

### 快捷操作

```bash
# 显示桌面（Win+D）
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/keyboard \
  -d '{"action": "press", "keys": ["LeftWin", "D"]}'
sleep 0.05
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/keyboard \
  -d '{"action": "release", "keys": ["LeftWin", "D"]}'

# Ctrl+C
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/keyboard \
  -d '{"action": "press", "keys": ["ControlLeft", "C"]}'
sleep 0.05
curl -H "Authorization: Bearer admin123" \
  -X POST http://localhost:9877/api/keyboard \
  -d '{"action": "release", "keys": ["ControlLeft", "C"]}'
```

---

## 坐标系统

### 归一化坐标 (0-1000)

客户端发送的坐标使用 **0-1000 的归一化坐标系**，服务端自动转换为实际屏幕像素坐标。

**转换公式：**
```typescript
const factor = platform === 'darwin' ? 1 : scaleFactor;
const x = screenWidth * factor * (normalizedX / 1000);
const y = screenHeight * factor * (normalizedY / 1000);
```

**示例：**
- 屏幕分辨率: 1920x1080, ScaleFactor: 1.5
- 客户端发送: `{x: 500, y: 500}`
- 实际坐标: `{x: 1440, y: 810}` (Windows/Linux)
- 实际坐标: `{x: 960, y: 540}` (macOS)

---

## WebSocket 协议（视频流 + 实时操作）

### WebSocket 连接流程

```
客户端                    服务端
  |                        |
  | ------- connect -----> |
  |                        |
  | <---- auth_required ---| (如果不是认证消息)
  |                        |
  | ------- auth --------> | {type: 'auth', password: 'xxx'}
  |                        |
  | <---- auth_result -----| {type: 'auth_result', success: true/false}
  |                        |
  | <------- ready --------| {type: 'ready', screenSize, platform}
  |                        |
  | ===== 开始控制操作 ===== |
```

### 消息类型

#### 1. 认证相关

| 消息类型 | 方向 | 描述 |
|---------|------|------|
| `auth` | C→S | 发送密码进行认证 `{password: string}` |
| `auth_result` | S→C | 认证结果 `{success: boolean}` |
| `auth_required` | S→C | 需要认证提示 |
| `ready` | S→C | 认证成功，服务就绪 `{screenSize, platform}` |

#### 2. 屏幕控制

| 消息类型 | 方向 | 描述 |
|---------|------|------|
| `capture_frame` | C→S | 捕获单帧 `{quality?: number, maxWidth?: number, maxHeight?: number}` |
| `start_stream` | C→S | 开始视频流 `{fps?: number, quality?: number, maxWidth?: number, maxHeight?: number}` |
| `stop_stream` | C→S | 停止视频流 |
| `frame` | S→C | 帧数据 `{data: base64, width, height, timestamp}` |
| `stream_started` | S→C | 流已开始 `{fps, quality}` |
| `stream_stopped` | S→C | 流已停止 |
| `get_screen_info` | C→S | 获取屏幕信息 |
| `screen_info` | S→C | 屏幕信息 `{width, height, scaleFactor}` |

**截屏参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `quality` | number | 20 | JPEG 压缩质量 (0-100)，越低文件越小 |
| `maxWidth` | number | 1024 | 最大宽度，用于压缩截图尺寸 |
| `maxHeight` | number | 768 | 最大高度，用于压缩截图尺寸 |

**推荐参数：** 对于 Claude vision 分析，推荐 `quality=20, maxWidth=1024, maxHeight=768`，截屏约 30-60KB（base64 后约 40-80KB）。

#### 3. 鼠标控制

| 消息类型 | 方向 | 描述 |
|---------|------|------|
| `mouse_move` | C→S | 移动鼠标 `{x, y}` (0-1000 归一化坐标) |
| `mouse_left_click` | C→S | 左键点击 `{x?, y?}` (可选坐标) |
| `mouse_right_click` | C→S | 右键点击 `{x?, y?}` (可选坐标) |
| `mouse_double_click` | C→S | 双击 |
| `mouse_press_left` | C→S | 左键按下 |
| `mouse_release_left` | C→S | 左键释放 |
| `mouse_drag` | C→S | 拖拽到位置 `{x, y}` |
| `mouse_scroll` | C→S | 滚轮滚动 `{direction, amount}` |
| `get_mouse_position` | C→S | 获取鼠标位置 |
| `mouse_position` | S→C | 鼠标位置 `{x, y}` |

#### 4. 键盘控制

| 消息类型 | 方向 | 描述 |
|---------|------|------|
| `keyboard_type` | C→S | 输入文本 `{text: string}` |
| `keyboard_press` | C→S | 按键按下 `{keys: string[]}` |
| `keyboard_release` | C→S | 按键释放 `{keys: string[]}` |

#### 5. 响应

| 消息类型 | 方向 | 描述 |
|---------|------|------|
| `response` | S→C | 操作响应 `{requestType, code: 0成功/1失败, msg?}` |

---

## 支持的按键

### 字母与数字
`A-Z`, `0-9`

### 功能键
`F1-F24`, `Fn`

### 控制键
- `ShiftLeft` / `ShiftRight`
- `AltLeft` / `AltRight`
- `ControlLeft` / `ControlRight`
- `MetaLeft` / `MetaRight` (Cmd/Win)
- `LeftCmd` / `RightCmd`
- `LeftWin` / `RightWin`

### 特殊键
`Enter`, `Space`, `Backspace`, `Delete`, `Tab`, `CapsLock`
`ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`
`Backquote`, `Backslash`

---

## 配置说明

配置文件位置：`%APPDATA%/agent-desk/config.json` (Windows) 或对应平台的 userData 目录

```json
{
  "wsPort": 9876,
  "httpPort": 9877,
  "password": "admin123"
}
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `wsPort` | WebSocket 服务端口 | 9876 |
| `httpPort` | HTTP 服务端口 | 9877 |
| `password` | 连接认证密码 | admin123 |

---

## 开发指南

### 安装依赖
```bash
pnpm install
```

### 开发运行
```bash
pnpm run dev
```

### 编译原生插件

```bash
# Windows（当前系统 Node.js）
npm run build:accessibility
# 或指定 Electron 版本
npm run build:accessibility:win

# macOS
npm run build:accessibility:mac
```

**注意：** 原生插件需要单独编译，`npm run build`（仅 TypeScript）和 `npm run build:win` 不会自动触发。开发时需要在首次运行前先执行一次。

### 构建

```bash
# 仅编译 TypeScript
npm run build

# 编译原生插件 + TypeScript
npm run build:accessibility && npm run build

# 打包 Windows 安装包（需先编译原生插件）
npm run build:accessibility && npm run build:win

# 打包 macOS
npm run build:accessibility:mac && npm run build:mac

# 打包 Linux
npm run build:linux
```

---

## 使用示例

### Node.js HTTP 客户端示例

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:9877';
const TOKEN = 'admin123';

async function screenshot() {
  // 方式1: 获取 base64 JSON
  const resp = await axios.post(`${BASE_URL}/api/screenshot`,
    { quality: 20, maxWidth: 1024, maxHeight: 768 },
    { headers: { Authorization: `Bearer ${TOKEN}` } }
  );
  // resp.data = { data: "base64...", width, height, timestamp }
  
  // 方式2: 直接保存图片
  const buffer = await axios.get(`${BASE_URL}/api/screenshot`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
    responseType: 'arraybuffer'
  });
  // require('fs').writeFileSync('screenshot.jpg', buffer.data);
}

async function mouseClick(x, y) {
  await axios.post(`${BASE_URL}/api/mouse`,
    { action: 'left_click', x, y },
    { headers: { Authorization: `Bearer ${TOKEN}` } }
  );
}

async function typeText(text) {
  await axios.post(`${BASE_URL}/api/keyboard`,
    { action: 'type', text },
    { headers: { Authorization: `Bearer ${TOKEN}` } }
  );
}

async function getAccessibilityTree() {
  const resp = await axios.get(`${BASE_URL}/api/accessibility`, {
    params: { maxDepth: 3 },
    headers: { Authorization: `Bearer ${TOKEN}` }
  });
  // resp.data.tree = { role, name, bounds, children }

  // 辅助方法：查找特定元素
  const buttons = resp.data.tree.children
    .flatMap(n => n.children || [])
    .filter(n => n.role === 'Button');
  return buttons;
}

screenshot().then(() => console.log('Done'));
```

### Node.js WebSocket 客户端示例

```javascript
const WebSocket = require('ws');

const ws = new WebSocket('ws://localhost:9876');

ws.on('open', () => {
  // 认证
  ws.send(JSON.stringify({ type: 'auth', password: 'admin123' }));
});

ws.on('message', (data) => {
  const msg = JSON.parse(data.toString());
  
  switch (msg.type) {
    case 'auth_result':
      if (msg.success) {
        console.log('认证成功');
        ws.send(JSON.stringify({ type: 'get_screen_info' }));
      }
      break;
      
    case 'ready':
      ws.send(JSON.stringify({ 
        type: 'start_stream', 
        fps: 30, 
        quality: 80 
      }));
      break;
      
    case 'frame':
      console.log(`收到帧: ${msg.width}x${msg.height}`);
      break;
  }
});

// 鼠标点击
ws.send(JSON.stringify({ 
  type: 'mouse_left_click', 
  x: 500, 
  y: 500  // 归一化坐标 0-1000
}));

// 输入文本
ws.send(JSON.stringify({ 
  type: 'keyboard_type', 
  text: 'Hello World' 
}));
```

### Python 客户端示例

```python
from embedded_agent.skills import AgentDeskSkill

async def main():
    # HTTP 模式（默认）
    desk = AgentDeskSkill()
    await desk.connect()
    
    # 截屏（低分辨率 + 高压缩，适合 Claude vision）
    img = await desk.capture_screen(max_width=1024, max_height=768, quality=20)
    
    # 操作
    await desk.mouse_left_click(500, 500)
    await desk.keyboard_type("hello")
    await desk.minimize_all_windows()
    
    await desk.disconnect()
    
    # WebSocket 模式（视频流）
    desk2 = AgentDeskSkill(transport='ws')
    await desk2.connect()
    await desk2.start_stream(fps=15, quality=20)
    frame = await desk2.get_frame()
    await desk2.stop_stream()
    await desk2.disconnect()

# Claude Code 调用方式（通过 curl）
# 截屏: curl -s -H "Authorization: Bearer admin123" http://localhost:9877/api/screenshot
# 点击: curl -s -H "Authorization: Bearer admin123" -X POST http://localhost:9877/api/mouse -d '{"action":"left_click","x":500,"y":500}'
# 输入: curl -s -H "Authorization: Bearer admin123" -X POST http://localhost:9877/api/keyboard -d '{"action":"type","text":"hello"}'
# 元素树: curl -s -H "Authorization: Bearer admin123" "http://localhost:9877/api/accessibility?maxDepth=2"
# 焦点元素: curl -s -H "Authorization: Bearer admin123" "http://localhost:9877/api/accessibility/focused"
```

---

## 安全注意事项

1. **密码保护**：默认密码为 `admin123`，生产环境务必修改
2. **局域网限制**：建议仅在受信任的局域网内使用
3. **防火墙配置**：确保 WebSocket/HTTP 端口在防火墙中正确配置
4. **HTTPS/WSS**：如需公网使用，建议添加 TLS/SSL 加密层

---

## 平台支持

| 平台 | 支持状态 | 注意事项 |
|------|---------|---------|
| Windows | ✅ 完全支持 + 无障碍元素树 | 坐标需要应用 scaleFactor，无障碍需 UIAutomation API（Win7+） |
| macOS | ✅ 完全支持 + 无障碍元素树 | 需要「辅助功能」权限授权 |
| Linux | ⚠️ 理论支持 | 依赖 nut-js 的 Linux 支持，无障碍暂不支持 |

---

## 依赖说明

- **@nut-tree-fork/nut-js**: 跨平台 UI 自动化库的分支版本
- **electron**: 提供桌面捕获和系统托盘功能
- **ws**: 高性能 WebSocket 实现
- **express**: HTTP API 服务器
- **node-addon-api / node-gyp**: C++ 原生插件构建工具链
- **Windows UIAutomation Core API**: Windows 无障碍元素树获取
- **macOS ApplicationServices / AXUIElement**: macOS 无障碍元素树获取

---

## 故障排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 无法连接 | 防火墙/端口占用 | 检查 wsPort/httpPort 配置，确保端口开放 |
| 认证失败 | 密码错误 | 检查客户端和服务端密码配置 |
| 屏幕捕获失败 | 权限问题 | macOS 需要授予屏幕录制权限 |
| 鼠标无响应 | 坐标转换错误 | 确认使用 0-1000 归一化坐标 |
| 键盘输入乱码 | 键名映射问题 | 使用 constants.ts 中定义的键名 |
| 无障碍 API 返回 `role: 'error'` | native addon 未加载 | `npm run build:accessibility` 重新编译 |
| 无障碍 API 编译失败 | C++ 编译环境问题 | 检查是否安装 VS2022 Build Tools 和 Windows SDK |
| macOS 无障碍无数据 | 权限未授权 | 系统设置 > 隐私 > 辅助功能 中授权 |

---

## 版本历史

- **v2.1.0** - 无障碍元素树
  - 新增 `GET /api/accessibility` 和 `GET /api/accessibility/focused`
  - Windows UIAutomation / macOS AXUIElement 原生插件
  - 客户端辅助方法 `findElementsByRole` / `findElementsAtPoint`

- **v2.0.0** - 双通信架构
  - HTTP API + WebSocket 双服务
  - Bearer Token 认证
  - Claude Code 友好 API 设计

- **v1.0.0** - 初始版本
  - WebSocket 远程控制
  - 屏幕捕获与流传输
  - 鼠标/键盘控制
  - 系统托盘应用