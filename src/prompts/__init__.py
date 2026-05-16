"""Prompt 模板模块

统一的提示词系统，包含静态提示词和动态提示词。

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

### 3. 统一验证提示词

```python
from src.prompts import build_verification_prompt, build_verification_message

# 构建 user message（包含截图）
message = build_verification_message(
    verification_prompt="验证保存成功",
    focus_diff="...",
    tree_diff="...",
    screenshot_base64="..."
)

# 或仅构建文本提示词
prompt_text = build_verification_prompt("验证保存成功")
```
"""

# 主要导出
from .builder import PromptBuilder, build_planner_prompt
from .vision_grounding import build_vision_grounding_prompt, VISION_GROUNDING_PROMPT
from .verification import build_verification_prompt, build_verification_message, VERIFICATION_PROMPT

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


__all__ = [
    # 主要类
    "PromptBuilder",
    
    # 便捷函数
    "build_planner_prompt",
    "build_vision_grounding_prompt",
    "build_verification_prompt",
    "build_verification_message",
    "build_dynamic_prompt",
    
    # 向后兼容别名
    "build_system_prompt",
    "build_vision_prompt",
    
    # 提示词常量
    "SYSTEM_ROLE",
    "AVAILABLE_ACTIONS",
    "EXECUTION_RULES",
    "OUTPUT_FORMAT",
    "VERIFICATION_METHODS",
    "VISION_GROUNDING_PROMPT",
    "VERIFICATION_PROMPT",
    
    # 工具函数
    "get_shortcuts",
]