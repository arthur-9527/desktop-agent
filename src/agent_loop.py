"""核心 Agent Loop 模块"""

import asyncio
from typing import Optional
from openai import AsyncOpenAI

from .agentdesk_client import AgentDeskClient
from .action_executor import ActionExecutor
from .prompts import build_system_prompt


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

    async def run(self, task: str) -> dict:
        """执行任务

        Args:
            task: 任务描述

        Returns:
            {"success": bool, "message": str, "steps": int}
        """
        self.action_executor = ActionExecutor(self.client)

        # 获取无障碍树作为辅助提示（可选）
        tree_hint = await self._get_accessibility_hint()

        # 构建 system prompt
        system_prompt = build_system_prompt(task)
        if tree_hint:
            system_prompt += f"\n\n[无障碍树参考]\n{tree_hint}"

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

            # 2. 构建消息
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
                        "text": "继续执行任务。" if step > 0 else "开始执行任务。"
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

    async def _get_accessibility_hint(self) -> str:
        """获取无障碍树，压缩为简短文本提示（可选，失败不影响）"""
        try:
            tree = await self.client.accessibility_tree(max_depth=3)
            return self._format_tree(tree)
        except Exception:
            return ""

    def _format_tree(self, tree: dict) -> str:
        """格式化无障碍树为简短文本"""
        if not tree or "tree" not in tree:
            return ""

        lines = []

        def walk(node, depth=0):
            role = node.get("role", "?")
            name = node.get("name", "")
            bounds = node.get("bounds", {})

            # 只保留可交互元素
            if role in ("Button", "Edit", "MenuItem", "Hyperlink",
                        "ListItem", "CheckBox", "TabItem", "ComboBox"):
                line = f"{'  ' * depth}[{role}] {name}"
                if bounds:
                    line += f" @({bounds.get('x', 0)},{bounds.get('y', 0)})"
                lines.append(line)

            for child in node.get("children", []):
                walk(child, depth + 1)

        walk(tree["tree"])

        # 限制最多 50 行
        return "\n".join(lines[:50])

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
