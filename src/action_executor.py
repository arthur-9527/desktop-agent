"""动作解析与执行模块"""

import asyncio
import re
from typing import Tuple, Optional, List

from .agentdesk_client import AgentDeskClient


class KeyMapper:
    """按键映射器，根据操作系统转换按键名称
    
    LLM 输出格式: hotkey(key='ctrl c')
    AgentDesk 接受格式: {"action": "press", "keys": ["ControlLeft", "C"]}
    """
    
    # 通用映射（三个系统相同）
    COMMON_MAP = {
        "ctrl": "ControlLeft",
        "control": "ControlLeft",
        "alt": "AltLeft",
        "shift": "ShiftLeft",
        "enter": "Enter",
        "return": "Enter",
        "tab": "Tab",
        "space": "Space",
        "backspace": "Backspace",
        "delete": "Delete",
        "del": "Delete",
        "esc": "Escape",
        "escape": "Escape",
        "up": "ArrowUp",
        "down": "ArrowDown",
        "left": "ArrowLeft",
        "right": "ArrowRight",
        "home": "Home",
        "end": "End",
        "pageup": "PageUp",
        "pagedown": "PageDown",
        "pgup": "PageUp",
        "pgdn": "PageDown",
        "insert": "Insert",
        "ins": "Insert",
        "capslock": "CapsLock",
        "numlock": "NumLock",
        "scrolllock": "ScrollLock",
        "printscreen": "PrintScreen",
        "prtsc": "PrintScreen",
        "pause": "Pause",
        "break": "Pause",
    }
    
    # Windows 特有映射
    WINDOWS_MAP = {
        "win": "LeftWin",
        "meta": "LeftWin",
        "cmd": "LeftWin",
        "super": "LeftWin",
    }
    
    # macOS 特有映射
    MACOS_MAP = {
        "win": "LeftCmd",
        "meta": "LeftCmd",
        "cmd": "LeftCmd",
        "super": "LeftCmd",
        "command": "LeftCmd",
        "option": "AltLeft",
    }
    
    # Linux 特有映射
    LINUX_MAP = {
        "win": "MetaLeft",
        "meta": "MetaLeft",
        "cmd": "MetaLeft",
        "super": "MetaLeft",
    }
    
    def __init__(self, os_type: str = "Windows"):
        """初始化按键映射器
        
        Args:
            os_type: 操作系统类型 Windows / macOS / Linux
        """
        self.os_type = os_type
    
    def normalize(self, key: str) -> str:
        """将 LLM 输出的按键名转换为 AgentDesk 接受的格式
        
        Args:
            key: LLM 输出的按键名，如 'ctrl', 'c', 'enter'
            
        Returns:
            AgentDesk 接受的按键名，如 'ControlLeft', 'C', 'Enter'
        """
        key_lower = key.lower()
        
        # 1. 通用映射
        if key_lower in self.COMMON_MAP:
            return self.COMMON_MAP[key_lower]
        
        # 2. 系统特定映射
        os_map = {
            "Windows": self.WINDOWS_MAP,
            "macOS": self.MACOS_MAP,
            "Linux": self.LINUX_MAP,
        }
        system_map = os_map.get(self.os_type, self.WINDOWS_MAP)
        if key_lower in system_map:
            return system_map[key_lower]
        
        # 3. 功能键 F1-F24
        if key_lower.startswith("f") and key_lower[1:].isdigit():
            fnum = int(key_lower[1:])
            if 1 <= fnum <= 24:
                return key.upper()
        
        # 4. 单字母转大写
        if len(key) == 1 and key.isalpha():
            return key.upper()
        
        # 5. 单数字
        if len(key) == 1 and key.isdigit():
            return key
        
        # 其他情况原样返回
        return key
    
    def normalize_keys(self, keys: List[str]) -> List[str]:
        """批量转换按键列表
        
        Args:
            keys: 按键列表，如 ['ctrl', 'c']
            
        Returns:
            转换后的按键列表，如 ['ControlLeft', 'C']
        """
        return [self.normalize(k) for k in keys]


