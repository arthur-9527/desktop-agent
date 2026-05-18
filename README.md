# DeskAgent

桌面自动化代理，采用三模型架构，通过 AgentDesk HTTP API 实现远程桌面操作控制。

> ⚠️ **警告**：该项目仅供学习研究使用，请谨慎操作。该工具具备真实的桌面控制能力，可能造成文件删除、系统配置修改等不可逆操作。使用者需自行承担因误操作导致的一切损失，作者概不负责。

## ✨ 特性

- **三模型架构**：Planner (LLM) 主循环决策 + Grounding (UI-TARS) 视觉定位 + Calibrator (LLM) 计划制定与操作验证
- **远程桌面控制**：通过 AgentDesk HTTP API 进行鼠标、键盘、截图等操作
- **无障碍树解析**：解析系统无障碍树，精准定位 UI 元素
- **视觉定位**：基于 UI-TARS 视觉模型的目标元素定位
- **执行计划**：Calibrator 模型自动制定任务执行计划并逐步执行
- **操作验证**：Calibrator 模型基于聚焦变化、无障碍树差异和截图的统一验证

## 🏗️ 架构

```
┌─────────────────────────────────────────┐
│               DeskAgent                  │
├─────────────────────────────────────────┤
│  Planner (LLM)        主循环 Worker 决策  │
│  Grounding (UI-TARS)   视觉定位           │
│  Calibrator (LLM)      计划制定 + 验证     │
├─────────────────────────────────────────┤
│  ActionExecutor       动作执行器          │
│  DesktopClient        API 客户端          │
│  AccessibilityParser  无障碍树解析         │
└──────────────┬──────────────────────────┘
               │ HTTP API
┌──────────────▼──────────────────────────┐
│            AgentDesk 服务                 │
└─────────────────────────────────────────┘
```

## 📋 环境要求

- Python 3.10+
- AgentDesk 服务（远程桌面控制后端）
- UI-TARS 视觉模型服务
- LLM 服务（Planner / Calibrator）

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/arthur-9527/desktop-agent.git
cd desktop-agent

# 安装依赖
pip install -r requirements.txt
```

## ⚙️ 配置

通过 `.env` 文件或环境变量配置：

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `AGENTDESK_HOST` | AgentDesk 服务地址 | `localhost` |
| `AGENTDESK_PORT` | AgentDesk 服务端口 | `9877` |
| `AGENTDESK_TOKEN` | AgentDesk 认证令牌 | `admin123` |
| `VISION_BASE_URL` | UI-TARS 视觉模型 API | `http://localhost:8000/v1` |
| `VISION_API_KEY` | 视觉模型 API Key | `sk-dummy` |
| `VISION_MODEL` | 视觉模型名称 | `UI-TARS-1.5-7B` |
| `LLM_BASE_URL` | Planner LLM API | `http://localhost:4000/v1` |
| `LLM_API_KEY` | Planner API Key | `sk-dummy` |
| `GENERAL_MODEL` | Planner 模型名称 | `qwopus-35b` |
| `CALIBRATION_BASE_URL` | Calibrator LLM API (空则复用 Planner) | - |
| `CALIBRATION_API_KEY` | Calibrator API Key | - |
| `CALIBRATION_MODEL` | Calibrator 模型名称 | - |
| `MAX_ITERATIONS` | 最大执行步数 | `25` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `DEBUG` | 调试模式 | `false` |

## 🚀 使用方法

```bash
# 直接指定任务
python main.py "在记事本中写一段文字并保存"

# 交互式输入任务
python main.py
```

## 📁 项目结构

```
deskagent/
├── main.py                     # 主入口
├── requirements.txt            # Python 依赖
├── src/
│   ├── agent_loop.py           # 核心 Agent 主循环
│   ├── action_executor.py      # 动作解析与执行
│   ├── accessibility_parser.py # 无障碍树解析
│   ├── config.py               # 配置管理
│   ├── logger.py               # 日志模块
│   ├── metrics.py              # 运行指标统计
│   ├── utils.py                # 工具函数
│   ├── desktoptools/           # AgentDesk HTTP API 客户端
│   │   ├── client.py           # 统一门面类
│   │   └── atomic_ops.py       # 原子操作
│   └── prompts/                # Prompt 管理
│       ├── builder.py          # Prompt 构建器
│       ├── verification.py     # 验证 Prompt
│       ├── vision_grounding.py # 视觉定位 Prompt
│       ├── static/             # 静态 Prompt 模板
│       └── dynamic/            # 动态上下文生成
└── docs/                       # 文档
```

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件