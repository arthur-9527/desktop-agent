#!/usr/bin/env python3
"""
视觉定位独立测试脚本
=====================
测试 _call_vision_for_grounding 的完整链路：
1. 读取本地截图 → Base64 编码
2. 调用 UI-TARS 视觉模型
3. 记录视觉大模型原始输出
4. 标准化坐标格式
5. 解析像素坐标
6. 转换为归一化坐标 (0-1000)

用法:
    python test_vision_grounding.py
"""

import asyncio
import base64
import os
import re
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()


def build_vision_grounding_prompt(target_description: str) -> str:
    """构建视觉定位 prompt（与 agent_loop.py 保持一致）"""
    return f"""Please locate the following target element based on the screenshot:

{target_description}

## Task

1. Locate the target element in the screenshot
2. If found, return the center coordinates of the element using `<point>x y</point>` format
3. Briefly describe the element you see and its position

!!! VERY IMPORTANT !!! Carefully distinguish between similar elements (e.g. address bar vs search bar in a browser). The one with a magnifying glass icon is usually the search bar. If the target is NOT visible, respond with "Target not found".
"""


def normalize_point_format(text: str) -> str:
    """标准化坐标格式（与 agent_loop.py 保持一致）
    
    支持的 UI-TARS 特有格式：
    - <point x1="X" y1="Y"> -> <point>X Y</point>
    - <points x1='X,Y' alt='...'> -> <point>X Y</point>
    - <point>x1='X,Y'</point> -> <point>X Y</point>
    - <point>x1(X,Y)</point> -> <point>X Y</point>
    """
    changed = False
    
    # 1. 匹配 <point x1="X" y1="Y"> 格式
    pattern1 = r'<point\s+x1="(\d+)"\s+y1="(\d+)"[^>]*>'
    def replace_point1(match):
        nonlocal changed
        changed = True
        return f'<point>{match.group(1)} {match.group(2)}</point>'
    text = re.sub(pattern1, replace_point1, text)
    
    # 2. 匹配 <points x1='X,Y' alt='...'> 或 <points x1="X,Y" alt="..."> 格式（UI-TARS 特有，支持单引号/双引号）
    pattern2 = r"<points\s+x1=['\"](\d+),(\d+)['\"][^>]*>"
    def replace_points(match):
        nonlocal changed
        changed = True
        return f'<point>{match.group(1)} {match.group(2)}</point>'
    text = re.sub(pattern2, replace_points, text)
    
    # 3. 匹配 <point>x1='X,Y'</point> 格式（UI-TARS 特有）
    pattern3 = r"<point>x1='(\d+),(\d+)'"
    def replace_point_text_quote(match):
        nonlocal changed
        changed = True
        return f'<point>{match.group(1)} {match.group(2)}'
    text = re.sub(pattern3, replace_point_text_quote, text)
    
    # 4. 匹配 <point>x1(X,Y)</point> 格式（UI-TARS 特有）
    pattern4 = r"<point>x1\((\d+),(\d+)\)"
    def replace_point_paren(match):
        nonlocal changed
        changed = True
        return f'<point>{match.group(1)} {match.group(2)}'
    text = re.sub(pattern4, replace_point_paren, text)
    
    # 5. 匹配 <point>(X,Y)</point> 格式（UI-TARS 特有，括号包裹坐标）
    pattern5 = r"<point>\((\d+),(\d+)\)"
    def replace_bracket_point(match):
        nonlocal changed
        changed = True
        return f'<point>{match.group(1)} {match.group(2)}'
    text = re.sub(pattern5, replace_bracket_point, text)
    
    # 6. 匹配裸括号格式 (X,Y) - 不在任何 XML 标签内时作为兜底
    if not changed:
        pattern6 = r'(?:^|\s)\((\d+),(\d+)\)(?:\s|$)'
        def replace_bare_bracket(match):
            nonlocal changed
            changed = True
            return f' <point>{match.group(1)} {match.group(2)}</point> '
        text = re.sub(pattern6, replace_bare_bracket, text)
    
    if changed:
        print(f"[Vision]   ↳ 坐标格式已标准化: <point x1=\"...\" y1=\"...\"> → <point>x y</point>")
    else:
        print(f"[Vision]   ↳ 格式无需标准化（已是 <point>x y</point> 格式）")
    return text


