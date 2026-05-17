#!/usr/bin/env python3
"""
稳定性测试：连续10次调用 UI-TARS 定位 YouTube 搜索框
使用中文 prompt + JSON 格式输出
"""

import asyncio
import base64
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()


def build_vision_grounding_prompt(target_description: str) -> str:
    return f"""请根据截图定位以下目标元素：

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

如果未找到目标，输出：
{{
    "found": false,
    "desc": "未找到目标"
}}
"""


async def main():
    vision_base_url = os.getenv("VISION_BASE_URL", "http://localhost:8890/v1")
    vision_api_key = os.getenv("VISION_API_KEY", "sk-dummy")
    vision_model = os.getenv("VISION_MODEL", "ui-tars")

    screenshot_path = os.path.join(os.path.dirname(__file__), "screenshot_now.jpg")

    target_description = (
        "YouTube 页面顶部中央的搜索框，是一个长条形的白色输入框，"
        "里面有'搜索'占位符文字，右侧有搜索按钮和麦克风图标"
    )

    if not os.path.exists(screenshot_path):
        print(f"❌ 截图文件不存在: {screenshot_path}")
        return

    with open(screenshot_path, "rb") as f:
        image_data = f.read()
    base64_data = base64.b64encode(image_data).decode("utf-8")

    vision_prompt = build_vision_grounding_prompt(target_description)

    print("=" * 70)
    print(f"YouTube 搜索框视觉定位稳定性测试 (10次) — 中文prompt + JSON")
    print(f"模型: {vision_model}")
    print(f"截图尺寸: 1366x768")
    print("=" * 70)
    print()

    results = []
    client = AsyncOpenAI(base_url=vision_base_url, api_key=vision_api_key)

    for i in range(10):
        try:
            response = await client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_data}"}},
                            {"type": "text", "text": vision_prompt}
                        ]
                    }
                ],
                max_tokens=256,
            )

            result = response.choices[0].message.content or ""
            usage = getattr(response, 'usage', None)
            token_info = f"t={usage.total_tokens}" if usage else "t=?"

            print(f"[{i+1:2d}/10] {result.strip()}")
            results.append(result.strip())

        except Exception as e:
            print(f"[{i+1:2d}/10] ❌ ERROR: {e}")
            results.append(f"ERROR: {e}")

    print()
    print("=" * 70)
    print("  所有10次原始输出汇总:")
    print("=" * 70)
    for i, r in enumerate(results, 1):
        print(f"  [{i:2d}] {r}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())