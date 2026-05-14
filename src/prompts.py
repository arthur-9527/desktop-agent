"""UI-TARS Prompt 模板"""

from ui_tars.prompt import COMPUTER_USE_DOUBAO

__all__ = ["COMPUTER_USE_DOUBAO", "SYSTEM_PROMPT"]

# 官方 prompt 已定义完整的 action space：
#   click(point='<point>x1 y1</point>')
#   left_double(point='<point>x1 y1</point>')
#   right_single(point='<point>x1 y1</point>')
#   drag(start_point='<point>x1 y1</point>', end_point='<point>x2 y2</point>')
#   hotkey(key='ctrl c')
#   type(content='xxx')          # 换行用 \n，提交表单在末尾加 \n
#   scroll(point='<point>x1 y1</point>', direction='down or up or right or left')
#   wait()                       # 等待 5s 后截图检查变化
#   finished(content='xxx')
#
# prompt 中 {language} 和 {instruction} 为占位符，运行时替换。


SYSTEM_PROMPT = COMPUTER_USE_DOUBAO


def build_system_prompt(task: str, language: str = "Chinese") -> str:
    """构建系统提示词

    Args:
        task: 任务描述
        language: 语言，默认中文

    Returns:
        完整的系统提示词
    """
    return COMPUTER_USE_DOUBAO.format(language=language, instruction=task)