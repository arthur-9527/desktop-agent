"""动态上下文提示词

动态提示词在每一步运行时更新，包括全局信息表、执行历史、执行计划、用户任务等。
"""


def build_global_info_section(global_info: str) -> str:
    """构建全局信息表部分
    
    Args:
        global_info: 全局动态信息表文本
        
    Returns:
        格式化后的全局信息部分
    """
    return f"""## 全局信息表

{global_info}

"""


def build_execution_plan_section(execution_plan: str) -> str:
    """构建执行计划部分
    
    Args:
        execution_plan: 执行计划文本
        
    Returns:
        格式化后的执行计划部分
    """
    if not execution_plan or execution_plan.strip() == "":
        return """## 当前执行计划

（暂无执行计划，请根据任务目标制定）
"""
    return f"""## 当前执行计划

{execution_plan}

"""


def build_history_section(history: str) -> str:
    """构建执行历史部分
    
    Args:
        history: 执行历史文本
        
    Returns:
        格式化后的执行历史部分
    """
    if not history or history.strip() == "":
        return """## 执行历史

（暂无执行历史）
"""
    return f"""## 执行历史

{history}

"""


def build_user_task_section(instruction: str, step: int = 0) -> str:
    """构建用户任务部分
    
    Args:
        instruction: 用户任务描述
        step: 当前步数（0 表示第一步）
        
    Returns:
        格式化后的用户任务部分
    """
    prefix = "开始执行任务" if step == 0 else "继续执行任务"
    return f"""## 用户任务

{prefix}: {instruction}

"""


def build_dynamic_prompt(
    global_info: str = "",
    execution_plan: str = "",
    history: str = "",
    instruction: str = "",
    step: int = 0,
) -> str:
    """构建完整的动态提示词
    
    Args:
        global_info: 全局信息表
        execution_plan: 执行计划
        history: 执行历史
        instruction: 用户任务
        step: 当前步数
        
    Returns:
        完整的动态提示词
    """
    parts = [
        build_global_info_section(global_info),
        build_execution_plan_section(execution_plan),
        build_history_section(history),
        build_user_task_section(instruction, step),
    ]
    return "\n".join(parts)


__all__ = [
    "build_global_info_section",
    "build_execution_plan_section",
    "build_history_section",
    "build_user_task_section",
    "build_dynamic_prompt",
]