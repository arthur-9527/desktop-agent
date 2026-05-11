"""
LLM 客户端 - 封装 OpenAI 兼容的 API 调用
支持视觉模型 (ui-tars) 和通用模型 (qwopus-27b)
"""
import base64
import logging
from typing import Optional

import openai

from config import LLM_BASE_URL, LLM_API_KEY, GENERAL_MODEL, VISION_MODEL

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM 客户端，支持视觉分析和文本推理"""

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        general_model: str = None,
        vision_model: str = None,
    ):
        self.base_url = base_url or LLM_BASE_URL
        self.api_key = api_key or LLM_API_KEY
        self.general_model = general_model or GENERAL_MODEL
        self.vision_model = vision_model or VISION_MODEL

        self.client = openai.OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def _encode_image(self, image_bytes: bytes) -> str:
        """将图片转为 base64"""
        return base64.b64encode(image_bytes).decode("utf-8")

    # ============ 视觉模型 ============

    def analyze_state(
        self,
        image_bytes: bytes,
        prompt: str = None,
        focused_element: dict = None,
        accessibility_tree: dict = None,
        detected_os: str = None,
    ) -> str:
        """
        视觉模型分析当前界面状态
        返回: 界面状态描述

        Args:
            image_bytes: 截图的二进制数据
            prompt: 自定义提示词（可选）
            focused_element: 当前焦点元素信息（可选）
            accessibility_tree: 无障碍元素树（可选），用于识别窗口层级
            detected_os: 从无障碍树检测到的操作系统（可选），优先级最高
        """
        if prompt is None:
            prompt = (
                "请结合以下无障碍元素树和截图图片，分析当前界面状态：\n\n"
                "【系统环境】\n"
                "- 操作系统类型（Windows/Linux/macOS）\n"
                "- 桌面环境（如 GNOME/KDE/Windows 桌面等）\n"
                "- 当前时间（截图中的时间显示）\n\n"
                "【前台窗口】（无障碍树中的顶级窗口，即应用的主窗口）\n"
                "请列出所有检测到的顶级窗口（从上到下，视觉上越靠前越大的是前台窗口）：\n"
                "- 每个窗口的名称、角色（Window/对话框等）、状态（最大化/最小化/普通）\n\n"
                "【子窗口/面板】（每个顶级窗口内的子面板、标签页、工具栏等）\n"
                "- 例如：VSCode 窗口内有编辑器面板、终端面板、侧边栏等\n"
                "- 如果有对话框/弹窗，请特别标注\n\n"
                "【可交互元素】（从截图补充，无障碍树可能缺失）\n"
                "- 任务栏内容：开始菜单/应用图标/系统托盘等\n"
                "- 窗口内的按钮、输入框、菜单等\n"
                "- 光标位置和当前焦点\n\n"
                "【对话框/通知】\n"
                "- 是否有任何模态对话框、气泡通知或警告\n\n"
                "【与任务相关】\n"
                "- 完成用户任务需要点击或操作的关键元素位置\n\n"
                "请用中文回答，结构化输出。特别注意：前台窗口是整个屏幕上最前面的窗口，而非某个窗口内的子面板。"
            )

        # 追加系统权威信息和窗口层级结构
        extra_context = ""
        if detected_os:
            extra_context += f"【权威系统信息】\n操作系统: {detected_os}（以此为准）\n\n"

        if accessibility_tree and accessibility_tree.get("tree"):
            window_hierarchy = self._build_window_hierarchy(accessibility_tree["tree"])
            if window_hierarchy:
                extra_context += f"【窗口层级（无障碍树）】\n{window_hierarchy}\n\n"

        if extra_context:
            prompt = extra_context + prompt

        # 如果有焦点元素信息，添加到提示词中
        if focused_element and focused_element.get("element"):
            element = focused_element["element"]
            element_info = (
                f"\n\n【当前焦点元素信息】\n"
                f"- 元素角色: {element.get('role', '未知')}\n"
                f"- 元素名称: {element.get('name', '无')}\n"
                f"- 元素位置: x={element.get('bounds', {}).get('x', '未知')}, y={element.get('bounds', {}).get('y', '未知')}\n"
                f"- 元素大小: {element.get('bounds', {}).get('width', '未知')}x{element.get('bounds', {}).get('height', '未知')}\n"
            )
            prompt += element_info

        base64_image = self._encode_image(image_bytes)

        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个界面分析助手，擅长描述和理解当前屏幕状态。请用中文回答。",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low",
                            },
                        },
                    ],
                },
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        return response.choices[0].message.content

    def decide_action(
        self,
        image_bytes: bytes,
        instruction: str,
        action_history: list = None,
        accessibility_info: dict = None,
    ) -> str:
        """
        视觉模型决定下一个动作 (参考 UI-TARS 的 Thought/Action 格式)
        返回: LLM 输出的完整文本（需要外部 action_parser 解析）
        """
        if action_history is None:
            action_history = []

        history_text = ""
        if action_history:
            history_text = "\n历史操作:\n" + "\n".join(
                f"{i+1}. {h['action']}: {h['description']}"
                for i, h in enumerate(action_history[-5:])
            )

        # 构建无障碍树上下文
        tree_context = ""
        if accessibility_info and accessibility_info.get("tree"):
            top_windows = self._extract_top_windows(accessibility_info["tree"])
            if top_windows:
                tree_context = (
                    "\n【当前窗口（无障碍树）】\n"
                    "以下是从无障碍 API 提取的当前窗口列表（role + name）：\n"
                )
                for i, win in enumerate(top_windows, 1):
                    tree_context += f"  {i}. [{win['role']}] {win.get('name', '无标题')}\n"
                tree_context += (
                    "【重要】如果需要打开新窗口，请点击任务栏的应用图标，"
                    "而不是在当前窗口中输入命令。\n"
                )

        base64_image = self._encode_image(image_bytes)

        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个GUI自动化助手。你通过截图来理解当前界面，"
                        "并输出下一步操作。请严格按照以下格式输出：\n\n"
                        "Thought: [你的思考过程，简要说明当前状态和下一步计划]\n"
                        "Action: [动作类型]\n"
                        "[动作参数]\n\n"
                        "可用的动作类型：\n"
                        "1. click - 点击：需要 point 参数 (如 point='<point>100 200</point>')\n"
                        "2. double_click - 双击：需要 point 参数\n"
                        "3. right_click - 右键：需要 point 参数\n"
                        "4. drag - 拖拽：需要 start_point 和 end_point 参数\n"
                        "5. hotkey - 快捷键：需要 key 参数 (如 key='ctrl c'，多键用空格分隔)\n"
                        "6. type - 输入文本：需要 content 参数 (如 content='hello')\n"
                        "7. scroll - 滚动：需要 direction 参数 (up/down)\n"
                        "8. wait - 等待：无需参数\n"
                        "9. finished - 完成任务：可选 content 参数\n\n"
                        "【坐标说明】坐标使用截图上的像素坐标。\n"
                        "【快捷键格式】key='win r' 表示 Win+R，key='ctrl c' 表示 Ctrl+C。\n"
                        "【输入格式】content='要输入的文字'。\n\n"
                        "【关键规则】\n"
                        "- 打开应用：优先点击任务栏或桌面图标，不要在终端输入命令\n"
                        "- 输入文字前：必须确保焦点在目标窗口上（点击窗口激活）\n"
                        "- 执行操作后系统会自动截图验证，如果操作没有效果会重新规划\n"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"任务: {instruction}\n\n"
                            f"当前界面状态: 请分析当前截图，决定下一步操作。{history_text}{tree_context}\n\n"
                            f"请按照指定格式输出你的思考过程和动作。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low",
                            },
                        },
                    ],
                },
            ],
            max_tokens=512,
            temperature=0.3,
        )
        return response.choices[0].message.content

    def check_completion(self, image_bytes: bytes, task_description: str) -> bool:
        """
        视觉模型检查任务是否完成
        只有当截图明确显示任务目标已达成时才返回 True
        """
        base64_image = self._encode_image(image_bytes)

        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是任务完成验证助手。请仔细查看截图，判断用户任务是否已经完成。\n\n"
                        "请严格判断，不要猜测。只有当以下条件都满足时才回答 '完成'：\n"
                        "1. 截图明确显示了任务目标的结果\n"
                        "2. 所有必要的操作都已执行\n"
                        "3. 结果符合用户指令\n\n"
                        "如果任务未完成，即使只差一点点，也要回答 '未完成' 并说明原因。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"用户任务: {task_description}\n\n"
                            f"请查看截图，判断这个任务是否已经完成？\n"
                            f"回答格式：\n"
                            f"- 如果完成了，回答：完成\n"
                            f"- 如果未完成，回答：未完成 + 简要原因（1句话）",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low",
                            },
                        },
                    ],
                },
            ],
            max_tokens=128,
            temperature=0.1,
        )
        result = response.choices[0].message.content.strip()
        logger.info(f"任务完成检查结果: {result[:100]}")
        # 只有明确包含"完成"才返回 True，排除"未完成"
        return "完成" in result and "未完成" not in result[:5]

    # ============ 通用模型 ============

    def plan_task(
        self,
        state_description: str,
        user_instruction: str,
        action_history: list = None,
        os_info: str = None,
        resolution: str = None,
    ) -> list:
        """
        通用模型规划任务步骤
        返回: 步骤列表，每个步骤:
        {
            "step": 1,
            "action": "动作类型",
            "description": "步骤描述",
            "target": "目标元素描述",
            "keys": ["快捷键按键"],
            "text": "输入文本",
            "point": "坐标 point='<point>x y</point>'"
        }
        
        Args:
            state_description: 当前界面状态描述
            user_instruction: 用户指令
            action_history: 历史操作记录
            os_info: 远程主机操作系统信息（如 "Windows 11", "Ubuntu 22.04 LTS (GNOME)" 等）
            resolution: 远程桌面分辨率（如 "1920x1080"）
        """
        if action_history is None:
            action_history = []

        history_text = ""
        if action_history:
            history_text = "\n已执行的操作:\n" + "\n".join(
                f"{i+1}. {h['action']}: {h['description']}"
                for i, h in enumerate(action_history[-5:])
            )

        # 构建远程主机信息
        remote_info = ""
        if os_info:
            remote_info += f"- 操作系统: {os_info}\n"
        if resolution:
            remote_info += f"- 远程桌面分辨率: {resolution}\n"

        # 根据操作系统类型添加快捷键说明
        hotkey_info = ""
        if os_info:
            os_lower = os_info.lower()
            if "windows" in os_lower or "win" in os_lower:
                hotkey_info = (
                    "1. 快捷键操作：使用 hotkey 动作，填写 keys 字段\n"
                    "   - Windows: [\"LeftWin\", \"D\"] 表示 Win+D（显示桌面）\n"
                    "   - Windows: [\"LeftWin\", \"R\"] 表示 Win+R（打开运行对话框）\n"
                    "   - Windows: [\"LeftWin\", \"E\"] 表示 Win+E（打开文件资源管理器）\n"
                    "   - Windows: [\"LeftWin\", \"S\"] 表示 Win+S（打开搜索）\n"
                    "   - Windows: [\"AltLeft\", \"F4\"] 表示 Alt+F4（关闭窗口）\n"
                )
            elif "linux" in os_lower or "ubuntu" in os_lower or "gnome" in os_lower or "kde" in os_lower:
                hotkey_info = (
                    "1. 快捷键操作：使用 hotkey 动作，填写 keys 字段\n"
                    "   - Linux: [\"Super\", \"D\"] 表示 Super+D（显示桌面）\n"
                    "   - Linux: [\"Super\", \"R\"] 表示 Super+R（打开运行对话框，如 GNOME）\n"
                    "   - Linux: [\"Super\", \"E\"] 表示 Super+E（打开文件管理器，如 GNOME）\n"
                    "   - Linux: [\"Super\", \"A\"] 表示 Super+A（打开应用列表，如 GNOME）\n"
                    "   - Linux: [\"AltLeft\", \"F4\"] 表示 Alt+F4（关闭窗口）\n"
                )
            elif "macos" in os_lower or "darwin" in os_lower:
                hotkey_info = (
                    "1. 快捷键操作：使用 hotkey 动作，填写 keys 字段\n"
                    "   - macOS: [\"CommandLeft\", \"D\"] 表示 Cmd+D\n"
                    "   - macOS: [\"CommandLeft\", \"H\"] 表示 Cmd+H（隐藏应用）\n"
                    "   - macOS: [\"CommandLeft\", \"M\"] 表示 Cmd+M（最小化窗口）\n"
                    "   - macOS: [\"CommandLeft\", \"W\"] 表示 Cmd+W（关闭窗口）\n"
                    "   - macOS: [\"ControlLeft\", \"CommandLeft\", \"Q\"] 表示注销\n"
                )

        # 输入文本的警告信息
        type_warning = (
            "\n2. 输入文本：使用 type 动作，填写 text 字段\n"
            "   - ⚠️ 注意：输入会发送到当前焦点所在的窗口！\n"
            "   - 如果当前焦点在终端，输入会发送到终端\n"
            "   - 如果焦点在文本编辑器，输入会发送到文本编辑器\n"
        )

        system_prompt = (
            "你是一个GUI自动化任务规划器。你根据当前界面状态和用户指令，"
            "规划出详细的执行步骤。\n\n"
            "【重要：这是一个远程桌面控制系统】\n"
            "你正在控制的是远程主机，不是你的本地计算机。你需要根据远程主机的操作系统类型来选择正确的操作方式。\n\n"
            "【强制规则：远程主机 OS 信息优先】\n"
            "如果状态描述中的操作系统类型与【远程主机信息】中的操作系统不一致，"
            "必须以【远程主机信息】中的操作系统为准，忽略状态描述中的操作系统描述。\n"
            "常见情况：状态描述中看到的可能是 WSL/Docker/虚拟机内的 Linux 桌面，"
            "但实际远程主机是 Windows，此时必须按 Windows 规划。\n\n"
        )

        if remote_info:
            system_prompt += f"【远程主机信息】\n{remote_info}\n"

        system_prompt += f"{hotkey_info}{type_warning}\n"

        system_prompt += (
            "3. 鼠标点击：使用 click 动作，填写 point 字段\n"
            "4. 双击/右键：使用 double_click/right_click 动作\n"
            "5. 滚动：使用 scroll 动作\n"
            "6. 完成任务：使用 finished 动作\n\n"
            "【关键规则】\n"
            "1. 如果任务涉及打开新应用，优先使用系统快捷键打开应用启动器（Win键/Super键/Cmd键），而不是在当前窗口输入命令\n"
            "2. 如果当前焦点在终端/命令行窗口，不要随意输入命令，除非任务明确需要\n"
            "3. 优先使用快捷键完成操作\n"
            "4. 鼠标操作需要精确定位到目标元素\n"
            "5. 每一步都要有清晰的描述\n"
            "6. 不要规划超过 5 步的操作\n"
            "7. 如果可以在 1-2 步内完成，就直接规划\n\n"
            "请严格按照以下JSON格式输出步骤：\n\n"
            "[\n"
            "  {\n"
            "    \"step\": 1,\n"
            "    \"action\": \"动作类型\",\n"
            "    \"description\": \"步骤描述\",\n"
            "    \"target\": \"目标元素描述\",\n"
            "    \"keys\": [\"快捷键按键\"],\n"
            "    \"text\": \"输入文本\",\n"
            "    \"point\": \"坐标\"\n"
            "  },\n"
            "  ...\n"
            "]\n\n"
            "可用的动作类型：\n"
            "- hotkey: 快捷键，填写 keys 字段\n"
            "- type: 输入文本，填写 text 字段\n"
            "- click: 点击，填写 point 字段，格式为 point='<point>x y</point>'\n"
            "- double_click: 双击，填写 point 字段\n"
            "- right_click: 右键，填写 point 字段\n"
            "- drag: 拖拽，填写 point 字段 (起点)\n"
            "- scroll: 滚动，填写 point 和 direction 字段\n"
            "- finished: 完成任务\n"
        )

        response = self.client.chat.completions.create(
            model=self.general_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": (
                        f"当前界面状态:\n{state_description}\n\n"
                        f"用户指令: {user_instruction}\n\n"
                        f"{history_text}\n\n"
                        f"请规划详细的执行步骤，以 JSON 格式输出。"
                    ),
                },
            ],
            max_tokens=2048,
            temperature=0.3,
        )
        return response.choices[0].message.content

    def select_target_element(
        self,
        image_bytes: bytes,
        accessibility_tree: dict,
        target_description: str,
    ) -> dict:
        """
        根据截图和 Accessibility 信息，定位目标元素
        返回: {
            "role": "元素角色",
            "name": "元素名称",
            "bounds": {"x": int, "y": int, "width": int, "height": int},
            "point": "point='<point>x y</point>'"
        }
        """
        base64_image = self._encode_image(image_bytes)

        # 提取关键元素信息用于提示
        element_summary = self._summarize_accessibility(accessibility_tree)

        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个UI元素定位助手。你通过截图和元素树信息，"
                        "定位用户描述的目标元素。请严格按照以下格式输出：\n\n"
                        "role: [元素角色]\n"
                        "name: [元素名称]\n"
                        "point: point='<point>x y</point>'\n\n"
                        "注意：\n"
                        "- 坐标使用物理分辨率坐标\n"
                        "- 如果无法确定，返回 point: point='<point>unknown unknown</point>'\n"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"目标元素描述: {target_description}\n\n"
                                f"可用元素信息:\n{element_summary}\n\n"
                                f"请定位目标元素并输出坐标。"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low",
                            },
                        },
                    ],
                },
            ],
            max_tokens=256,
            temperature=0.3,
        )
        return response.choices[0].message.content

    def _summarize_accessibility(self, tree: dict, max_items: int = 30) -> str:
        """将 Accessibility 树信息摘要化"""
        if not tree or tree.get("role") == "error":
            return "无障碍信息不可用"

        def _flatten(node, depth=0, count=0):
            if count[0] >= max_items:
                return "..."
            lines = []
            indent = "  " * depth
            name = node.get("name", "")[:50]
            bounds = node.get("bounds", {})
            pos = f"{bounds.get('x', 0)},{bounds.get('y', 0)}" if bounds else "unknown"
            lines.append(f"{indent}- {node['role']}: {name} [{pos}]")
            count[0] += 1
            for child in node.get("children", []):
                if count[0] >= max_items:
                    break
                child_lines = _flatten(child, depth + 1, count)
                lines.extend(child_lines)
            return lines

        return "\n".join(_flatten(tree))

    def _extract_top_windows(self, tree: dict, max_count: int = 10) -> list:
        """从无障碍树提取顶级窗口节点"""
        if not tree or tree.get("role") == "error":
            return []
        window_roles = {"window", "dialog"}
        result = []
        for child in tree.get("children", []):
            role = child.get("role", "").lower()
            if role in window_roles and child.get("bounds"):
                result.append(child)
                if len(result) >= max_count:
                    break
        return result

    def _build_window_hierarchy(self, tree: dict) -> str:
        """
        从无障碍树构建层级化的窗口结构描述
        格式：顶级窗口 → 子面板/标签 → 子元素
        """
        if not tree or tree.get("role") == "error":
            return ""

        root = tree
        lines = []
        children = root.get("children", [])

        # 过滤出有意义的顶级节点（通常是窗口）
        window_roles = {"window", "dialog", "menu", "popup", "tooltip"}
        top_windows = [
            c for c in children
            if c.get("role", "").lower() in window_roles
            or (c.get("bounds") and c.get("bounds", {}).get("width", 0) > 100)
        ]

        if not top_windows:
            top_windows = children[:5]

        for i, win in enumerate(top_windows, 1):
            self._format_window_node(win, lines, prefix=f"{i}. ", depth=0)

        return "\n".join(lines)

    def _format_window_node(self, node: dict, lines: list, prefix: str = "", depth: int = 0, max_children: int = 8):
        """格式化单个节点为可读行"""
        role = node.get("role", "Unknown")
        name = node.get("name", "")
        bounds = node.get("bounds", {})
        size = ""
        if bounds.get("width") and bounds.get("height"):
            size = f" ({bounds['width']}x{bounds['height']})"

        line = f"{prefix}[{role}] {name}{size}"
        lines.append("  " * depth + line)

        panel_roles = {"pane", "group", "tab", "toolbar", "menu", "list", "edit", "button", "document"}
        children = node.get("children", [])
        panel_children = [c for c in children if c.get("role", "").lower() in panel_roles][:max_children]
        other_children = [c for c in children if c.get("role", "").lower() not in panel_roles][:3]

        shown_children = panel_children + other_children
        for j, child in enumerate(shown_children):
            child_prefix = f"{j+1}. " if depth == 0 else "- "
            self._format_window_node(child, lines, prefix=child_prefix, depth=depth + 1, max_children=5)