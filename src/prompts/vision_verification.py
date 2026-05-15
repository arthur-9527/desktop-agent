"""视觉验证提示词"""


VISION_VERIFICATION_PROMPT = """请根据截图验证操作是否成功完成。

## 验证标准

{verification_prompt}

!!!VERY IMPORTANT: 请仔细检查截图，区分相似元素（如地址栏和搜索栏），确保验证准确性。

请用 JSON 格式回答：

```json
{{
  "success": true/false,
  "reason": "简要说明验证结果"
}}
```

- `success`: true 表示验证通过，false 表示验证失败
- `reason`: 简要解释验证结果，说明看到了什么或没看到什么
"""


def build_vision_verification_prompt(verification_prompt: str) -> str:
    """构建视觉验证提示词
    
    Args:
        verification_prompt: 验证标准描述
        
    Returns:
        完整的提示词
    """
    return VISION_VERIFICATION_PROMPT.format(verification_prompt=verification_prompt)


__all__ = ["VISION_VERIFICATION_PROMPT", "build_vision_verification_prompt"]