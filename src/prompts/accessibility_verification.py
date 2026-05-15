"""无障碍树差异验证提示词

用于验证操作是否成功，基于操作前后无障碍树的差异分析。
"""


ACCESSIBILITY_VERIFICATION_PROMPT = """请根据操作前后的无障碍树差异，判断操作是否成功。

## 验证标准

{verification_prompt}

## 操作前后差异

{diff_summary}

## 请分析

1. 差异是否表明操作达到了预期效果？
2. 验证标准是否满足？

请用 JSON 格式回答：

```json
{{
  "success": true/false,
  "reason": "简要说明判断依据"
}}
```

- `success`: true 表示验证通过，false 表示验证失败
- `reason`: 简要解释为什么判断成功或失败，引用具体的差异内容
"""


def build_accessibility_verification_prompt(
    verification_prompt: str,
    diff_summary: str,
) -> str:
    """构建无障碍树验证提示词
    
    Args:
        verification_prompt: 验证标准描述
        diff_summary: 无障碍树差异摘要
        
    Returns:
        完整的提示词
    """
    return ACCESSIBILITY_VERIFICATION_PROMPT.format(
        verification_prompt=verification_prompt,
        diff_summary=diff_summary,
    )


__all__ = [
    "ACCESSIBILITY_VERIFICATION_PROMPT",
    "build_accessibility_verification_prompt",
]