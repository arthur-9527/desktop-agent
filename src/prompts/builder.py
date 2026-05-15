"""PromptBuilder - 提示词构建器

将静态提示词和动态提示词组装成完整的系统提示词。
"""

from typing import Optional

from .static import (
    SYSTEM_ROLE,
    AVAILABLE_ACTIONS,
    EXECUTION_RULES,
    OUTPUT_FORMAT,
    VERIFICATION_METHODS,
    get_shortcuts,
)


class PromptBuilder:
    """提示词构建器
    
    负责组装静态提示词（缓存）和动态提示词（每步更新）
    """
    
    def __init__(self, os_type: str = "Windows"):
        """初始化提示词构建器
        
        Args:
            os_type: 操作系统类型 Windows / macOS / Linux
        """
        self.os_type = os_type
        self._static_prompt: Optional[str] = None
    
    def build_static_prompt(self) -> str:
        """构建静态提示词（系统启动时调用一次，缓存复用）
        
        静态提示词包含不随运行时变化的部分：
        - 系统角色定义
        - 可用动作列表
        - 快捷键参考（根据 OS 类型）
        - 执行规则
        - 输出格式
        - 验证方式说明
        
        Returns:
            完整的静态提示词
        """
        if self._static_prompt is not None:
            return self._static_prompt
        
        # 根据 OS 类型获取快捷键
        shortcuts = get_shortcuts(self.os_type)
        
        # 组装静态提示词
        parts = [
            SYSTEM_ROLE,
            "",  # 空行分隔
            AVAILABLE_ACTIONS,
            "",  # 空行分隔
            shortcuts,
            "",  # 空行分隔
            EXECUTION_RULES,
            "",  # 空行分隔
            OUTPUT_FORMAT,
            "",  # 空行分隔
            VERIFICATION_METHODS,
        ]
        
        self._static_prompt = "\n".join(parts)
        return self._static_prompt
    
    def build_system_message(
        self,
        global_info: str = "",
        execution_plan: str = "",
        history: str = "",
        instruction: str = "",
    ) -> str:
        """构建完整的系统消息（静态 + 动态）
        
        Args:
            global_info: 全局信息表
            execution_plan: 执行计划
            history: 执行历史
            instruction: 用户任务
            
        Returns:
            完整的系统提示词（静态 + 动态）
        """
        # 静态部分
        static = self.build_static_prompt()
        
        # 动态部分
        dynamic_parts = []
        
        if global_info:
            dynamic_parts.append(f"## 全局信息表\n\n{global_info}")
        
        if execution_plan:
            dynamic_parts.append(f"## 当前执行计划\n\n{execution_plan}")
        else:
            dynamic_parts.append("## 当前执行计划\n\n（暂无执行计划，请根据任务目标制定）")
        
        if history:
            dynamic_parts.append(f"## 执行历史\n\n{history}")
        else:
            dynamic_parts.append("## 执行历史\n\n（暂无执行历史）")
        
        if instruction:
            dynamic_parts.append(f"## 用户任务\n\n{instruction}")
        
        dynamic = "\n\n".join(dynamic_parts)
        
        # 合并
        return f"{static}\n\n{dynamic}"
    
    def update_os(self, os_type: str):
        """更新操作系统类型
        
        Args:
            os_type: 新的操作系统类型
        """
        if os_type != self.os_type:
            self.os_type = os_type
            self._static_prompt = None  # 清除缓存，下次重新构建
    
    def clear_cache(self):
        """清除静态提示词缓存"""
        self._static_prompt = None


# ============================================================================
# 便捷的构建函数（向后兼容）
# ============================================================================

def build_planner_prompt(
    task: str,
    global_info: str = "",
    history: str = "",
    execution_plan: str = "",
    os_type: str = "Windows",
) -> str:
    """构建 Planner 系统提示词（便捷函数，向后兼容）
    
    Args:
        task: 任务描述
        global_info: 全局动态信息表
        history: 执行历史
        execution_plan: 当前执行计划
        os_type: 操作系统类型
        
    Returns:
        完整的系统提示词
    """
    builder = PromptBuilder(os_type=os_type)
    return builder.build_system_message(
        global_info=global_info,
        execution_plan=execution_plan,
        history=history,
        instruction=task,
    )


__all__ = [
    "PromptBuilder",
    "build_planner_prompt",
]