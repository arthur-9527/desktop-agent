"""核心 Agent Loop 模块 - 三模型架构

架构：
- Planner (LLM): 主循环决策（每轮）
- Grounding (UI-TARS): 视觉定位（按需）
- Calibrator (LLM): 周期校准（每 N 步）
"""

import asyncio
import json
import re
from typing import Optional, List
from openai import AsyncOpenAI

from .desktoptools import DesktopClient
from .action_executor import ActionExecutor
from .accessibility_parser import (
    create_info_table,
    AccessibilityParser,
    GlobalInfo,
    diff_trees,
    diff_focused,
)
from .prompts import (
    PromptBuilder, 
    build_planner_prompt, 
    build_calibrator_prompt,
    build_vision_grounding_prompt,
    build_vision_verification_prompt,
    build_accessibility_verification_prompt,
    build_verification_prompt,
)
from .metrics import RunMetrics, StepMetric, MetricsTimer
from .config import Config


class ExecutionHistory:
    """执行历史管理"""
    
    def __init__(self, max_entries: int = 20):
        self.max_entries = max_entries
        self.entries: List[str] = []
    
    def add(self, entry: str):
        """添加执行记录"""
        self.entries.append(entry)
        # 滑动窗口
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
    
    def format(self) -> str:
        """格式化为文本"""
        if not self.entries:
            return "（暂无执行历史）"
        return "\n".join(self.entries)
    
    def summary(self, last_n: int = 5) -> str:
        """生成摘要（最近 N 条）"""
        recent = self.entries[-last_n:] if len(self.entries) > last_n else self.entries
        if not recent:
            return "（暂无执行记录）"
        return "\n".join(f"- {e}" for e in recent)


class ExecutionPlan:
    """执行计划管理"""
    
    def __init__(self, steps: List[str]):
        self.steps = steps  # 所有计划步骤
        self.current = 0    # 当前步骤索引
        self.completed = [] # 已完成的步骤索引列表
    
    def is_complete(self) -> bool:
        """计划是否全部完成"""
        return self.current >= len(self.steps)
    
    def next_step(self) -> Optional[str]:
        """获取下一步骤"""
        if self.is_complete():
            return None
        step = self.steps[self.current]
        self.completed.append(self.current)
        self.current += 1
        return step
    
    def format(self) -> str:
        """格式化为文本"""
        if not self.steps:
            return "（暂无执行计划，请先制定）"
        
        lines = ["### 当前执行计划", ""]
        for i, step in enumerate(self.steps):
            marker = "✓" if i in self.completed else "→"
            if i == self.current:
                marker = "▶"
            lines.append(f"{marker} 步骤{i+1}: {step}")
        return "\n".join(lines)
    
    def update(self, new_steps: List[str]):
        """更新执行计划"""
        self.steps = new_steps
        self.current = min(self.current, len(new_steps))
        self.completed = [c for c in self.completed if c < len(new_steps)]
    
    def summary(self) -> str:
        """生成计划摘要"""
        if not self.steps:
            return "暂无计划"
        completed_count = len(self.completed)
        current = "已完成" if self.is_complete() else f"进行中({completed_count}/{len(self.steps)})"
        return f"计划状态: {current} - {'; '.join(self.steps)}"


