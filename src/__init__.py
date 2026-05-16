"""DeskAgent - UI-TARS 驱动的桌面自动化 Agent（三模型架构）"""

__version__ = "1.2.0"

# 核心组件
from .agent_loop import DeskAgent, ExecutionHistory
from .action_executor import ActionExecutor, KeyMapper
from .config import Config, get_config

# 无障碍树解析
from .accessibility_parser import (
    AccessibilityParser, 
    create_info_table, 
    GlobalInfo,
    diff_trees,
    DiffResult
)

# Prompts
from .prompts import (
    build_planner_prompt,
    build_vision_prompt
)

# Metrics
from .metrics import RunMetrics, StepMetric, MetricsTimer

__all__ = [
    # 核心组件
    "DeskAgent",
    "ActionExecutor",
    "KeyMapper",
    "Config",
    "get_config",
    "ExecutionHistory",
    # 无障碍树
    "AccessibilityParser",
    "create_info_table",
    "GlobalInfo",
    "diff_trees",
    "DiffResult",
    # Prompts
    "build_planner_prompt",
    "build_vision_prompt",
    # Metrics
    "RunMetrics",
    "StepMetric",
    "MetricsTimer",
]