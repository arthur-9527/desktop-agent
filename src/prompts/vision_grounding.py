"""视觉定位提示词（UI-TARS）"""


VISION_GROUNDING_PROMPT = """Please locate the following target element based on the screenshot:

{target_description}

## Task

1. Locate the target element in the screenshot
2. If found, return the center coordinates of the element (using `<point>x y</point>` format)
3. Briefly describe the element you see and its position
4. !!!VERY IMPORTANT!!! Please carefully distinguish between similar elements such as the address bar and search bar in the browser. The one with a magnifying glass icon is usually the search bar.

## Coordinate System

The screenshot uses a 0-1000 normalized coordinate system. The top-left corner is (0, 0), and the bottom-right corner is (1000, 1000).

## Grid Information

The screenshot has a grid overlay to help you locate elements precisely:
- **Large cells**: 4 columns × 4 rows = 16 large cells (thick red lines)
- **Small cells**: Each large cell is subdivided into 4×4 = 16 small cells (thin dashed lines)
- **Large cell size**: {large_cell_width} × {large_cell_height} pixels
- **Small cell size**: {small_cell_width} × {small_cell_height} pixels

Use the grid lines to estimate coordinates more accurately. First identify which large cell the target is in, then refine the position using the small cells.
"""


def build_vision_grounding_prompt(
    target_description: str,
    screenshot_width: int = 1024,
    screenshot_height: int = 768,
) -> str:
    """构建视觉定位提示词
    
    Args:
        target_description: 目标元素描述
        screenshot_width: 截图宽度（像素）
        screenshot_height: 截图高度（像素）
        
    Returns:
        完整的提示词
    """
    # 计算网格格子大小（grid level 64: 4x4 大格子，每个大格子 4x4 小格子）
    large_cell_width = screenshot_width // 4
    large_cell_height = screenshot_height // 4
    small_cell_width = large_cell_width // 4
    small_cell_height = large_cell_height // 4
    
    return VISION_GROUNDING_PROMPT.format(
        target_description=target_description,
        large_cell_width=large_cell_width,
        large_cell_height=large_cell_height,
        small_cell_width=small_cell_width,
        small_cell_height=small_cell_height,
    )


__all__ = ["VISION_GROUNDING_PROMPT", "build_vision_grounding_prompt"]