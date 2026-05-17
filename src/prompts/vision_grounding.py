"""视觉定位（Vision Grounding）prompt —— 中文 + JSON 格式输出"""


VISION_GROUNDING_PROMPT = """请根据截图定位以下目标元素：

{target_description}

## 任务

1. 在截图中定位目标元素
2. 返回该元素中心点的像素坐标

## 输出格式
你必须严格按照以下 JSON 格式输出，不要输出任何其他内容：
{{
    "found": true/false,
    "x": 整数像素坐标X,
    "y": 整数像素坐标Y,
    "desc": "简短的中文描述"
}}

如果目标元素无法精确定位（例如有多个相似候选、未完全可见、无显著特征等），
请用 desc 字段尽可能多地列举与目标相关的 UI 元素信息和坐标，供用户决策：
{{
    "found": false,
    "desc": "列举所有可能相关的UI元素及其位置信息"
}}
"""


def build_vision_grounding_prompt(
    target_description: str
) -> str:
    """Build the vision grounding prompt.

    Args:
        target_description: Description of the target element to locate.

    Returns:
        The formatted prompt string.
    """
    return VISION_GROUNDING_PROMPT.format(
        target_description=target_description
    )


__all__ = ["VISION_GROUNDING_PROMPT", "build_vision_grounding_prompt"]
