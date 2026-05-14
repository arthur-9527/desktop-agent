"""核心 Agent Loop 模块"""

import asyncio
import platform
from typing import Optional
from openai import AsyncOpenAI

from .agentdesk_client import AgentDeskClient
from .action_executor import ActionExecutor
from .prompts import build_system_prompt
from .accessibility_parser import create_info_table, AccessibilityParser, GlobalInfo


class DeskAgent:
    """UI-TARS 驱动的桌面 Agent"""

    def __init__(
        self,
        agentdesk: AgentDeskClient,
        model: AsyncOpenAI,
        model_name: str = "UI-TARS-1.5-7B",
        max_steps: int = 25,
        context_window_size: int = 5,
        debug: bool = False,
    ):
        self.client = agentdesk
        self.model = model
        self.model_name = model_name
        self.max_steps = max_steps
        self.context_window_size = context_window_size  # 保留最近 N 步的截图
        self.debug = debug
        self.action_executor: Optional[ActionExecutor] = None
        self.global_info: Optional[GlobalInfo] = None  # 缓存结构化全局信息
        self._accessibility_parser = AccessibilityParser()

    async def run(self, task: str) -> dict:
        """执行任务

        Args:
            task: 任务描述

        Returns:
            {"success": bool, "message": str, "steps": int}
        """
        # 获取初始全局动态信息（结构化）
        self.global_info = await self._get_global_info_struct()
        os_type = self.global_info.os if self.global_info else "Windows"
        print(f"[全局信息] 操作系统: {os_type}")

        # 初始化 ActionExecutor，传入操作系统类型
        self.action_executor = ActionExecutor(self.client, os_type=os_type)

        # 获取初始全局动态信息表（文本格式，用于 prompt）
        info_table = await self._get_global_info_table()
        if info_table:
            print(f"[全局信息] 已获取动态信息表")

        # 构建 system prompt
        system_prompt = build_system_prompt(task)
        if info_table:
            system_prompt += f"\n\n{info_table}"

        messages = [{"role": "system", "content": system_prompt}]

        for step in range(self.max_steps):
            print(f"\n{'=' * 50}")
            print(f"Step {step + 1}/{self.max_steps}")

            # 1. 截图（带网格，帮助 UI-TARS 精确定位）
            try:
                screenshot = await self.client.screenshot(show_grid=True)
            except Exception as e:
                print(f"截图失败: {e}")
                return {
                    "success": False,
                    "message": f"截图失败: {e}",
                    "steps": step,
                }

            # 2. 更新全局动态信息表（每次操作后）
            info_table = await self._get_global_info_table()

            # 3. 构建消息
            user_text = "继续执行任务。" if step > 0 else "开始执行任务。"
            
            # 添加网格信息提示
            grid_info = screenshot.get("grid_info")
            if grid_info:
                h_count = grid_info.get("horizontalCount", 64)
                v_count = grid_info.get("verticalCount", 64)
                user_text += f"\n\n[网格信息] 截图带有 {h_count}×{v_count} 归一化网格，坐标系统为 0-1000。"
            
            if info_table:
                user_text += f"\n\n{info_table}"

            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{screenshot['base64']}"
                        }
                    },
                    {
                        "type": "text",
                        "text": user_text
                    },
                ]
            })

            # 3. 调用 UI-TARS 模型
            try:
                response = await self.model.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=1024,
                )
            except Exception as e:
                print(f"模型调用失败: {e}")
                return {
                    "success": False,
                    "message": f"模型调用失败: {e}",
                    "steps": step,
                }

            raw_output = response.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": raw_output})

            # 滑动窗口：保留 system + 最近 N 轮对话
            messages = self._trim_messages(messages)

            print(f"模型输出: {raw_output[:300]}{'...' if len(raw_output) > 300 else ''}")

            # 4. 解析动作
            parsed = self.action_executor.parse(raw_output)
            action_type = parsed.get("action_type", "unknown")
            print(f"解析动作: {action_type}")

            # 5. 判断是否完成
            if action_type == "finished":
                message = parsed.get("action_inputs", {}).get("content", "Done")
                print(f"\n✓ 任务完成: {message}")
                return {
                    "success": True,
                    "message": message,
                    "steps": step + 1,
                }

            # 6. 调试模式：等待用户确认
            if self.debug:
                input("按 Enter 执行此动作...")

            # 7. 执行动作
            try:
                await self.action_executor.execute(parsed)
            except Exception as e:
                print(f"动作执行失败: {e}")

            # 8. 等待界面更新
            await asyncio.sleep(0.5)

        return {
            "success": False,
            "message": "达到最大步数限制",
            "steps": self.max_steps
        }

    async def _get_global_info_struct(self) -> Optional[GlobalInfo]:
        """获取结构化的全局动态信息（用于内部逻辑判断）

        Returns:
            GlobalInfo 结构化数据，失败时返回 None
        """
        try:
            tree = await self.client.accessibility_tree(max_depth=10)
            return self._accessibility_parser.parse(tree, None, None)
        except Exception as e:
            print(f"[全局信息] 结构化数据获取失败: {e}")
            return None

    async def _get_global_info_table(self) -> str:
        """获取全局动态信息表

        纯代码处理，不经过 LLM，速度很快。
        失败时返回空字符串，不影响主流程。
        """
        try:
            # 并行获取：无障碍树、鼠标位置、焦点元素
            tree = await self.client.accessibility_tree(max_depth=10)

            # 尝试获取鼠标位置和焦点元素（可选）
            mouse_pos = None
            focused = None
            try:
                mouse_pos = await self.client.mouse_position()
            except Exception:
                pass
            try:
                focused = await self.client.accessibility_focused()
            except Exception:
                pass

            # 解析生成信息表
            return create_info_table(tree, mouse_pos, focused)

        except Exception as e:
            print(f"[全局信息] 获取失败: {e}")
            return ""

    def _trim_messages(self, messages: list) -> list:
        """滑动窗口：保留 system + 最近 N 轮对话

        每轮对话包含一个 user 消息（带截图）和一个 assistant 消息。

        Args:
            messages: 消息列表

        Returns:
            裁剪后的消息列表
        """
        if len(messages) <= 1:
            return messages

        # 保留 system message
        system_msg = messages[0]

        # 计算需要保留的消息数
        # 每轮 = 1 user + 1 assistant，所以保留 2 * context_window_size 条
        keep_count = self.context_window_size * 2

        # 获取最近的对话（跳过 system）
        recent_messages = messages[1:]

        # 如果超出窗口大小，裁剪
        if len(recent_messages) > keep_count:
            recent_messages = recent_messages[-keep_count:]
            print(f"[Context] 裁剪到最近 {self.context_window_size} 轮对话")

        return [system_msg] + recent_messages
