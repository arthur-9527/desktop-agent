"""
远程桌面控制 Agent - 主流程编排
三阶段: 状态感知 → 任务规划 → 执行循环
"""
import asyncio
import io
import json
import logging
from typing import Optional

from PIL import Image

from desktop import DesktopController
from llm import LLMClient
from action_parser import ActionParser, ParsedAction

logger = logging.getLogger(__name__)


class RemoteDesktopAgent:
    """远程桌面控制 Agent"""

    def __init__(
        self,
        desktop: DesktopController = None,
        llm: LLMClient = None,
        max_iterations: int = 10,
        loop_interval_ms: int = 500,
    ):
        self.desktop = desktop or DesktopController()
        self.llm = llm or LLMClient()
        self.action_parser = ActionParser()
        self.max_iterations = max_iterations
        self.loop_interval_ms = loop_interval_ms

        # 状态
        self.action_history = []  # 历史操作记录
        self.current_screenshot = None  # 当前截图
        self.current_state_description = None  # 当前状态描述

    async def run(self, instruction: str) -> dict:
        """
        执行任务

        流程:
        1. 初始状态感知（截图 + 无障碍树 → 设置分辨率/OS）
        2. LLM 规划所有步骤
        3. 对每步: 执行 → 失败则截图 replan → 下一条
        4. 最终截图验证
        """
        logger.info(f"开始执行任务: {instruction}")

        result = {
            "instruction": instruction,
            "steps": [],
            "success": False,
            "message": "",
        }

        try:
            # ========== 阶段1: 初始状态感知 ==========
            state_desc = await self._perceive_state()
            if not state_desc:
                result["message"] = "无法获取远程桌面截图"
                return result

            logger.info("初始状态感知完成，开始执行循环")

            # ========== 阶段2: 任务规划 ==========
            steps = await self._plan_task(state_desc, instruction)
            if not steps:
                result["message"] = "无法规划任务步骤"
                return result

            logger.info(f"规划了 {len(steps)} 个步骤: {[s.get('description','') for s in steps]}")

            # ========== 阶段3: 执行循环 ==========
            success, messages = await self._execute_loop(steps, instruction)

            result["success"] = success
            result["steps"] = messages
            result["message"] = "任务完成" if success else "任务执行失败"

        except Exception as e:
            logger.error(f"Agent 执行异常: {e}", exc_info=True)
            result["message"] = f"异常: {str(e)}"

        return result

    async def _perceive_state(self) -> Optional[str]:
        """阶段1: 状态感知 - 截图 + 视觉模型分析 + 焦点元素"""
        try:
            # 获取截图
            img = await asyncio.to_thread(self.desktop.screenshot_to_image)
            if not img:
                logger.error("无法获取截图")
                return None

            self.current_screenshot = img
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=20)
            image_bytes = buffer.getvalue()

            # 获取焦点元素信息
            focused_element = None
            try:
                focused_element = await asyncio.to_thread(self.desktop.get_focused_element)
                logger.info(f"焦点元素: {focused_element}")
            except Exception as e:
                logger.warning(f"获取焦点元素失败: {e}")

            # 获取 Accessibility 树（用于获取真实分辨率和 OS）
            accessibility_tree = None
            try:
                accessibility_tree = await asyncio.to_thread(self.desktop.get_accessibility_tree, 2)
            except Exception as e:
                logger.warning(f"获取无障碍树失败: {e}")

            # 从 Accessibility 树获取真实屏幕信息
            screen_info = self._extract_screen_from_tree(accessibility_tree)
            logger.info(f"屏幕信息（从无障碍树提取）: {screen_info}")

            # 将真实分辨率同步到 DesktopController，确保坐标转换准确
            if screen_info and screen_info.get("width") and screen_info.get("height"):
                self.desktop.set_remote_screen_info(
                    width=screen_info["width"],
                    height=screen_info["height"],
                    os_type=screen_info.get("os"),
                )

            # 将无障碍树信息传给视觉模型，帮助正确识别前台窗口和多窗口场景
            # 视觉模型分析状态（传入焦点元素和屏幕信息）
            state_desc = await asyncio.to_thread(
                self.llm.analyze_state,
                image_bytes,
                focused_element=focused_element,
                accessibility_tree=accessibility_tree,
                detected_os=screen_info.get("os") if screen_info else None,
            )
            self.current_state_description = state_desc
            logger.info(f"状态分析完成: {state_desc[:200]}...")

            # 保存屏幕信息供后续使用
            self._screen_info = screen_info
            return state_desc

        except Exception as e:
            logger.error(f"状态感知失败: {e}", exc_info=True)
            return None

    def _extract_screen_from_tree(self, tree: dict) -> dict:
        """
        从无障碍树根节点提取真实的屏幕分辨率和 OS 信息
        优先级：bounds > screen_info API
        """
        if not tree:
            return None

        root = tree.get("tree") or tree
        bounds = root.get("bounds", {})

        width = bounds.get("width")
        height = bounds.get("height")

        if width and height and width > 0 and height > 0:
            screen_info = {"width": width, "height": height}

            # 从元素 role 推断操作系统
            os_type = self._detect_os_from_tree(root)
            if os_type:
                screen_info["os"] = os_type

            return screen_info

        return None

    def _detect_os_from_tree(self, node: dict) -> Optional[str]:
        """
        从无障碍树特征推断操作系统
        关键特征：
        - Windows: "Chrome Legacy Window", "Application", Pane with 窗口模式
        - Linux/GNOME: "mutter", "Gnome-shell", "xdotool"
        - macOS: "AXStandardWindow", "AXGroup", Apple 特征
        """
        if not node:
            return None

        role = node.get("role", "").lower()
        name = node.get("name", "").lower()
        children = node.get("children", [])

        # Windows 特征
        windows_indicators = [
            "chrome legacy window",
            "chrome widget",
            "windows shell",
            "progman",
            "workerw",
            "application",  # Windows 常用
        ]
        for child in children:
            child_role = child.get("role", "").lower()
            child_name = child.get("name", "").lower()
            if any(ind in child_role or ind in child_name for ind in windows_indicators):
                return "Windows"
            # 检查 Chrome 窗口
            if child_role == "window" and child_name and "chrome" in child_name:
                return "Windows"

        # macOS 特征
        mac_indicators = ["axstandardwindow", "axgroup", "axscrollarea"]
        if any(ind in role for ind in mac_indicators):
            return "macOS"

        # Linux/GNOME 特征
        linux_indicators = ["mutter", "gnome", "kwin", "x compositor"]
        for child in children:
            child_name = child.get("name", "").lower()
            child_role = child.get("role", "").lower()
            if any(ind in child_name or ind in child_role for ind in linux_indicators):
                return "Linux"

        # 递归检查子节点
        for child in children:
            result = self._detect_os_from_tree(child)
            if result:
                return result

        return None

    def _override_os_in_description(self, description: str, os_type: str) -> str:
        """
        用权威的 OS 类型覆盖状态描述中的 OS 信息
        防止视觉模型把 WSL 内嵌的 Linux 桌面误判为远程主机的 OS
        """
        if not description or not os_type:
            return description

        # 匹配各种 OS 描述格式并替换
        import re

        # Windows
        description = re.sub(
            r"(?i)操作系统类型[：:]\s*(Windows[^\s]*|Linux[^\s]*|macOS[^\s]*)",
            f"操作系统类型: {os_type}",
            description,
        )
        # 匹配单独一行的 OS 描述
        description = re.sub(
            r"(?im)^.*?(操作系统类型|OS[:：]|系统类型).*$",
            f"【系统类型（远程主机，无障碍树检测）】: {os_type}",
            description,
        )
        # 覆盖 Linux/GNOME 桌面环境描述中的 OS 部分
        if "linux" in description.lower() or "gnome" in description.lower():
            suffix = (
                f"\n\n【重要】虽然视觉上看到的是 Linux/GNOME 桌面环境，"
                f"但无障碍树确认远程主机操作系统为: {os_type}。"
                f"请按 {os_type} 的方式规划操作，而非 Linux。"
            )
            return description + suffix
        return description

    async def _plan_task(
        self, state_description: str, instruction: str
    ) -> Optional[list]:
        """阶段2: 任务规划 - 通用模型规划步骤"""
        try:
            # 构建远程主机信息
            os_info = None
            resolution = None
            if hasattr(self, '_screen_info') and self._screen_info:
                resolution = f"{self._screen_info.get('width', '?')}x{self._screen_info.get('height', '?')}"
                os_info = self._screen_info.get('os')

            # 如果树提取失败，回退到从状态描述推断
            if not os_info:
                if "windows" in state_description.lower():
                    os_info = "Windows"
                elif "linux" in state_description.lower() or "ubuntu" in state_description.lower() or "gnome" in state_description.lower() or "kde" in state_description.lower():
                    os_info = "Linux"
                elif "macos" in state_description.lower() or "darwin" in state_description.lower():
                    os_info = "macOS"

            # 用无障碍树提取的 OS 覆盖状态描述中的错误 OS 判断
            # 防止视觉模型把 WSL Linux 桌面误判为远程主机的 OS
            if os_info and state_description:
                state_description = self._override_os_in_description(
                    state_description, os_info
                )

            logger.info(f"远程主机信息 - OS: {os_info}, 分辨率: {resolution}")
            
            plan = await asyncio.to_thread(
                self.llm.plan_task, 
                state_description, 
                instruction, 
                self.action_history,
                os_info=os_info,
                resolution=resolution,
            )

            # 解析 JSON 输出
            steps = self._parse_plan(plan)
            if steps is not None:
                logger.info(f"规划了 {len(steps)} 个步骤")
            return steps

        except Exception as e:
            logger.error(f"任务规划失败: {e}", exc_info=True)
            return None

    def _parse_plan(self, plan_text: str) -> Optional[list]:
        """解析 LLM 输出的任务规划"""
        if not plan_text:
            logger.error("LLM 返回空内容，无法解析任务规划")
            return None
        try:
            # 尝试提取 JSON
            json_start = plan_text.find("[")
            json_end = plan_text.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                json_text = plan_text[json_start:json_end]
                return json.loads(json_text)
            logger.error(f"未找到 JSON 数组: {plan_text[:200]}")
            return None
        except json.JSONDecodeError:
            logger.error(f"无法解析任务规划: {plan_text[:200]}")
            return None

    async def _execute_loop(
        self, steps: list, instruction: str
    ) -> tuple:
        """
        阶段3: 执行循环
        流程: 规划所有步骤 → 对每步执行+验证 → 失败则 replan 该步
        """
        messages = []

        for i, step in enumerate(steps):
            step_num = i + 1
            step_action = step.get("action", "")
            step_desc = step.get("description", "")
            step_keys = step.get("keys", [])
            step_text = step.get("text", "")
            step_point = step.get("point", "")

            logger.info(f"=== 执行步骤 {step_num}: {step_desc} ===")

            # -------- 执行该步骤 --------
            if step_keys:
                success, msg = await self._execute_hotkey(step_keys, step_desc)
            elif step_point:
                success, msg = await self._execute_click_point(step_point, step_desc)
            elif step_text:
                success, msg = await self._execute_type_text(step_text, step_desc)
            else:
                success, msg = False, {"type": "error", "content": f"步骤无有效操作: {step_desc}"}

            messages.append(msg)
            if success:
                self.action_history.append({"action": step_action, "description": step_desc})
                logger.info(f"步骤 {step_num} 执行成功")
            else:
                logger.warning(f"步骤 {step_num} 执行失败，尝试 replan")
                messages.append({"type": "warning", "content": f"步骤 {step_num} 执行失败，尝试 replan"})
                # replan：该步失败时，截图重新分析 + 让 LLM 决定补救动作
                replan_success = await self._replan_step(step_num, step_desc, instruction, messages)
                if not replan_success:
                    logger.error(f"步骤 {step_num} replan 失败，终止")
                    return False, messages

            # 执行后短暂等待
            await asyncio.sleep(self.loop_interval_ms / 1000)

        # -------- 最终验证 --------
        success = await self._check_final_completion(instruction)
        return success, messages

    async def _replan_step(
        self, step_num: int, failed_desc: str, instruction: str, messages: list
    ) -> bool:
        """单个步骤失败时，截图 + 让 LLM 决定补救动作"""
        for attempt in range(3):
            logger.info(f"replan 尝试 {attempt + 1}/3")

            img = await asyncio.to_thread(self.desktop.screenshot_to_image)
            if not img:
                continue
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=20)
            image_bytes = buffer.getvalue()

            tree = None
            try:
                tree = await asyncio.to_thread(self.desktop.get_accessibility_tree, 2)
            except Exception:
                pass

            current_state = await asyncio.to_thread(
                self.llm.analyze_state,
                image_bytes,
                accessibility_tree=tree,
            )

            # 让 LLM 根据当前状态决定补救动作
            action_decision = await asyncio.to_thread(
                self.llm.decide_action,
                image_bytes,
                f"【任务】{instruction}\n"
                f"【原步骤失败】{failed_desc}\n"
                f"【当前状态】{current_state}\n"
                f"请根据当前状态，决定下一步补救动作，使任务继续推进。\n"
                f"输出格式: Thought: ...\\nAction: ...\\n参数",
                self.action_history,
                accessibility_info=tree,
            )
            logger.info(f"replan LLM 决策: {action_decision[:200]}...")

            parsed = self.action_parser.parse(action_decision)
            if parsed.action == "finished":
                self.action_history.append({"action": "finished", "description": parsed.thought})
                return True

            success, msg = await self._execute_parsed_action(parsed)
            messages.append(msg)
            if success:
                self.action_history.append({"action": parsed.action, "description": parsed.thought})
                logger.info(f"replan 动作成功: {parsed.action}")
                return True

            await asyncio.sleep(self.loop_interval_ms / 1000)

        return False

    async def _execute_hotkey(self, keys: list, description: str) -> tuple:
        try:
            logger.info(f"执行快捷键: {keys}")
            await asyncio.to_thread(self.desktop.keyboard_hotkey, keys)
            await asyncio.sleep(self.loop_interval_ms / 1000)
            return True, {"type": "success", "content": f"快捷键成功: {keys}"}
        except Exception as e:
            logger.error(f"快捷键失败: {e}")
            return False, {"type": "error", "content": f"快捷键失败: {str(e)}"}

    async def _execute_click_point(self, point_str: str, description: str) -> tuple:
        """执行点击（支持多种坐标格式）"""
        try:
            point_match = self.action_parser.parse(f"Action: click\npoint='{point_str}'")
            if not point_match.point:
                return False, {"type": "error", "content": f"无法解析坐标: {point_str}"}
            norm_x, norm_y = self.desktop.physical_to_normalized(
                point_match.point[0], point_match.point[1]
            )
            logger.info(f"执行点击: {point_match.point} → 归一化({norm_x}, {norm_y})")
            await asyncio.to_thread(self.desktop.mouse_left_click, norm_x, norm_y)
            await asyncio.sleep(self.loop_interval_ms / 1000)
            return True, {"type": "success", "content": f"点击成功: {point_str}"}
        except Exception as e:
            logger.error(f"点击失败: {e}")
            return False, {"type": "error", "content": f"点击失败: {str(e)}"}

    async def _execute_type_text(self, text: str, description: str) -> tuple:
        try:
            logger.info(f"执行输入: {text}")
            await asyncio.to_thread(self.desktop.keyboard_type, text)
            await asyncio.sleep(self.loop_interval_ms / 1000)
            return True, {"type": "success", "content": f"输入成功: {text}"}
        except Exception as e:
            logger.error(f"输入失败: {e}")
            return False, {"type": "error", "content": f"输入失败: {str(e)}"}

    async def _check_final_completion(self, instruction: str) -> bool:
        """最终截图验证"""
        try:
            img = await asyncio.to_thread(self.desktop.screenshot_to_image)
            if not img:
                return False
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=20)
            image_bytes = buffer.getvalue()
            return await asyncio.to_thread(
                self.llm.check_completion, image_bytes, instruction
            )
        except Exception as e:
            logger.error(f"最终验证失败: {e}")
            return False

    async def _execute_parsed_action(self, parsed: ParsedAction) -> tuple:
        """执行解析后的动作"""
        try:
            if parsed.action == "click" and parsed.point:
                norm_x, norm_y = self.desktop.physical_to_normalized(
                    parsed.point[0], parsed.point[1]
                )
                await asyncio.to_thread(self.desktop.mouse_left_click, norm_x, norm_y)
                self.action_history.append({"action": "click", "description": parsed.thought})
                return True, {"type": "success", "content": f"点击成功: {parsed.point}"}

            elif parsed.action == "double_click" and parsed.point:
                norm_x, norm_y = self.desktop.physical_to_normalized(
                    parsed.point[0], parsed.point[1]
                )
                await asyncio.to_thread(self.desktop.mouse_double_click, norm_x, norm_y)
                self.action_history.append({"action": "double_click", "description": parsed.thought})
                return True, {"type": "success", "content": f"双击成功: {parsed.point}"}

            elif parsed.action == "right_click" and parsed.point:
                norm_x, norm_y = self.desktop.physical_to_normalized(
                    parsed.point[0], parsed.point[1]
                )
                await asyncio.to_thread(self.desktop.mouse_right_click, norm_x, norm_y)
                self.action_history.append({"action": "right_click", "description": parsed.thought})
                return True, {"type": "success", "content": f"右键成功: {parsed.point}"}

            elif parsed.action == "hotkey" and parsed.key:
                keys = self.action_parser._parse_key(parsed.key)
                await asyncio.to_thread(self.desktop.keyboard_hotkey, keys)
                self.action_history.append({"action": "hotkey", "description": parsed.thought})
                return True, {"type": "success", "content": f"快捷键成功: {parsed.key}"}

            elif parsed.action == "type" and parsed.text:
                await asyncio.to_thread(self.desktop.keyboard_type, parsed.text)
                self.action_history.append({"action": "type", "description": parsed.thought})
                return True, {"type": "success", "content": f"输入成功: {parsed.text}"}

            elif parsed.action == "scroll" and parsed.direction:
                await asyncio.to_thread(self.desktop.mouse_scroll, parsed.direction)
                self.action_history.append({"action": "scroll", "description": parsed.thought})
                return True, {"type": "success", "content": f"滚动成功: {parsed.direction}"}

            elif parsed.action == "wait":
                await asyncio.sleep(1)
                return True, {"type": "info", "content": "等待完成"}

            elif parsed.action == "finished":
                return True, {"type": "success", "content": "任务完成"}

            else:
                return False, {"type": "error", "content": f"未知动作: {parsed.action}"}

        except Exception as e:
            logger.error(f"执行解析动作失败: {e}")
            return False, {"type": "error", "content": f"执行失败: {str(e)}"}

    async def run_interactive(self, instruction: str) -> dict:
        """
        交互式执行 - 打印每一步的执行过程
        """
        print(f"\n{'='*50}")
        print(f"开始执行任务: {instruction}")
        print(f"{'='*50}\n")

        # 初始状态感知
        print("【初始状态感知】")
        state_desc = await self._perceive_state()
        if not state_desc:
            print("❌ 无法获取截图")
            return {"success": False, "message": "无法获取截图"}
        print(f"✅ 初始状态感知完成\n")

        # 任务规划
        print("【任务规划】")
        steps = await self._plan_task(state_desc, instruction)
        if not steps:
            print("❌ 无法规划步骤")
            return {"success": False, "message": "无法规划"}
        print(f"✅ 规划了 {len(steps)} 个步骤:")
        for i, s in enumerate(steps, 1):
            print(f"  {i}. {s.get('description', '')}")
        print()

        # 执行循环
        print("【执行循环】")
        success, messages = await self._execute_loop(steps, instruction)

        print(f"\n{'='*50}")
        print("✅ 任务完成!" if success else "❌ 任务失败")
        print(f"{'='*50}\n")

        return {"success": success, "messages": messages}