class DeskAgent:
    """三模型架构的桌面 Agent"""
    
    def __init__(
        self,
        agentdesk: DesktopClient,
        vision_model: AsyncOpenAI,  # UI-TARS
        planner_model: AsyncOpenAI,  # LLM for planning
        calibrator_model: Optional[AsyncOpenAI] = None,  # LLM for calibration
        config: Optional[Config] = None,
    ):
        self.client = agentdesk
        self.vision_model = vision_model  # UI-TARS
        self.planner_model = planner_model
        self.calibrator_model = calibrator_model or planner_model
        
        # 配置
        self.config = config or Config()
        self.max_steps = self.config.max_iterations
        self.context_window_size = self.config.context_window_size
        self.calibration_interval = self.config.calibration_interval
        self.debug = self.config.debug
        
        # 内部状态
        self.action_executor: Optional[ActionExecutor] = None
        self.global_info: Optional[GlobalInfo] = None
        self._accessibility_parser = AccessibilityParser()
        self._history = ExecutionHistory()
        self._metrics: Optional[RunMetrics] = None
        
        # 执行计划
        self._execution_plan: Optional[ExecutionPlan] = None
        
        # 视觉定位缓存
        self._vision_cache: dict = {}
    
    async def run(self, task: str) -> dict:
        """执行任务（三模型架构）
        
        Args:
            task: 任务描述
        
        Returns:
            {"success": bool, "message": str, "steps": int, "metrics": dict}
        """
        # 初始化 Metrics
        self._metrics = RunMetrics(task=task)
        
        # 获取初始无障碍树（复用同一棵树，避免重复 HTTP 调用）
        raw_tree_before = await self._get_accessibility_tree()
        info_table = await self._get_info_table_from_tree(raw_tree_before)
        
        # 获取操作系统类型
        self.global_info = self._accessibility_parser.parse(raw_tree_before, None, None)
        os_type = self.global_info.os if self.global_info else "Windows"
        print(f"[全局信息] 操作系统: {os_type}")
        
        # 初始化 ActionExecutor
        self.action_executor = ActionExecutor(self.client, os_type=os_type)
        
        # 初始化 PromptBuilder（复用缓存）
        self._prompt_builder = PromptBuilder(os_type=os_type)
        
        # 构建 Planner system prompt
        system_prompt = self._prompt_builder.build_system_message(
            global_info=info_table,
            execution_plan="",
            history="",
            instruction=task
        )
        
        # Planner 消息历史
        messages = [{"role": "system", "content": system_prompt}]
        
        # 主循环
        for step in range(self.max_steps):
            print(f"\n{'=' * 50}")
            print(f"Step {step + 1}/{self.max_steps}")
            
            step_metric = StepMetric(
                step=step + 1,
                action="",
                action_type="unknown"
            )
            
            # ========== Step 1: Planner 决策 ==========
            timer = MetricsTimer()
            timer.start()
            
            # 更新全局状态表（复用上一步的树，避免重复 HTTP 调用）
            info_table = await self._get_info_table_from_tree(raw_tree_before)
            
            # 构建 user message
            user_content = self._build_user_message(step, info_table)
            messages.append({"role": "user", "content": user_content})
            
            # 调用 Planner LLM（带重试机制）
            max_retries = 3
            planner_output = None
            
            for retry in range(max_retries):
                try:
                    response = await self.planner_model.chat.completions.create(
                        model=self.config.general_model,
                        messages=messages,
                        max_tokens=8192,
                        temperature=0.1,
                    )
                    
                    # 详细日志：记录 API 响应状态
                    if hasattr(response, 'choices') and response.choices:
                        choice = response.choices[0]
                        finish_reason = getattr(choice, 'finish_reason', 'unknown')
                        planner_output = choice.message.content or ""
                        
                        # 记录 token 使用情况
                        usage = getattr(response, 'usage', None)
                        if usage:
                            print(f"[Planner] Token 使用: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
                        
                        # 检查输出是否为空
                        if not planner_output.strip():
                            print(f"[Planner] 警告: 输出为空, finish_reason={finish_reason}")
                            if retry < max_retries - 1:
                                print(f"[Planner] 重试 {retry + 2}/{max_retries}...")
                                await asyncio.sleep(0.5)
                                continue
                        else:
                            # 输出正常，退出重试循环
                            break
                    else:
                        print(f"[Planner] 警告: API 响应无 choices")
                        if retry < max_retries - 1:
                            print(f"[Planner] 重试 {retry + 2}/{max_retries}...")
                            await asyncio.sleep(0.5)
                            continue
                        
                except Exception as e:
                    step_metric.planning_time_ms = timer.stop()
                    step_metric.error = str(e)
                    print(f"[Planner] API 调用异常: {type(e).__name__}: {e}")
                    if retry < max_retries - 1:
                        print(f"[Planner] 重试 {retry + 2}/{max_retries}...")
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        print(f"[Planner] 达到最大重试次数，跳过此步")
                        self._metrics.add_step(step_metric)
                        continue
            
            step_metric.planning_time_ms = timer.stop()
            
            # 检查是否有有效输出
            if not planner_output or not planner_output.strip():
                print(f"[Planner] 输出为空，跳过此步")
                self._history.add(f"Step {step + 1}: Planner 输出为空")
                step_metric.error = "Planner 输出为空"
                self._metrics.add_step(step_metric)
                continue
            
            print(f"[Planner] 输出: {planner_output[:200]}{'...' if len(planner_output) > 200 else ''}")
            
            # 解析 Planner 输出
            parsed = self._parse_planner_output(planner_output)
            
            if parsed is None:
                print(f"[Planner] JSON 解析失败")
                print(f"[Planner] 原始输出内容:\n{planner_output[:500]}{'...' if len(planner_output) > 500 else ''}")
                self._history.add(f"Step {step + 1}: 解析失败 - {planner_output[:100]}")
                step_metric.error = "JSON 解析失败"
                self._metrics.add_step(step_metric)
                continue
            
            use_vision_prompt = parsed.get("use_vision_prompt")
            action_str = parsed.get("action", "")
            
            # 提取计划状态
            plan_status = parsed.get("plan_status")
            if plan_status:
                steps = plan_status.get("steps", [])
                current = plan_status.get("current", 0)
                completed = plan_status.get("completed", [])
                if steps:
                    # 更新执行计划
                    self._execution_plan = ExecutionPlan(steps)
                    self._execution_plan.current = current
                    self._execution_plan.completed = completed
                    print(f"[计划] 更新计划: {self._execution_plan.summary()}")
            
            step_metric.action = action_str
            step_metric.action_type = self._extract_action_type(action_str)
            
            # 添加到消息历史
            messages.append({"role": "assistant", "content": planner_output})
            messages = self._trim_messages(messages)
            
            # ========== Step 2: 判断是否需要视觉定位 ==========
            if use_vision_prompt is not None:
                print(f"[Vision] 需要视觉定位: {use_vision_prompt}")
                step_metric.use_vision = True
                
                timer.start()
                
                # 调用 UI-TARS 视觉定位
                vision_result = await self._call_vision_for_grounding(use_vision_prompt)
                
                step_metric.vision_time_ms = timer.stop()
                
                if vision_result:
                    print(f"[Vision] 定位结果: {vision_result}")
                    self._history.add(f"Step {step + 1}: [视觉定位] {use_vision_prompt[:50]} → {vision_result[:100]}")
                    
                    # 将视觉结果注入上下文，继续下一步决策
                    messages.append({
                        "role": "user", 
                        "content": f"视觉定位结果: {vision_result}\n\n请根据这个信息重新决策下一步动作。"
                    })
                else:
                    # 视觉定位失败，注入恢复策略，让 Planner 知道如何应对
                    recovery_message = (
                        f"视觉定位失败，无法找到目标元素。\n\n"
                        f"建议恢复策略：\n"
                        f"1. 检查目标元素是否在可见区域内，尝试滚动页面寻找\n"
                        f"2. 使用无障碍树中的元素 ID 尝试点击（如已知）\n"
                        f"3. 尝试更通用的描述重新视觉定位\n"
                        f"4. 如果目标确实不可见，考虑使用快捷键或其他方式导航"
                    )
                    self._history.add(f"Step {step + 1}: [视觉定位失败] {use_vision_prompt[:50]}")
                    step_metric.error = "视觉定位失败"
                    messages.append({
                        "role": "user",
                        "content": recovery_message
                    })
                
                self._metrics.add_step(step_metric)
                continue  # 回到 Step 1，让 Planner 基于新信息决策
            
            # ========== Step 3: 执行操作 ==========
            action_parsed = self.action_executor.parse(action_str)
            action_type = action_parsed.get("action_type", "unknown")
            step_metric.action_type = action_type
            
            print(f"[Action] 类型: {action_type}")
            print(f"[Action] 完整动作: {action_str}")
            
            # 判断是否完成
            if action_type == "finished":
                message = action_parsed.get("action_inputs", {}).get("content", "Done")
                print(f"\n✓ 任务完成: {message}")
                self._history.add(f"Step {step + 1}: [完成] {message}")
                step_metric.success = True
                self._metrics.add_step(step_metric)
                self._metrics.finalize(success=True)
                return self._build_result(True, message, step + 1)
            
            if action_type == "failed":
                message = action_parsed.get("action_inputs", {}).get("content", "Failed")
                print(f"\n✗ 任务失败: {message}")
                self._history.add(f"Step {step + 1}: [失败] {message}")
                step_metric.error = message
                self._metrics.add_step(step_metric)
                self._metrics.finalize(success=False)
                return self._build_result(False, message, step + 1)
            
            # 调试模式
            if self.debug:
                input("按 Enter 执行此动作...")

            # ========== Step 3.5: 执行前采集快照（用于 accessibility/mixed 验证） ==========
            # 提前解析验证配置
            verification = parsed.get("verification", {}) or {}
            verification_method = verification.get("method", "visual") if isinstance(verification, dict) else "visual"
            verification_prompt = verification.get("prompt", "") if isinstance(verification, dict) else str(verification)

            tree_before_action = None
            focused_before_action = None
            if verification_method in ("accessibility", "mixed"):
                print(f"[验证] 方法: {verification_method}，验证目标: {verification_prompt}")
                print(f"[验证] 执行前采集树和聚焦快照")
                tree_before_action = await self._get_accessibility_tree_depth(15)
                try:
                    focused_before_action = await self.client.accessibility_focused()
                except Exception as e:
                    print(f"[验证] 获取聚焦元素失败: {e}")

            # ========== Step 4: 执行操作 ==========
            timer.start()
            try:
                # 获取输入法状态（从托盘信息）
                ime_status = self._get_ime_status()
                await self.action_executor.execute(action_parsed, ime_status)
                step_metric.execution_time_ms = timer.stop()
            except Exception as e:
                step_metric.execution_time_ms = timer.stop()
                step_metric.error = str(e)
                print(f"[Action] 执行失败: {e}")
                self._history.add(f"Step {step + 1}: [执行失败] {action_type} - {e}")
                self._metrics.add_step(step_metric)
                continue

            # 特殊处理：check_input 结果注入上下文
            if action_type == "check_input":
                check_result = self.action_executor.get_last_input_check_result()
                self._history.add(f"Step {step + 1}: [检查输入框] {check_result}")
                step_metric.success = True
                self._metrics.add_step(step_metric)

                # 注入结果到消息历史，让 Planner 决定下一步
                messages.append({
                    "role": "user",
                    "content": f"输入框检查结果: {check_result}\n\n请根据这个信息决定输入策略 (replace/append)。"
                })
                continue  # 回到 Step 1，让 Planner 基于检查结果决策

            # 等待界面更新
            await asyncio.sleep(0.5)

            # ========== Step 5: 验证（三种方式：accessibility/visual/mixed） ==========
            if verification_prompt:
                timer.start()
                print(f"[验证] 开始验证，验证目标: {verification_prompt}")

                # 根据验证方法选择验证方式
                if verification_method == "accessibility":
                    success, reason, verification_time = await self._verify_with_accessibility(
                        verification_prompt, tree_before_action, focused_before_action
                    )
                elif verification_method == "mixed":
                    success, reason, verification_time = await self._verify_mixed(
                        verification_prompt, tree_before_action, focused_before_action
                    )
                else:  # 默认 visual
                    success, reason, verification_time = await self._verify_with_vision(verification_prompt)

                step_metric.verification_time_ms = verification_time

                if success:
                    print(f"[验证] 操作成功: {reason}")
                    step_metric.success = True
                    self._history.add(f"Step {step + 1}: [成功] {action_type} - {reason}")
                else:
                    print(f"[验证] 操作失败: {reason}")
                    step_metric.success = False
                    self._history.add(f"Step {step + 1}: [失败] {action_type} - {reason}")

                # 将验证结果注入上下文，让 Planner 下一步决策时能直接看到
                messages.append({
                    "role": "user",
                    "content": f"验证结果: {'成功' if success else '失败'} - {reason}"
                })
            else:
                # 没有验证标准，默认成功
                print(f"[验证] 无验证标准，默认成功")
                step_metric.success = True
                step_metric.verification_time_ms = 0
                self._history.add(f"Step {step + 1}: [成功] {action_type} - 无验证标准")

            # 更新无障碍树和全局状态表
            raw_tree_after = await self._get_accessibility_tree()
            self.global_info = self._accessibility_parser.parse(raw_tree_after, None, None)

            # 更新 info_table 为最新状态（用于校准后的 system prompt 重建）
            info_table = await self._get_info_table_from_tree(raw_tree_after)
            
            # ========== Step 5: 校准检查 ==========
            if self._should_calibrate(step + 1):
                print(f"[Calibrator] 触发校准...")
                timer.start()
                calibration_result = await self._run_calibration(task)
                self._metrics.calibrator_time_ms += timer.stop()
                if calibration_result:
                    self._metrics.calibrator_calls += 1
                    # 处理校准结果中的计划更新
                    plan_updated = self._process_calibration_result(calibration_result)
                    if plan_updated:
                        # 更新 Planner prompt 中的系统提示（使用最新的 info_table 和复用的 PromptBuilder）
                        new_system_prompt = self._prompt_builder.build_system_message(
                            global_info=info_table,
                            execution_plan=self._execution_plan.format() if self._execution_plan else "",
                            history=self._history.format(),
                            instruction=task
                        )
                        messages[0]["content"] = new_system_prompt
                    # 注入校准结果到上下文
                    messages.append({
                        "role": "user",
                        "content": f"[校准反馈]\n{calibration_result}"
                    })
            
            # 更新基准树
            raw_tree_before = raw_tree_after
            
            self._metrics.add_step(step_metric)
        
        # 达到最大步数
        self._metrics.finalize(success=False)
        return self._build_result(False, "达到最大步数限制", self.max_steps)
    
    def _parse_planner_output(self, output: str) -> Optional[dict]:
        """解析 Planner 输出的 JSON"""
        # 清洗输出
        output = output.strip()
        
        # 尝试提取 JSON
        try:
            # 尝试直接解析
            return json.loads(output)
        except json.JSONDecodeError:
            pass
        
        # 尝试从 markdown 代码块提取
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', output)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试匹配 JSON 对象（扩展以支持 verification 字段）
        json_match = re.search(r'\{[^{}]*"(use_vision_prompt|action|verification)"[^{}]*\}', output)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _parse_verification_result(self, output: str) -> Optional[dict]:
        """解析视觉验证返回的 JSON"""
        output = output.strip()
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            pass
        
        # 尝试从 markdown 代码块提取
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', output)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试匹配 JSON 对象
        json_match = re.search(r'\{[^{}]*"success"[^{}]*\}', output)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _extract_action_type(self, action_str: str) -> str:
        """从 action 字符串提取动作类型"""
        if not action_str:
            return "unknown"
        
        # 匹配动作类型
        match = re.match(r'(\w+)\s*\(', action_str)
        if match:
            return match.group(1).lower()
        
        return "unknown"
    
    def _build_user_message(self, step: int, info_table: str) -> str:
        """构建 user message"""
        if step == 0:
            text = "开始执行任务。"
        else:
            text = "继续执行任务。"
        
        if info_table:
            text += f"\n\n{info_table}"
        
        # 添加执行历史
        history_text = self._history.format()
        if history_text and step > 0:
            text += f"\n\n最近的执行记录:\n{history_text}"
        
        return text
    
    def _process_calibration_result(self, calibration_result: str) -> bool:
        """处理校准结果，返回是否有计划更新
        
        使用正则表达式替代简单字符串匹配，增强对格式变体的容错：
        - 支持中英文冒号（: / ：）
        - 支持多种空格格式
        - 正确解析多位数字的步骤编号（如 "10.", "11."）
        
        Args:
            calibration_result: 校准结果文本
        
        Returns:
            是否有计划更新
        """
        # 检查是否有更新计划的指示（支持中英文冒号）
        if re.search(r'更新计划\s*[:：]\s*是', calibration_result):
            # 尝试提取新计划（支持中英文冒号，处理多位数字步骤）
            new_plan_match = re.search(r'新计划\s*[:：]\s*(.*?)(?:\n\s*\n|\Z)', calibration_result, re.DOTALL)
            if new_plan_match:
                new_plan_text = new_plan_match.group(1).strip()
                # 解析新计划步骤：使用正则正确解析数字步骤
                new_steps = []
                for line in new_plan_text.split('\n'):
                    # 使用正则匹配步骤编号：支持 "1.", "10.", "1)", "10)", "1、" 等格式
                    line_match = re.match(r'^\s*(?:\d+[.\)]\s*|[一二三四五六七八九十]+[、.]\s*)?(.+)', line)
                    if line_match:
                        step_text = line_match.group(1).strip()
                        if step_text:
                            new_steps.append(step_text)
                
                if new_steps:
                    if self._execution_plan:
                        self._execution_plan.update(new_steps)
                    else:
                        self._execution_plan = ExecutionPlan(new_steps)
                    print(f"[Calibrator] 计划已更新: {self._execution_plan.summary()}")
                    return True
        return False
    
    async def _call_vision_for_grounding(
        self, 
        target_description: str
    ) -> Optional[str]:
        """调用 UI-TARS 进行视觉定位
        
        Args:
            target_description: 目标元素描述
        
        Returns:
            包含归一化坐标的结果描述，失败返回 None
        """
        try:
            # 截图（不带网格）
            screenshot = await self.client.screenshot()

            # 构建视觉定位 prompt
            vision_prompt = build_vision_grounding_prompt(target_description)
            
            # 调用 UI-TARS
            response = await self.vision_model.chat.completions.create(
                model=self.config.vision_model,
                messages=[
                    {
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
                                "text": vision_prompt
                            }
                        ]
                    }
                ],
                max_tokens=256,
            )
            
            result = response.choices[0].message.content or ""
            
            # 标准化坐标格式：将 <point x1="..." y1="..."> 转换为 <point>x y</point>
            result = self._normalize_point_format(result)
            
            # 解析像素坐标并转换为归一化坐标 (0-1000)
            pixel_x, pixel_y = self._parse_pixel_coordinates(result)
            if pixel_x is not None and pixel_y is not None:
                normalized_x, normalized_y = self._pixel_to_normalized(pixel_x, pixel_y)
                result = f"目标已定位: 归一化坐标 ({normalized_x}, {normalized_y})"
                print(f"[Vision] 像素坐标 ({pixel_x}, {pixel_y}) -> 归一化坐标 ({normalized_x}, {normalized_y})")
            
            return result
            
        except Exception as e:
            print(f"[Vision] 调用失败: {e}")
            return None
    
    async def _verify_with_vision(self, verification_prompt: str) -> tuple:
        """调用视觉模型验证操作是否成功
        
        Args:
            verification_prompt: 验证标准
        
        Returns:
            (success, reason) 元组，success 为布尔值，reason 为理由
        """
        timer = MetricsTimer()
        timer.start()
        
        try:
            # 截图
            screenshot = await self.client.screenshot()
            
            # 构建视觉验证 prompt
            verification_prompt_text = build_verification_prompt(verification_prompt)
            
            # 调用视觉模型
            response = await self.vision_model.chat.completions.create(
                model=self.config.vision_model,
                messages=[
                    {
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
                                "text": verification_prompt_text
                            }
                        ]
                    }
                ],
                max_tokens=128,
            )
            
            result = response.choices[0].message.content or ""
            parsed = self._parse_verification_result(result)
            
            if parsed:
                success = parsed.get("success", False)
                reason = parsed.get("reason", "解析失败")
            else:
                success = False
                reason = f"验证解析失败: {result[:100]}"
            
            return (success, reason, timer.stop())
            
        except Exception as e:
            print(f"[验证] 视觉验证异常: {e}")
            return (False, f"视觉验证异常: {str(e)}", timer.stop())
    
    def _normalize_point_format(self, text: str) -> str:
        """标准化坐标格式
        
        将视觉模型返回的多种坐标格式统一转换为 <point>x y</point> 格式
        支持的输入格式：
        - <point x1="157" y1="44"> -> <point>157 44</point>
        - <point x1="157" y1="44" alt="..."> -> <point>157 44</point>
        - <point>157 44</point> -> 保持不变
        
        Args:
            text: 包含坐标的文本
        
        Returns:
            标准化后的文本
        """
        # 匹配 <point x1="..." y1="..."> 格式
        pattern = r'<point\s+x1="(\d+)"\s+y1="(\d+)"[^>]*>'
        
        def replace_point(match):
            x = match.group(1)
            y = match.group(2)
            return f'<point>{x} {y}</point>'
        
        # 替换所有匹配项
        normalized = re.sub(pattern, replace_point, text)
        
        # 如果有变化，记录日志
        if normalized != text:
            print(f"[Vision] 坐标格式已标准化")
        
        return normalized
    
    def _parse_pixel_coordinates(self, text: str) -> tuple:
        """从文本中解析像素坐标
        
        从 UI-TARS 返回的文本中提取 <point>x y</point> 格式的像素坐标
        
        Args:
            text: 包含坐标的文本
        
        Returns:
            (pixel_x, pixel_y) 或 (None, None) 如果未找到坐标
        """
        # 匹配 <point>x y</point> 格式
        match = re.search(r'<point\s+(\d+)\s+(\d+)[\s>]', text)
        if match:
            return int(match.group(1)), int(match.group(2))
        
        # 尝试 <point x1="..." y1="..."> 格式
        match = re.search(r'<point\s+x1="(\d+)"\s+y1="(\d+)"[^>]*>', text)
        if match:
            return int(match.group(1)), int(match.group(2))
        
        return None, None
    
    def _pixel_to_normalized(self, pixel_x: int, pixel_y: int) -> tuple:
        """将像素坐标转换为归一化坐标 (0-1000)
        
        使用截图配置的固定尺寸进行转换：
        SCREENSHOT_MAX_WIDTH = 1366
        SCREENSHOT_MAX_HEIGHT = 768
        
        Args:
            pixel_x: 像素 X 坐标
            pixel_y: 像素 Y 坐标
        
        Returns:
            (normalized_x, normalized_y)
        """
        width = self.config.screenshot_max_width   # 1366
        height = self.config.screenshot_max_height  # 768
        
        normalized_x = int(pixel_x * 1000 / width)
        normalized_y = int(pixel_y * 1000 / height)
        
        return normalized_x, normalized_y
    
    def _should_calibrate(self, step: int) -> bool:
        """判断是否应该触发校准"""
        if self.calibration_interval <= 0:
            return False
        return step > 1 and step % self.calibration_interval == 0
    
    async def _run_calibration(self, task: str) -> Optional[str]:
        """运行校准检查"""
        try:
            history_summary = self._history.summary(last_n=5)
            global_info = await self._get_global_info_table()
            
            # 添加执行计划信息
            execution_plan = ""
            if self._execution_plan:
                execution_plan = self._execution_plan.format()
            
            calibrator_prompt = build_calibrator_prompt(
                task=task,
                history_summary=history_summary,
                global_info=global_info,
                execution_plan=execution_plan
            )
            
            response = await self.calibrator_model.chat.completions.create(
                model=self._get_calibration_model_name(),
                messages=[{"role": "user", "content": calibrator_prompt}],
                max_tokens=256,
                temperature=0.3,
            )
            
            result = response.choices[0].message.content or ""
            print(f"[Calibrator] 结果: {result[:200]}")
            return result
            
        except Exception as e:
            print(f"[Calibrator] 调用失败: {e}")
            return None
    
    def _get_calibration_model_name(self) -> str:
        """获取校准模型名称"""
        if self.config.calibration_model:
            return self.config.calibration_model
        return self.config.general_model
    
    async def _get_accessibility_tree(self) -> dict:
        """获取无障碍树"""
        try:
            return await self.client.accessibility_tree(max_depth=10)
        except Exception as e:
            print(f"[Accessibility] 获取失败: {e}")
            return {}
    
    async def _get_global_info_struct(self) -> Optional[GlobalInfo]:
        """获取结构化的全局动态信息"""
        try:
            tree = await self.client.accessibility_tree(max_depth=10)
            return self._accessibility_parser.parse(tree, None, None)
        except Exception as e:
            print(f"[全局信息] 结构化数据获取失败: {e}")
            return None
    
    async def _get_global_info_table(self) -> str:
        """获取全局动态信息表（完整 HTTP 调用）"""
        try:
            tree = await self.client.accessibility_tree(max_depth=10)
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
            
            return create_info_table(tree, mouse_pos, focused)
        except Exception as e:
            print(f"[全局信息] 获取失败: {e}")
            return ""
    
    async def _get_info_table_from_tree(self, tree: dict) -> str:
        """从已有的树数据生成信息表（避免重复 HTTP 调用）
        
        Args:
            tree: 已获取的无障碍树
        
        Returns:
            格式化的信息表字符串
        """
        try:
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
            
            return create_info_table(tree, mouse_pos, focused)
        except Exception as e:
            print(f"[全局信息] 生成失败: {e}")
            return ""
    
    def _trim_messages(self, messages: list) -> list:
        """滑动窗口：保留 system + 最近 N 轮完整对话
        
        每轮对话包含 user + assistant 两条消息。裁剪时确保不拆散对话对。
        """
        if len(messages) <= 1:
            return messages
        
        system_msg = messages[0]
        conversation_msgs = messages[1:]
        keep_count = self.context_window_size * 2  # 保留 N 轮对话
        keep_pairs = self.context_window_size  # 保留 N 轮完整对话
        
        if len(conversation_msgs) <= keep_count:
            return messages
        
        # 确保从 user 消息开始裁剪（不拆散对话对）
        # 每轮对话 = user + assistant = 2 条消息
        conversation_msgs = conversation_msgs[-keep_pairs * 2:]
        
        print(f"[Context] 裁剪到最近 {keep_pairs} 轮对话（{len(conversation_msgs)} 条消息）")
        
        return [system_msg] + conversation_msgs
    
    def _build_result(self, success: bool, message: str, steps: int) -> dict:
        """构建返回结果"""
        return {
            "success": success,
            "message": message,
            "steps": steps,
            "metrics": self._metrics.to_dict() if self._metrics else {}
        }
    
    def _get_ime_status(self) -> str:
        """从全局状态表获取输入法状态
        
        Returns:
            输入法状态字符串，如 "中文模式" 或 "英文模式"，未知则返回空字符串
        """
        if not self.global_info:
            return ""
        
        # 从托盘项中查找输入法状态
        for tray_item in self.global_info.tray_items:
            extra = tray_item.extra or ""
            if "中文模式" in extra or "英文模式" in extra:
                return extra
        
        # 也检查托盘项名称
        for tray_item in self.global_info.tray_items:
            name = tray_item.name or ""
            if "中文" in name:
                return "中文模式"
            elif "英文" in name or "英语" in name:
                return "英文模式"
        
        return ""
    
    async def _get_accessibility_tree_depth(self, max_depth: int = 15) -> dict:
        """获取指定深度的无障碍树
        
        Args:
            max_depth: 最大深度（默认15）
        
        Returns:
            无障碍树数据
        """
        try:
            return await self.client.accessibility_tree(max_depth=max_depth)
        except Exception as e:
            print(f"[Accessibility] 获取深度{max_depth}树失败: {e}")
            return {}
    
    async def _verify_with_accessibility(
        self,
        verification_prompt: str,
        tree_before: dict,
        focused_before: dict = None,
    ) -> tuple:
        """使用无障碍树差异 + 聚焦元素变化验证操作是否成功

        同时对比两个维度的数据：
        1. 聚焦元素变化（从 diff_a11y.py 方案借鉴）
        2. 无障碍树结构变化

        Args:
            verification_prompt: 验证标准描述
            tree_before: 操作前的无障碍树
            focused_before: 操作前的聚焦元素 {"element": {...}}

        Returns:
            (success, reason, time_ms) 元组
        """
        timer = MetricsTimer()
        timer.start()

        try:
            print(f"[验证] 无障碍树验证 - 验证目标: {verification_prompt}")
            print("[验证] 获取执行后无障碍树...")
            tree_after = await self._get_accessibility_tree_depth(15)

            # 获取操作后聚焦元素
            focused_after = None
            try:
                focused_after = await self.client.accessibility_focused()
            except Exception as e:
                print(f"[验证] 获取聚焦元素失败: {e}")

            # 维度 1: 对比聚焦元素
            focus_diff, focus_changed = diff_focused(focused_before, focused_after)
            print(f"[验证] 聚焦变化: {focus_diff[:200]}")

            # 维度 2: 对比无障碍树
            print("[验证] 对比无障碍树差异...")
            diff_result = diff_trees(tree_before, tree_after)
            tree_diff = diff_result.format_for_llm(max_items=15) if diff_result.changed else "无障碍树结构无变化"
            print(f"[验证] 树差异:\n{tree_diff[:300]}")

            # 两个维度都无变化时直接返回
            if not diff_result.changed and not focus_changed:
                print("[验证] 聚焦元素和无障碍树均无变化")
                return (False, "聚焦元素和无障碍树均无变化，操作可能未生效", timer.stop())

            # 调用 LLM 分析两个维度的差异
            verification_prompt_text = build_accessibility_verification_prompt(
                verification_prompt=verification_prompt,
                focus_diff=focus_diff,
                tree_diff=tree_diff,
            )

            response = await self.planner_model.chat.completions.create(
                model=self.config.general_model,
                messages=[{"role": "user", "content": verification_prompt_text}],
                max_tokens=8192,
                temperature=0.1,
            )

            result = response.choices[0].message.content or ""
            parsed = self._parse_verification_result(result)

            if parsed:
                success = parsed.get("success", False)
                reason = parsed.get("reason", "解析失败")
            else:
                success = False
                reason = f"无障碍树验证解析失败: {result[:100]}"

            return (success, reason, timer.stop())

        except Exception as e:
            print(f"[验证] 无障碍树验证异常: {e}")
            return (False, f"无障碍树验证异常: {str(e)}", timer.stop())

    async def _verify_mixed(
        self,
        verification_prompt: str,
        tree_before: dict,
        focused_before: dict = None,
    ) -> tuple:
        """使用混合验证（无障碍树 + 聚焦 + 视觉）

        Args:
            verification_prompt: 验证标准描述
            tree_before: 操作前的无障碍树
            focused_before: 操作前的聚焦元素

        Returns:
            (success, reason, time_ms) 元组
        """
        timer = MetricsTimer()
        timer.start()

        try:
            print(f"[验证] 混合验证 - 验证目标: {verification_prompt}")
            print("[验证] 混合验证 - 第一步：无障碍树 + 聚焦验证")
            accessibility_success, accessibility_reason, _ = await self._verify_with_accessibility(
                verification_prompt, tree_before, focused_before
            )

            # 如果无障碍树验证通过，直接返回成功
            if accessibility_success:
                print("[验证] 无障碍树验证通过，混合验证成功")
                return (True, f"无障碍树验证通过: {accessibility_reason}", timer.stop())

            # 如果无障碍树验证失败，进行视觉验证作为补充
            print("[验证] 混合验证 - 第二步：视觉验证补充")
            vision_success, vision_reason, _ = await self._verify_with_vision(verification_prompt)

            # 综合判断
            if vision_success:
                print("[验证] 视觉验证通过，混合验证成功")
                return (True, f"视觉验证通过(无障碍树延迟): {vision_reason}", timer.stop())

            # 两者都失败
            print("[验证] 无障碍树和视觉验证都失败")
            return (False, f"无障碍树: {accessibility_reason}; 视觉: {vision_reason}", timer.stop())

        except Exception as e:
            print(f"[验证] 混合验证异常: {e}")
            return (False, f"混合验证异常: {str(e)}", timer.stop())
