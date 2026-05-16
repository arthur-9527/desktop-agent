#!/usr/bin/env python3
"""
批量视觉定位测试 - 运行 N 次并汇总结果
"""
import asyncio
import base64
import os
import re
import sys
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

RUN_COUNT = 10
screenshot_path = os.path.join(os.path.dirname(__file__), "screenshot_clean.jpg")
vision_base_url = os.getenv("VISION_BASE_URL", "http://localhost:8889/v1")
vision_api_key = os.getenv("VISION_API_KEY", "sk-dummy")
vision_model = os.getenv("VISION_MODEL", "ui-tars")
max_width = int(os.getenv("SCREENSHOT_MAX_WIDTH", "1366"))
max_height = int(os.getenv("SCREENSHOT_MAX_HEIGHT", "768"))

target_description = "B站页面顶部的搜索框，位于页面顶部中央偏右位置，是一个白色的长条形输入框，右侧有一个橙色的搜索按钮"

PROMPT_TEMPLATE = f"""Please locate the following target element based on the screenshot:

{target_description}

## Task

1. Locate the target element in the screenshot
2. If found, return the center coordinates of the element using `<point>x y</point>` format
3. Briefly describe the element you see and its position

!!! VERY IMPORTANT !!! Carefully distinguish between similar elements (e.g. address bar vs search bar in a browser). The one with a magnifying glass icon is usually the search bar. If the target is NOT visible, respond with "Target not found".
"""


async def run_once(client, base64_data, run_id):
    """运行一次视觉定位测试"""
    try:
        response = await client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_data}"}},
                        {"type": "text", "text": PROMPT_TEMPLATE}
                    ]
                }
            ],
            max_tokens=256,
        )
        
        result = response.choices[0].message.content or ""
        usage = getattr(response, 'usage', None)
        tokens = usage.total_tokens if usage else 0
        
        # 提取数字对
        nums = re.findall(r'(\d+)[,\s]+(\d+)', result)
        
        # 提取完整原始输出（单行）
        raw_stripped = result.strip().replace('\n', ' ')[:120]
        
        return {
            "id": run_id,
            "raw": raw_stripped,
            "numbers": nums,
            "tokens": tokens,
            "success": len(nums) > 0
        }
    except Exception as e:
        return {
            "id": run_id,
            "raw": f"ERROR: {e}",
            "numbers": [],
            "tokens": 0,
            "success": False
        }


async def main():
    print("=" * 70)
    print(f"批量视觉定位测试 - 连续运行 {RUN_COUNT} 次")
    print(f"模型: {vision_model} | 截图: {screenshot_path}")
    print(f"目标: B站搜索框")
    print("=" * 70)
    
    # 读取截图
    with open(screenshot_path, "rb") as f:
        base64_data = base64.b64encode(f.read()).decode("utf-8")
    
    client = AsyncOpenAI(base_url=vision_base_url, api_key=vision_api_key)
    
    results = []
    for i in range(RUN_COUNT):
        print(f"\n[{i+1}/{RUN_COUNT}] 运行中...", end=" ", flush=True)
        r = await run_once(client, base64_data, i + 1)
        results.append(r)
        
        # 提取坐标
        coord_str = "❌ 无坐标"
        if r["numbers"]:
            nx = r["numbers"][0][0]
            ny = r["numbers"][0][1]
            norm_x = int(int(nx) * 1000 / max_width)
            norm_y = int(int(ny) * 1000 / max_height)
            coord_str = f"像素({nx},{ny}) → 归一化({norm_x},{norm_y})"
        
        print(f"[{r['tokens']}toks] {coord_str}")
    
    await client.close()
    
    # === 汇总 ===
    print("\n" + "=" * 70)
    print("汇总结果")
    print("=" * 70)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print(f"总运行: {RUN_COUNT}")
    print(f"成功提取坐标: {len(successful)}/{RUN_COUNT}")
    print(f"失败: {len(failed)}/{RUN_COUNT}")
    
    if successful:
        print("\n--- 输出格式统计 ---")
        formats = {}
        for r in successful:
            raw = r["raw"]
            if "points x1=" in raw:
                fmt = "<points x1='X,Y' alt='...'>"
            elif "x1=" in raw:
                fmt = "<point>x1='X,Y'</point>"
            elif "x1(" in raw:
                fmt = "<point>x1(X,Y)</point>"
            else:
                fmt = "其他"
            formats[fmt] = formats.get(fmt, 0) + 1
        
        for fmt, count in sorted(formats.items(), key=lambda x: -x[1]):
            bar = "█" * count + "░" * (RUN_COUNT - count)
            print(f"  {fmt:42s} {count:2d}次 {bar}")
        
        print("\n--- 坐标数值统计 ---")
        xs = []
        ys = []
        for r in successful:
            if r["numbers"]:
                xs.append(int(r["numbers"][0][0]))
                ys.append(int(r["numbers"][0][1]))
        
        print(f"  X: min={min(xs)}, max={max(xs)}, avg={sum(xs)//len(xs)}, 波动={max(xs)-min(xs)}px")
        print(f"  Y: min={min(ys)}, max={max(ys)}, avg={sum(ys)//len(ys)}, 波动={max(ys)-min(ys)}px")
        
        print("\n--- 归一化坐标范围 (0-1000) ---")
        norm_xs = [int(x * 1000 / max_width) for x in xs]
        norm_ys = [int(y * 1000 / max_height) for y in ys]
        print(f"  X: {min(norm_xs)} ~ {max(norm_xs)}")
        print(f"  Y: {min(norm_ys)} ~ {max(norm_ys)}")
        
        print("\n--- 全部输出 ---")
        for r in successful:
            print(f"  #{r['id']:2d}: {r['raw']}")
    
    if failed:
        print("\n--- 失败记录 ---")
        for r in failed:
            print(f"  #{r['id']:2d}: {r['raw']}")


if __name__ == "__main__":
    asyncio.run(main())