def parse_pixel_coordinates(text: str) -> tuple:
    """从文本解析像素坐标（与 agent_loop.py 保持一致）
    
    支持格式：
    - <point>X Y</point>（标准化后的标准格式）
    - <point X Y...>（备用格式）
    """
    # 匹配 <point>X Y</point> 或 <point X Y...> 格式
    # 标准化后: <point>692 104</point> -> 尾随 < 来自 </point>
    # 未标准化: <point 692 104...</point> -> 尾随空格
    match = re.search(r'<point[>\s]+(\d+)\s+(\d+)(?:[<\s/]|$)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    # 尝试 <point x1="..." y1="..."> 格式
    match = re.search(r'<point\s+x1="(\d+)"\s+y1="(\d+)"[^>]*>', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def pixel_to_normalized(pixel_x: int, pixel_y: int, max_width: int = 1366, max_height: int = 768) -> tuple:
    """将像素坐标转换为归一化坐标 (0-1000)（与 agent_loop.py 保持一致）"""
    normalized_x = int(pixel_x * 1000 / max_width)
    normalized_y = int(pixel_y * 1000 / max_height)
    return normalized_x, normalized_y


async def test_vision_grounding():
    """测试视觉定位完整链路"""
    
    # ====== 配置 ======
    vision_base_url = os.getenv("VISION_BASE_URL", "http://localhost:8889/v1")
    vision_api_key = os.getenv("VISION_API_KEY", "sk-dummy")
    vision_model = os.getenv("VISION_MODEL", "ui-tars")
    max_width = int(os.getenv("SCREENSHOT_MAX_WIDTH", "1366"))
    max_height = int(os.getenv("SCREENSHOT_MAX_HEIGHT", "768"))
    
    # 测试截图路径
    screenshot_path = os.path.join(os.path.dirname(__file__), "screenshot_clean.jpg")
    
    # 用户提供的提示词
    target_description = "B站页面顶部的搜索框，位于页面顶部中央偏右位置，是一个白色的长条形输入框，右侧有一个橙色的搜索按钮"
    
    print("=" * 70)
    print("视觉定位（Vision Grounding）独立测试")
    print("=" * 70)
    print(f"[配置] 视觉模型: {vision_model}")
    print(f"[配置] Base URL: {vision_base_url}")
    print(f"[配置] 截图尺寸: {max_width}x{max_height}")
    print(f"[配置] 截图文件: {screenshot_path}")
    print()
    
    # ====== Step 1: 读取截图并 Base64 编码 ======
    print("[Step 1] 读取截图并编码为 Base64")
    if not os.path.exists(screenshot_path):
        print(f"  ❌ 截图文件不存在: {screenshot_path}")
        return
    
    with open(screenshot_path, "rb") as f:
        image_data = f.read()
    base64_data = base64.b64encode(image_data).decode("utf-8")
    print(f"  ✓ 截图大小: {len(image_data)} bytes")
    print(f"  ✓ Base64 长度: {len(base64_data)} chars")
    print()
    
    # ====== Step 2: 构建 prompt ======
    print("[Step 2] 构建视觉定位 prompt")
    vision_prompt = build_vision_grounding_prompt(target_description)
    print(f"  ✓ Prompt 内容:")
    print(f"    ┌{'─'*60}┐")
    for line in vision_prompt.strip().split('\n'):
        print(f"    │ {line}")
    print(f"    └{'─'*60}┘")
    print()
    
    # ====== Step 3: 调用 UI-TARS ======
    print("[Step 3] 调用 UI-TARS 视觉模型...")
    print(f"  → 发送请求...")
    
    client = AsyncOpenAI(
        base_url=vision_base_url,
        api_key=vision_api_key,
    )
    
    try:
        response = await client.chat.completions.create(
            model=vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_data}"
                            }
                        },
                        {
                            "type": "text",
                            "text": vision_prompt
                        }
                    ]
                }
            ],
            max_tokens=256,
        )
        
        result = response.choices[0].message.content or ""
        finish_reason = getattr(response.choices[0], 'finish_reason', 'unknown')
        
        # 记录 Token 使用情况
        usage = getattr(response, 'usage', None)
        if usage:
            print(f"  ✓ Token 使用: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
        else:
            print(f"  ⚠ Token 使用: 未返回（模型不支持或未配置）")
        
        print(f"  ✓ finish_reason: {finish_reason}")
        print()
        
        # ====== Step 4: 记录视觉大模型原始输出 ======
        print("[Step 4] 视觉大模型原始输出")
        print(f"  ┌{'─'*60}┐")
        for line in result.strip().split('\n'):
            print(f"  │ {line}")
        print(f"  └{'─'*60}┘")
        print()
        
        # 提取原始坐标标签
        raw_point_matches = re.findall(r'<point[^>]*>', result)
        print(f"[Step 4.1] 原始坐标标签提取")
        if raw_point_matches:
            for tag in raw_point_matches:
                print(f"  ✓ 发现坐标标签: {tag}")
        else:
            print(f"  ❌ 未发现坐标标签")
        print()
        
        # ====== Step 5: 标准化坐标格式 ======
        print("[Step 5] 标准化坐标格式")
        result_normalized = normalize_point_format(result)
        print()
        
        # ====== Step 6: 解析像素坐标 ======
        print("[Step 6] 解析像素坐标")
        pixel_x, pixel_y = parse_pixel_coordinates(result_normalized)
        print(f"  pixel_x = {pixel_x}")
        print(f"  pixel_y = {pixel_y}")
        
        if pixel_x is not None and pixel_y is not None:
            print(f"  ✓ 成功解析像素坐标: ({pixel_x}, {pixel_y})")
        else:
            print(f"  ❌ 未能解析出像素坐标")
            # 尝试从原始输出中提取
            alt_matches = re.findall(r'(\d+)[\s,]+(\d+)', result)
            print(f"  → 原始输出中的数字对: {alt_matches}")
        print()
        
        # ====== Step 7: 转换为归一化坐标 ======
        print("[Step 7] 转换为归一化坐标 (0-1000)")
        if pixel_x is not None and pixel_y is not None:
            calc_x_expr = f"{pixel_x} × 1000 ÷ {max_width}"
            calc_y_expr = f"{pixel_y} × 1000 ÷ {max_height}"
            calc_x_result = int(pixel_x * 1000 / max_width)
            calc_y_result = int(pixel_y * 1000 / max_height)
            
            print(f"  x: {calc_x_expr} = {calc_x_result}")
            print(f"  y: {calc_y_expr} = {calc_y_result}")
            
            normalized_x, normalized_y = pixel_to_normalized(pixel_x, pixel_y, max_width, max_height)
            print(f"  ✓ 归一化坐标: ({normalized_x}, {normalized_y})")
            
            # 最终结果
            final_result = f"目标已定位: 归一化坐标 ({normalized_x}, {normalized_y})"
            print()
            print(f"[最终结果] {final_result}")
        else:
            print(f"  ❌ 无法计算归一化坐标（像素坐标缺失）")
            final_result = result_normalized
        
        print()
        print("=" * 70)
        print("测试完成")
        print("=" * 70)
        
    except Exception as e:
        print(f"  ❌ API 调用失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_vision_grounding())