class ActionExecutor:
    """动作解析与执行器

    UI-TARS 1.5 输出 0-1000 归一化坐标，与 AgentDesk 坐标系一致，无需换算。
    快捷键需要根据操作系统类型进行转换。
    """

    def __init__(self, client: AgentDeskClient, os_type: str = "Windows"):
        self.client = client
        self.os_type = os_type
        self.key_mapper = KeyMapper(os_type)
    
    def update_os(self, os_type: str):
        """更新操作系统类型
        
        Args:
            os_type: 操作系统类型 Windows / macOS / Linux
        """
        if os_type != self.os_type:
            self.os_type = os_type
            self.key_mapper = KeyMapper(os_type)
            print(f"[KeyMapper] 操作系统更新为: {os_type}")

    def parse(self, model_output: str) -> dict:
        """解析 UI-TARS 模型输出

        Args:
            model_output: 模型原始输出文本

        Returns:
            解析后的动作字典，包含 action_type 和 action_inputs
        """
        # 尝试使用官方解析器
        try:
            from ui_tars.action_parser import parse_action_to_structure_output
            result = parse_action_to_structure_output(
                model_output,
                factor=1,
                origin_resized_height=768,
                origin_resized_width=1366,
                model_type="UI-TARS-1.5-7B",
            )
            # parse_action_to_structure_output 返回 list，取第一个
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return {"action_type": "wait", "action_inputs": {}}
        except ImportError:
            # 如果官方包不可用，使用简化解析
            return self._simple_parse(model_output)

    def _simple_parse(self, output: str) -> dict:
        """简化的动作解析器（备用）"""
        output = output.strip()

        # finished 动作
        if "finished" in output.lower():
            match = re.search(r"finished\s*\(\s*content\s*=\s*['\"](.+?)['\"]\s*\)", output, re.IGNORECASE)
            content = match.group(1) if match else "Task completed"
            return {"action_type": "finished", "action_inputs": {"content": content}}

        # wait 动作
        if "wait" in output.lower():
            return {"action_type": "wait", "action_inputs": {}}

        # click 动作
        if "click" in output.lower():
            coords = self._extract_point(output)
            if coords:
                return {"action_type": "click", "action_inputs": {"start_box": str(list(coords))}}

        # left_double 动作
        if "left_double" in output.lower() or "double" in output.lower():
            coords = self._extract_point(output)
            if coords:
                return {"action_type": "left_double", "action_inputs": {"start_box": str(list(coords))}}

        # right_single 动作
        if "right_single" in output.lower() or "right" in output.lower():
            coords = self._extract_point(output)
            if coords:
                return {"action_type": "right_single", "action_inputs": {"start_box": str(list(coords))}}

        # drag 动作
        if "drag" in output.lower():
            start = self._extract_point(output, "start_point")
            end = self._extract_point(output, "end_point") or self._extract_point(output)
            if start and end:
                return {
                    "action_type": "drag",
                    "action_inputs": {
                        "start_box": str(list(start)),
                        "end_box": str(list(end))
                    }
                }

        # scroll 动作
        if "scroll" in output.lower():
            direction = "down"
            if "up" in output.lower():
                direction = "up"
            elif "left" in output.lower():
                direction = "left"
            elif "right" in output.lower():
                direction = "right"
            return {"action_type": "scroll", "action_inputs": {"direction": direction}}

        # type 动作
        if "type" in output.lower():
            match = re.search(r"type\s*\(\s*content\s*=\s*['\"](.+?)['\"]\s*\)", output, re.IGNORECASE | re.DOTALL)
            if match:
                return {"action_type": "type", "action_inputs": {"content": match.group(1)}}

        # hotkey 动作
        if "hotkey" in output.lower():
            match = re.search(r"hotkey\s*\(\s*key\s*=\s*['\"](.+?)['\"]\s*\)", output, re.IGNORECASE)
            if match:
                return {"action_type": "hotkey", "action_inputs": {"key": match.group(1)}}

        # 默认返回 wait
        return {"action_type": "wait", "action_inputs": {}}

    def _extract_point(self, text: str, key: str = "point") -> Optional[Tuple[float, float]]:
        """从文本中提取坐标点

        Args:
            text: 包含坐标的文本
            key: "point" 返回第一个点，"start_point" 返回第一个点，"end_point" 返回第二个点

        Returns:
            (x, y) 坐标元组，或 None
        """
        # 找到所有 <point>x y</point> 格式的坐标
        point_pattern = r"<point>\s*(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*</point>"
        points = re.findall(point_pattern, text)

        if points:
            if key == "end_point" and len(points) >= 2:
                # drag 的终点是第二个点
                return (float(points[1][0]), float(points[1][1]))
            elif points:
                # 默认返回第一个点
                return (float(points[0][0]), float(points[0][1]))

        # 尝试匹配 [x, y] 格式
        bracket_pattern = r"\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]"
        brackets = re.findall(bracket_pattern, text)
        if brackets:
            if key == "end_point" and len(brackets) >= 2:
                return (float(brackets[1][0]), float(brackets[1][1]))
            elif brackets:
                return (float(brackets[0][0]), float(brackets[0][1]))

        # 尝试匹配 (x, y) 格式
        paren_pattern = r"\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)"
        parens = re.findall(paren_pattern, text)
        if parens:
            if key == "end_point" and len(parens) >= 2:
                return (float(parens[1][0]), float(parens[1][1]))
            elif parens:
                return (float(parens[0][0]), float(parens[0][1]))

        return None

    async def execute(self, parsed: dict):
        """执行单个动作

        Args:
            parsed: 解析后的动作字典
        """
        action_type = parsed.get("action_type", "wait")
        inputs = parsed.get("action_inputs", {})

        if action_type == "click":
            x, y = self._get_coords(inputs)
            await self.client.mouse_click(x=int(x), y=int(y))

        elif action_type == "left_double":
            x, y = self._get_coords(inputs)
            await self.client.mouse_click(button="double", x=int(x), y=int(y))

        elif action_type == "right_single":
            x, y = self._get_coords(inputs)
            await self.client.mouse_click(button="right", x=int(x), y=int(y))

        elif action_type == "drag":
            x1, y1 = self._get_coords(inputs, key="start_box")
            x2, y2 = self._get_coords(inputs, key="end_box")
            # press_left → drag → release_left（三步）
            await self.client.mouse_down()
            await self.client.mouse_drag(int(x2), int(y2))
            await self.client.mouse_up()

        elif action_type == "scroll":
            await self.client.mouse_scroll(
                direction=inputs.get("direction", "down"),
                amount=1,
            )

        elif action_type == "type":
            await self.client.keyboard_type(inputs["content"])

        elif action_type == "hotkey":
            # 使用 KeyMapper 转换按键名称
            raw_keys = inputs.get("key", "").split()  # 官方格式: "ctrl c"
            if raw_keys:
                keys = self.key_mapper.normalize_keys(raw_keys)
                print(f"[Hotkey] {raw_keys} -> {keys}")
                await self.client.keyboard_hotkey(*keys)

        elif action_type == "wait":
            await asyncio.sleep(5)

        elif action_type == "finished":
            # 任务完成，无需执行动作
            pass

        else:
            print(f"未知动作类型: {action_type}")

    def _get_coords(self, inputs: dict, key: str = "start_box") -> Tuple[float, float]:
        """从解析后的 action_inputs 提取坐标（已是 0-1000 归一化）

        Args:
            inputs: action_inputs 字典
            key: 坐标键名

        Returns:
            (x, y) 坐标元组
        """
        coords_str = inputs.get(key, "[500, 500]")

        # 尝试解析列表格式
        if isinstance(coords_str, str):
            nums = re.findall(r"[\d.]+", coords_str)
            if len(nums) >= 2:
                return (float(nums[0]), float(nums[1]))
        elif isinstance(coords_str, (list, tuple)) and len(coords_str) >= 2:
            return (float(coords_str[0]), float(coords_str[1]))

        return (500.0, 500.0)