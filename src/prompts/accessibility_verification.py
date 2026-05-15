"""无障碍树差异验证提示词

用于验证操作是否成功，基于操作前后两个维度的数据：
1. 聚焦元素变化（操作前后焦点转移情况）
2. 无障碍树结构变化（元素新增/删除/修改）
"""


ACCESSIBILITY_VERIFICATION_PROMPT = """请根据操作前后的聚焦元素变化和无障碍树结构差异，综合判断操作是否成功。

## 验证标准

{verification_prompt}

## 聚焦元素变化

{focus_diff}

## 无障碍树结构变化

{tree_diff}

## 请分析

1. 聚焦元素变化是否表明操作达到了预期效果？
2. 无障碍树结构变化是否支持这一判断？
3. 综合两个维度，验证标准是否满足？

注意：
- 聚焦变化（如焦点转移到目标元素）即使无障碍树结构无变化，也可能意味着操作成功
- 无障碍树结构变化（如弹窗出现）是强信号，应重点参考
- 两个维度都无变化时，操作很可能未生效

请用 JSON 格式回答：

```json
{{
  "success": true/false,
  "reason": "简要说明判断依据，引用具体的聚焦变化和/或树差异"
}}
```

- `success`: true 表示验证通过，false 表示验证失败
- `reason`: 简要解释为什么判断成功或失败
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