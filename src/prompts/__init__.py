"""Prompt 模板模块

新的提示词系统，支持静态提示词和动态提示词分离。

## 使用方式

### 1. 使用 PromptBuilder（推荐）

```python
from src.prompts import PromptBuilder

builder = PromptBuilder(os_type="Windows")
system_prompt = builder.build_system_message(
    global_info="...",
    execution_plan="...",
    history="...",
    instruction="任务描述"
)
```

### 2. 使用便捷函数（向后兼容）

```python
from src.prompts import build_planner_prompt

system_prompt = build_planner_prompt(
    task="任务描述",
    global_info="...",
    history="...",
    execution_plan="..."
)
```

### 3. 单独构建提示词

```python
from src.prompts.static import get_shortcuts, AVAILABLE_ACTIONS
from src.prompts import build_vision_grounding_prompt, build_calibrator_prompt

shortcuts = get_shortcuts("Windows")
vision_prompt = build_vision_grounding_prompt("找到保存按钮")
```
"""

# 主要导出
from .builder import PromptBuilder, build_planner_prompt
from .calibrator import build_calibrator_prompt, CALIBRATOR_PROMPT
from .vision_grounding import build_vision_grounding_prompt, VISION_GROUNDING_PROMPT
from .vision_verification import build_vision_verification_prompt, VISION_VERIFICATION_PROMPT
from .accessibility_verification import build_accessibility_verification_prompt, ACCESSIBILITY_VERIFICATION_PROMPT

# 静态提示词导出
from .static import (
    SYSTEM_ROLE,
    AVAILABLE_ACTIONS,
    EXECUTION_RULES,
    OUTPUT_FORMAT,
    VERIFICATION_METHODS,
    get_shortcuts,
)

# 动态提示词导出
from .dynamic import build_dynamic_prompt

# 为了向后兼容，保留旧的函数别名
build_system_prompt = build_planner_prompt
build_vision_prompt = build_vision_grounding_prompt
build_verification_prompt = build_vision_verification_prompt


__all__ = [
    # 主要类
    "PromptBuilder",
    
    # 便捷函数
    "build_planner_prompt",
    "build_calibrator_prompt",
    "build_vision_grounding_prompt",
    "build_vision_verification_prompt",
    "build_accessibility_verification_prompt",
    "build_dynamic_prompt",
    
    # 向后兼容别名
    "build_system_prompt",
    "build_vision_prompt",
    "build_verification_prompt",
    
    # 提示词常量
    "SYSTEM_ROLE",
    "AVAILABLE_ACTIONS",
    "EXECUTION_RULES",
    "OUTPUT_FORMAT",
    "VERIFICATION_METHODS",
    "CALIBRATOR_PROMPT",
    "VISION_GROUNDING_PROMPT",
    "VISION_VERIFICATION_PROMPT",
    "ACCESSIBILITY_VERIFICATION_PROMPT",
    
    # 工具函数
    "get_shortcuts",
]