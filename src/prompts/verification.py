"""统一验证提示词

用于验证操作是否成功，基于四种维度的数据：
1. 验证目标：用户期望的验证标准
2. 聚焦元素变化（操作前后焦点转移情况）
3. 无障碍树结构变化（元素新增/删除/修改）
4. 验证截图（操作后的视觉截图）

使用校准大模型进行验证。
"""


VERIFICATION_PROMPT = """你是一个任务执行验证器。你的职责是判断根据传入的信息以及图片内容判断操作是否成功完成。

## 验证目标
{verification_prompt}

## 聚焦元素变化
{focus_diff}

## 无障碍树结构变化
{tree_diff}

## 操作后截图
{image}


## 输出格式

请以 JSON 格式回答：

```json
{{
  "success": true/false,
  "reason": "简要说明验证结果"
}}
```

- `success`: true 表示验证通过，false 表示验证失败
- `reason`: 
  - 无论成功或失败，都需要尽可能多的列出当前界面中与验证目标相关的UI元素及其状态（如：该窗口展示窗口内容、按钮名称、是否可见、是否禁用、大致位置等），供下一步决策参考
  - 验证通过时：简要说明成功原因，并列出相关UI元素状态
  - 验证失败时：详细描述失败原因，并更详细的列出相关UI元素状态
"""


def build_verification_prompt(
    verification_prompt: str,
    focus_diff: str,
    tree_diff: str,
    screenshot_base64: str = "",
) -> list:
    """构建统一验证提示词
    
    Args:
        verification_prompt: 验证标准描述
        focus_diff: 聚焦元素变化描述
        tree_diff: 无障碍树差异摘要
        screenshot_base64: 截图的 base64 编码（可选）
    
    Returns:
        包含文本和图片内容的消息列表
    """
    content_parts = []
    
    # 文本部分
    text = VERIFICATION_PROMPT.format(
        verification_prompt=verification_prompt,
        focus_diff=focus_diff if focus_diff else "（无聚焦变化信息）",
        tree_diff=tree_diff if tree_diff else "（无障碍树无变化）",
        image="（暂无截图）" if not screenshot_base64 else "（截图已提供）",
    )
    content_parts.append({"type": "text", "text": text})
    
    # 图片部分
    if screenshot_base64:
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{screenshot_base64}"
            }
        })
    
    return content_parts


def build_verification_message(
    verification_prompt: str,
    focus_diff: str,
    tree_diff: str,
    screenshot_base64: str = "",
) -> dict:
    """构建统一验证消息
    
    Args:
        verification_prompt: 验证标准描述
        focus_diff: 聚焦元素变化描述
        tree_diff: 无障碍树差异摘要
        screenshot_base64: 截图的 base64 编码（可选）
    
    Returns:
        完整的消息字典
    """
    content = build_verification_prompt(
        verification_prompt,
        focus_diff,
        tree_diff,
        screenshot_base64,
    )
    
    return {"role": "user", "content": content}


__all__ = [
    "VERIFICATION_PROMPT",
    "build_verification_prompt",
    "build_verification_message",
]