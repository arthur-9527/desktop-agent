"""无障碍树差异验证提示词

用于验证操作是否成功，基于操作前后两个维度的数据：
1. 聚焦元素变化（操作前后焦点转移情况）
2. 无障碍树结构变化（元素新增/删除/修改）
"""


ACCESSIBILITY_VERIFICATION_PROMPT = """判断操作是否成功。

验证目标: {verification_prompt}
聚焦变化: {focus_diff}
树差异: {tree_diff}

规则：聚焦变化即使无树变化也可能成功；树变化是强信号；两者都无变化则很可能失败。

返回JSON:
{{"success": true/false, "reason": "判断依据"}}
"""


def build_accessibility_verification_prompt(
    verification_prompt: str,
    focus_diff: str,
    tree_diff: str,
) -> str:
    """构建无障碍树验证提示词

    Args:
        verification_prompt: 验证标准描述
        focus_diff: 聚焦元素变化描述
        tree_diff: 无障碍树差异摘要

    Returns:
        完整的提示词
    """
    return ACCESSIBILITY_VERIFICATION_PROMPT.format(
        verification_prompt=verification_prompt,
        focus_diff=focus_diff,
        tree_diff=tree_diff,
    )


__all__ = [
    "ACCESSIBILITY_VERIFICATION_PROMPT",
    "build_accessibility_verification_prompt",
]