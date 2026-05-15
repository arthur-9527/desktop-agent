"""Calibrator 校准提示词"""


CALIBRATOR_PROMPT = """你是一个任务执行校准器。你的职责是审视执行历史，判断任务是否偏离目标，并提供调整建议。

## 原始任务
{task}

## 执行历史摘要
{history_summary}

## 当前全局状态
{global_info}

## 当前执行计划
{execution_plan}

## 请回答以下问题

1. **进度判断**: 当前进度如何？完成了多少？
2. **偏离检测**: 执行是否偏离了原始任务目标？
3. **建议调整**: 如果偏离，应该如何调整？

## 输出格式

请以简洁的中文回答，不超过 200 字。格式如下：

```
进度: [进度描述]
偏离: [是/否，原因]
更新计划: [是/否]
新计划: [如果需要更新，给出新计划步骤，否则留空]
建议: [调整建议]
```
"""


def build_calibrator_prompt(
    task: str,
    history_summary: str,
    global_info: str = "",
    execution_plan: str = "",
) -> str:
    """构建 Calibrator 提示词
    
    Args:
        task: 原始任务
        history_summary: 执行历史摘要
        global_info: 当前全局状态
        execution_plan: 当前执行计划
        
    Returns:
        完整的提示词
    """
    return CALIBRATOR_PROMPT.format(
        task=task,
        history_summary=history_summary,
        global_info=global_info if global_info else "（暂无状态信息）",
        execution_plan=execution_plan if execution_plan else "（暂无执行计划）",
    )


__all__ = ["CALIBRATOR_PROMPT", "build_calibrator_prompt"]