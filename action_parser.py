"""
动作解析器 - 解析 LLM 输出的 Thought/Action 格式
参考 UI-TARS 格式
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 支持的 action 类型
SUPPORTED_ACTIONS = [
    "click",
    "double_click",
    "right_click",
    "drag",
    "hotkey",
    "type",
    "scroll",
    "wait",
    "finished",
]

# Action 参数模式
POINT_PATTERN = r"point='<point>(\d+)\s+(\d+)</point>'"
START_POINT_PATTERN = r"start_point='<point>(\d+)\s+(\d+)</point>'"
END_POINT_PATTERN = r"end_point='<point>(\d+)\s+(\d+)</point>'"
KEY_PATTERN = r"key='([^']+?)'[\s\)]"
CONTENT_PATTERN = r"content='([^']+?)'[\s\)]"
DIRECTION_PATTERN = r"direction='(up|down|left|right)'"



class ParsedAction:
    """解析后的动作"""

    def __init__(
        self,
        action: str,
        thought: str = "",
        point: Optional[tuple] = None,
        start_point: Optional[tuple] = None,
        end_point: Optional[tuple] = None,
        key: Optional[str] = None,
        text: Optional[str] = None,
        direction: Optional[str] = None,
        finished: bool = False,
    ):
        self.action = action
        self.thought = thought
        self.point = point  # (x, y)
        self.start_point = start_point
        self.end_point = end_point
        self.key = key
        self.text = text
        self.direction = direction
        self.finished = finished

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "thought": self.thought,
            "point": self.point,
            "start_point": self.start_point,
            "end_point": self.end_point,
            "key": self.key,
            "text": self.text,
            "direction": self.direction,
            "finished": self.finished,
        }

    def __repr__(self):
        return f"ParsedAction(action={self.action}, point={self.point}, key={self.key}, text={self.text})"


class ActionParser:
    """解析 LLM 输出的 Thought/Action 格式"""

    def parse(self, llm_output: str) -> ParsedAction:
        """
        解析 LLM 输出

        输入格式示例:
        Thought: 我需要点击确定按钮
        Action: click
        point='<point>100 200</point>'

        返回:
        ParsedAction(action='click', thought='我需要点击确定按钮', point=(100, 200))
        """
        thought = ""
        action = ""
        point = None
        start_point = None
        end_point = None
        key = None
        text = None
        direction = None

        # 提取 Thought
        thought_match = re.search(r"Thought:\s*(.+)", llm_output, re.IGNORECASE)
        if thought_match:
            thought = thought_match.group(1).strip()

        # 提取 Action
        action_match = re.search(r"Action:\s*(\w+)", llm_output, re.IGNORECASE)
        if action_match:
            action = action_match.group(1).lower().strip()
        else:
            # 尝试提取 Action: 格式 (如 "Action: click(point='...')")
            action_pattern = r"Action:\s*(\w+)"
            action_match = re.search(action_pattern, llm_output, re.IGNORECASE)
            if action_match:
                action = action_match.group(1).lower().strip()

        # 判断是否完成任务
        finished = "finished" in llm_output.lower()

        # 提取参数
        point_match = re.search(POINT_PATTERN, llm_output)
        if point_match:
            point = (int(point_match.group(1)), int(point_match.group(2)))

        start_match = re.search(START_POINT_PATTERN, llm_output)
        end_match = re.search(END_POINT_PATTERN, llm_output)
        if start_match and end_match:
            start_point = (int(start_match.group(1)), int(start_match.group(2)))
            end_point = (int(end_match.group(1)), int(end_match.group(2)))

        key_match = re.search(KEY_PATTERN, llm_output)
        if key_match:
            key = key_match.group(1).strip().lower()

        content_match = re.search(CONTENT_PATTERN, llm_output)
        if content_match:
            text = content_match.group(1).strip()

        direction_match = re.search(DIRECTION_PATTERN, llm_output)
        if direction_match:
            direction = direction_match.group(1)

        # 尝试另一种格式: click(point='<point>x y</point>')
        if not action and point:
            action_pattern = r"(\w+)\s*\(\s*point='<point>\d+\s+\d+</point>'"
            action_match = re.search(action_pattern, llm_output)
            if action_match:
                action = action_match.group(1).lower().strip()

        # 尝试解析快捷键格式: hotkey(key='ctrl c')
        if not action:
            hotkey_pattern = r"hotkey\s*\(\s*key='([^']+)'"
            hotkey_match = re.search(hotkey_pattern, llm_output)
            if hotkey_match:
                action = "hotkey"
                key = hotkey_match.group(1).strip().lower()

        # 尝试解析输入格式: type(content='xxx')
        if not action:
            type_pattern = r"type\s*\(\s*content='([^']+)' "
            type_match = re.search(type_pattern, llm_output)
            if type_match:
                action = "type"
                text = type_match.group(1).strip()

        # 尝试解析滚动格式: scroll(point='<point>x y</point>', direction='...')
        if not action:
            scroll_pattern = r"scroll\s*\(\s*point='<point>\d+\s+\d+</point>'\s*,\s*direction='(up|down|left|right)'"
            scroll_match = re.search(scroll_pattern, llm_output)
            if scroll_match:
                action = "scroll"
                direction = scroll_match.group(1)
                point_match = re.search(POINT_PATTERN, llm_output)
                if point_match:
                    point = (
                        int(point_match.group(1)),
                        int(point_match.group(2)),
                    )

        # 验证 action
        if action and action not in SUPPORTED_ACTIONS:
            logger.warning(f"Unknown action: {action}, defaulting to 'wait'")
            action = "wait"

        # 如果没有解析到 action，默认为 wait
        if not action:
            action = "wait"

        return ParsedAction(
            action=action,
            thought=thought,
            point=point,
            start_point=start_point,
            end_point=end_point,
            key=key,
            text=text,
            direction=direction,
            finished=finished,
        )

    def execute(self, parsed: ParsedAction) -> dict:
        """
        将解析后的动作转换为可执行的操作
        返回: {
            "action": "动作类型",
            "params": { ... },
            "description": "描述"
        }
        """
        action_map = {
            "click": lambda p: {
                "action": "mouse_left_click",
                "params": {"x": p.point[0] if p.point else None, "y": p.point[1] if p.point else None} if p.point else None,
                "description": f"点击 ({p.point})" if p.point else "点击",
            },
            "double_click": lambda p: {
                "action": "mouse_double_click",
                "params": {"x": p.point[0] if p.point else None, "y": p.point[1] if p.point else None} if p.point else None,
                "description": f"双击 ({p.point})" if p.point else "双击",
            },
            "right_click": lambda p: {
                "action": "mouse_right_click",
                "params": {"x": p.point[0] if p.point else None, "y": p.point[1] if p.point else None} if p.point else None,
                "description": f"右键 ({p.point})" if p.point else "右键",
            },
            "drag": lambda p: {
                "action": "mouse_drag",
                "params": {
                    "start_x": p.start_point[0] if p.start_point else None,
                    "start_y": p.start_point[1] if p.start_point else None,
                    "end_x": p.end_point[0] if p.end_point else None,
                    "end_y": p.end_point[1] if p.end_point else None,
                },
                "description": f"拖拽 ({p.start_point} → {p.end_point})" if p.start_point and p.end_point else "拖拽",
            },
            "hotkey": lambda p: {
                "action": "keyboard_hotkey",
                "params": {"keys": self._parse_key(p.key) if p.key else []},
                "description": f"快捷键: {p.key}" if p.key else "快捷键",
            },
            "type": lambda p: {
                "action": "keyboard_type",
                "params": {"text": p.text if p.text else ""},
                "description": f"输入: {p.text}" if p.text else "输入文本",
            },
            "scroll": lambda p: {
                "action": "mouse_scroll",
                "params": {"direction": p.direction or "down", "amount": 1},
                "description": f"滚动 ({p.direction})" if p.direction else "滚动",
            },
            "wait": lambda p: {
                "action": "wait",
                "params": {"delay": 1},
                "description": "等待",
            },
            "finished": lambda p: {
                "action": "finished",
                "params": {"message": p.text if p.text else "任务完成"},
                "description": "任务完成",
            },
        }

        if parsed.action not in action_map:
            return {"action": "wait", "params": {"delay": 1}, "description": "未知动作，等待"}

        result = action_map[parsed.action](parsed)
        if parsed.thought:
            result["thought"] = parsed.thought
        return result

    def _parse_key(self, key_str: str) -> list:
        """解析快捷键字符串，如 'ctrl c' → ['ControlLeft', 'C']"""
        if not key_str:
            return []

        key_map = {
            "ctrl": "ControlLeft",
            "control": "ControlLeft",
            "alt": "AltLeft",
            "shift": "ShiftLeft",
            "win": "LeftWin",
            "meta": "LeftWin",
            "cmd": "LeftWin",
            "super": "LeftWin",
            "command": "LeftWin",
            "r": "R",
            "f1": "F1",
            "f2": "F2",
            "f3": "F3",
            "f4": "F4",
            "f5": "F5",
            "f6": "F6",
            "f7": "F7",
            "f8": "F8",
            "f9": "F9",
            "f10": "F10",
            "f11": "F11",
            "f12": "F12",
            "enter": "Enter",
            "escape": "Escape",
            "tab": "Tab",
            "space": "Space",
            "backspace": "Backspace",
            "delete": "Delete",
            "left": "ArrowLeft",
            "right": "ArrowRight",
            "up": "ArrowUp",
            "down": "ArrowDown",
        }

        keys = key_str.lower().split()
        result = []
        for key in keys:
            mapped = key_map.get(key, key.upper())
            result.append(mapped)
        return result