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
    create_focused_element_table,
    AccessibilityParser,
    GlobalInfo,
    diff_trees,
    diff_focused,
)
from .prompts import (
    PromptBuilder, 
    build_planner_prompt, 
    build_planning_prompt,
    build_vision_grounding_prompt,
)
from .prompts.verification import (
    build_verification_message,
)
from .metrics import RunMetrics, StepMetric, MetricsTimer
from .config import Config
from .logger import get_logger

logger = get_logger(__name__)


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
    
    async def _make_plan(self, task: str, info_table: str, focused_info: str) -> Optional[dict]:
        """调用 Calibrator 模型制定执行计划
        
        Args:
            task: 用户任务描述
            info_table: 全局动态信息表
            focused_info: 当前聚焦元素信息
            
        Returns:
            包含 steps 列表的字典，失败返回 None
        """
        logger.info("=" * 50)
        logger.info("[Planner] 开始制定执行计划")
        logger.info(f"[Planner] 任务: {task[:200]}{'...' if len(task) > 200 else ''}")
        
        try:
            # 构建计划制定 prompt
            planning_prompt = build_planning_prompt(
                task=task,
                global_info=info_table,
                focused_info=focused_info,
            )
            
            # 调用 Calibrator 模型
            response = await self.calibrator_model.chat.completions.create(
                model=self._get_verification_model_name(),
                messages=[{"role": "user", "content": planning_prompt}],
                max_tokens=8192,
                temperature=0.1,
            )
            
            output = response.choices[0].message.content or ""
            
            # 记录 token 使用
            usage = getattr(response, 'usage', None)
            if usage:
                logger.info(f"[Planner] Token 使用: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
            
            # 解析 JSON
            result = self._parse_planner_output(output)
            if result and result.get("steps"):
                steps = result["steps"]
                logger.info(f"[Planner] 计划制定成功: {len(steps)} 个步骤")
                for i, step in enumerate(steps):
                    logger.info(f"[Planner]   步骤 {i+1}: {step}")
                return result
            else:
                logger.warning(f"[Planner] 计划制定失败: 输出中缺少 steps")
                logger.debug(f"[Planner] 原始输出:\n{output[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"[Planner] 调用异常: {type(e).__name__}: {e}")
            return None
    
    async def run(self, task: str) -> dict:
        """执行任务（Planner + Worker 双架构）
        
        Planner (Calibrator 模型): 任务开始时制定全局执行计划
        Worker (Planner 模型): 每步执行动作
        
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
        
        # 获取聚焦元素
        focused_element = None
        try:
            focused_element = await self.client.accessibility_focused()
        except Exception as e:
            logger.warning(f"[聚焦元素] 获取失败: {e}")
        
        # 格式化聚焦元素信息
        focused_info = create_focused_element_table(focused_element)
        
        # 获取操作系统类型
        self.global_info = self._accessibility_parser.parse(raw_tree_before, None, focused_element)
        os_type = self.global_info.os if self.global_info else "Windows"
        logger.info(f"[全局信息] 操作系统: {os_type}")
        
        # 初始化 ActionExecutor
        self.action_executor = ActionExecutor(self.client, os_type=os_type)
        
        # 初始化 PromptBuilder（复用缓存）
        self._prompt_builder = PromptBuilder(os_type=os_type)
        
        # ========== 阶段 0: Planner 制定执行计划 ==========
        plan_result = await self._make_plan(task, info_table, focused_info)
        if plan_result and plan_result.get("steps"):
            self._execution_plan = ExecutionPlan(plan_result["steps"])
            logger.info(f"[Planner] 最终计划: {self._execution_plan.summary()}")
        else:
            logger.warning("[Planner] 计划制定失败，将在执行中逐步制定")
        
        # 构建 Worker system prompt（包含已制定的计划）
        execution_plan_text = self._execution_plan.format() if self._execution_plan else ""
        system_prompt = self._prompt_builder.build_system_message(
            global_info=info_table,
            focused_info=focused_info,
            execution_plan=execution_plan_text,
            history="",
            instruction=task
        )
        
        # Worker 消息历史
        messages = [{"role": "system", "content": system_prompt}]
        
        # 主循环（Worker 执行）
        for step in range(self.max_steps):
            logger.info("=" * 50)
            logger.info(f"Step {step + 1}/{self.max_steps}")
            
            step_metric = StepMetric(
                step=step + 1,
                action="",
                action_type="unknown"
            )
            
            # ========== Step 1: Worker 决策 ==========
            timer = MetricsTimer()
            timer.start()
            
            # 更新全局状态表（复用上一步的树，避免重复 HTTP 调用）
            info_table = await self._get_info_table_from_tree(raw_tree_before)
            
            # 构建 user message
            user_content = self._build_user_message(step, info_table)
            messages.append({"role": "user", "content": user_content})
            
            # 调用 Worker 模型（带重试机制）
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
                            logger.info(f"[Worker] Token 使用: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
                        
                        # 检查输出是否为空
                        if not planner_output.strip():
                            logger.warning(f"[Worker] 输出为空, finish_reason={finish_reason}")
                            if retry < max_retries - 1:
                                logger.info(f"[Worker] 重试 {retry + 2}/{max_retries}...")
                                await asyncio.sleep(0.5)
                                continue
                        else:
                            # 输出正常，退出重试循环
                            break
                    else:
                        logger.warning(f"[Worker] API 响应无 choices")
                        if retry < max_retries - 1:
                            logger.info(f"[Worker] 重试 {retry + 2}/{max_retries}...")
                            await asyncio.sleep(0.5)
                            continue
                        
                except Exception as e:
                    step_metric.planning_time_ms = timer.stop()
                    step_metric.error = str(e)
                    logger.error(f"[Worker] API 调用异常: {type(e).__name__}: {e}")
                    if retry < max_retries - 1:
                        logger.info(f"[Worker] 重试 {retry + 2}/{max_retries}...")
                        await asyncio.sleep(0.5)
                        continue
                    else:
                        logger.warning(f"[Worker] 达到最大重试次数，跳过此步")
                        self._metrics.add_step(step_metric)
                        continue
            
            step_metric.planning_time_ms = timer.stop()
            
            # 检查是否有有效输出
            if not planner_output or not planner_output.strip():
                logger.warning(f"[Worker] 输出为空，跳过此步")
                self._history.add(f"Step {step + 1}: Worker 输出为空")
                step_metric.error = "Planner 输出为空"
                self._metrics.add_step(step_metric)
                continue
            
            logger.info(f"[Worker] 输出: {planner_output[:200]}{'...' if len(planner_output) > 200 else ''}")
            
            # 解析 Planner 输出
            parsed = self._parse_planner_output(planner_output)
            
            if parsed is None:
                logger.warning(f"[Worker] JSON 解析失败")
                logger.debug(f"[Worker] 原始输出内容:\n{planner_output[:500]}{'...' if len(planner_output) > 500 else ''}")
                self._history.add(f"Step {step + 1}: 解析失败 - {planner_output[:100]}")
                step_metric.error = "JSON 解析失败"
                self._metrics.add_step(step_metric)
                continue
            
            use_vision_prompt = parsed.get("use_vision_prompt")
            action_str = parsed.get("action", "")
            
            step_metric.action = action_str
            step_metric.action_type = self._extract_action_type(action_str)
            
            # 添加到消息历史
            messages.append({"role": "assistant", "content": planner_output})
            messages = self._trim_messages(messages)
            
            # ========== Step 2: 判断是否需要视觉定位 ==========
            if use_vision_prompt is not None:
                logger.info(f"[Vision] 需要视觉定位: {use_vision_prompt}")
                step_metric.use_vision = True
                
                timer.start()
                
                # 调用 UI-TARS 视觉定位
                vision_result = await self._call_vision_for_grounding(use_vision_prompt)
                
                step_metric.vision_time_ms = timer.stop()
                
                if vision_result:
                    logger.info(f"[Vision] 定位结果: {vision_result}")
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
            
            logger.info(f"[Action] 类型: {action_type}")
            logger.info(f"[Action] 完整动作: {action_str}")
            
            # 判断是否完成
            if action_type == "finished":
                message = action_parsed.get("action_inputs", {}).get("content", "Done")
                logger.info(f"\n✓ 任务完成: {message}")
                self._history.add(f"Step {step + 1}: [完成] {message}")
                step_metric.success = True
                self._metrics.add_step(step_metric)
                self._metrics.finalize(success=True)
                return self._build_result(True, message, step + 1)
            
            if action_type == "failed":
                message = action_parsed.get("action_inputs", {}).get("content", "Failed")
                logger.info(f"\n✗ 任务失败: {message}")
                self._history.add(f"Step {step + 1}: [失败] {message}")
                step_metric.error = message
                self._metrics.add_step(step_metric)
                self._metrics.finalize(success=False)
                return self._build_result(False, message, step + 1)
            
            # 调试模式
            if self.debug:
                input("按 Enter 执行此动作...")

            # ========== Step 3.5: 执行前采集快照（用于统一验证） ==========
            # 提前解析验证配置
            verification = parsed.get("verification", {}) or {}
            verification_prompt = verification.get("prompt", "") if isinstance(verification, dict) else str(verification)

            tree_before_action = None
            focused_before_action = None
            if verification_prompt:
                logger.info(f"[验证] 验证目标: {verification_prompt}")
                logger.info(f"[验证] 执行前采集树和聚焦快照")
                tree_before_action = await self._get_accessibility_tree_depth(15)
                try:
                    focused_before_action = await self.client.accessibility_focused()
                except Exception as e:
                    logger.warning(f"[验证] 获取聚焦元素失败: {e}")

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
                logger.error(f"[Action] 执行失败: {e}")
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

            # ========== Step 5: 验证（统一验证流程） ==========
            if verification_prompt:
                timer.start()
                logger.info(f"[验证] 开始验证，验证目标: {verification_prompt}")

                # 获取操作后的无障碍树和截图
                tree_after_action = await self._get_accessibility_tree_depth(15)
                screenshot_after = await self.client.screenshot()

                # 获取操作后聚焦元素
                focused_after_action = None
                try:
                    focused_after_action = await self.client.accessibility_focused()
                except Exception as e:
                    logger.warning(f"[验证] 获取聚焦元素失败: {e}")

                # 计算聚焦变化
                focus_diff, focus_changed = diff_focused(focused_before_action, focused_after_action)
                logger.info(f"[验证] 聚焦变化: {focus_diff[:200]}")

                # 计算无障碍树差异
                diff_result = diff_trees(tree_before_action, tree_after_action)
                tree_diff = diff_result.format_for_llm(max_items=15) if diff_result.changed else "无障碍树结构无变化"
                logger.info(f"[验证] 树差异:\n{tree_diff[:300]}")

                # 调用校准模型进行统一验证
                verification_message = build_verification_message(
                    verification_prompt=verification_prompt,
                    focus_diff=focus_diff,
                    tree_diff=tree_diff,
                    screenshot_base64=screenshot_after.get("base64", ""),
                )

                response = await self.calibrator_model.chat.completions.create(
                    model=self._get_verification_model_name(),
                    messages=[verification_message],
                    max_tokens=8192,
                    temperature=0.1,
                )

                result = response.choices[0].message.content or ""
                parsed = self._parse_verification_result(result)

                step_metric.verification_time_ms = timer.stop()

                if parsed:
                    success = parsed.get("success", False)
                    reason = parsed.get("reason", "解析失败")
                else:
                    success = False
                    reason = f"验证解析失败: {result[:100]}"

                if success:
                    logger.info(f"[验证] 操作成功: {reason}")
                    step_metric.success = True
                    self._history.add(f"Step {step + 1}: [成功] {action_type} - {reason}")
                else:
                    logger.warning(f"[验证] 操作失败: {reason}")
                    step_metric.success = False
                    self._history.add(f"Step {step + 1}: [失败] {action_type} - {reason}")

                # 将验证结果注入上下文，让 Planner 下一步决策时能直接看到
                messages.append({
                    "role": "user",
                    "content": f"验证结果: {'成功' if success else '失败'} - {reason}"
                })
            else:
                # 没有验证标准，默认成功
                logger.info(f"[验证] 无验证标准，默认成功")
                step_metric.success = True
                step_metric.verification_time_ms = 0
                self._history.add(f"Step {step + 1}: [成功] {action_type} - 无验证标准")

            # 更新无障碍树和全局状态表
            raw_tree_after = await self._get_accessibility_tree()
            self.global_info = self._accessibility_parser.parse(raw_tree_after, None, None)

            # 更新 info_table 为最新状态（用于校准后的 system prompt 重建）
            info_table = await self._get_info_table_from_tree(raw_tree_after)
            
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
        
        # 尝试直接解析
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
    
    async def _call_vision_for_grounding(
        self, 
        target_description: str
    ) -> Optional[str]:
        """调用 UI-TARS 进行视觉定位（中文 prompt + JSON 格式输出）
        
        流程：
        1. 解析 JSON 输出
        2. found=true + x/y → 计算归一化坐标，返回 "目标已定位: 归一化坐标 (nx, ny)"
        3. found=false + desc → 返回 desc 文本（含多个候选元素坐标），LLM 自行选择
        4. JSON 格式解析失败 → 返回原始输出 + 转换公式，LLM 自行提取
        
        Args:
            target_description: 目标元素描述
        
        Returns:
            结果描述字符串。
        """
        try:
            logger.info(f"[Vision] ====== 开始视觉定位 ======")
            logger.info(f"[Vision] 输入提示词: {target_description}")
            screenshot = await self.client.screenshot()
            logger.info(f"[Vision] 截图完成: {screenshot.get('width', '?')}x{screenshot.get('height', '?')}")

            width = self.config.screenshot_max_width   # 1366
            height = self.config.screenshot_max_height  # 768

            vision_prompt = build_vision_grounding_prompt(target_description)
            logger.info(f"[Vision] 发送给模型的完整 prompt:\n{vision_prompt}")
            
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
            
            raw_output = response.choices[0].message.content or ""
            
            usage = getattr(response, 'usage', None)
            if usage:
                logger.info(f"[Vision] Token 使用: prompt={usage.prompt_tokens}, completion={usage.completion_tokens}, total={usage.total_tokens}")
            
            logger.info(f"[Vision] 视觉大模型原始输出:\n{raw_output}")
            
            # ====== 解析 JSON 输出 ======
            # 返回值: (x, y, desc_text) 
            #   - found=true + 解析到坐标: (pixel_x, pixel_y, None)
            #   - found=false/JSON 格式解析失败: (None, None, desc_or_raw)
            pixel_x, pixel_y, desc_or_raw = self._parse_vision_json_output(raw_output)
            
            if pixel_x is not None and pixel_y is not None:
                # 情况 1: 精确定位到单个元素
                logger.info(f"[Vision] 精确定位: pixel_x={pixel_x}, pixel_y={pixel_y}")
                normalized_x, normalized_y = self._pixel_to_normalized(pixel_x, pixel_y)
                result = f"目标已定位: 归一化坐标 ({normalized_x}, {normalized_y})"
                logger.info(f"[Vision] 像素坐标 ({pixel_x}, {pixel_y}) -> 归一化坐标 ({normalized_x}, {normalized_y})")
            elif desc_or_raw:
                # 情况 2 + 3: 模型返回了 desc（候选列举）或 JSON 解析失败（原始文本）
                # 不管是 desc 还是 raw_output，都原样传递给 LLM，
                # 附加坐标转换公式方便 LLM 自行计算
                logger.info(f"[Vision] 获取到文本描述，传递回 LLM")
                result = (
                    f"视觉定位结果：{desc_or_raw}\n"
                    f"注意：以上坐标是像素坐标，如需使用请转换为归一化坐标："
                    f"x = x/{width}*1000，y=y/{height}*1000"
                )
            else:
                logger.warning(f"[Vision] 视觉定位无任何输出")
                result = raw_output
            
            logger.info(f"[Vision] 最终返回结果: {result}")
            logger.info(f"[Vision] ====== 视觉定位结束 ======")
            
            return result
            
        except Exception as e:
            logger.error(f"[Vision] 调用失败: {type(e).__name__}: {e}")
            import traceback
            logger.debug(f"[Vision] 异常堆栈:\n{traceback.format_exc()}")
            return None
    
    def _parse_vision_json_output(self, text: str) -> tuple:
        """解析 UI-TARS 返回的 JSON 格式输出
        
        三种返回值：
        1. found=true + x/y → (pixel_x, pixel_y, None)        # 精确定位
        2. found=false + desc → (None, None, desc_text)       # 候选列举
        3. JSON 格式解析失败 → (None, None, raw_output)       # 原始文本
        
        Args:
            text: 模型输出的原始文本
        
        Returns:
            (pixel_x or None, pixel_y or None, desc_or_raw or None)
        """
        text = text.strip()
        
        # 1. 移除 markdown 代码块包裹
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            text = json_match.group(1).strip()
        
        # 2. 尝试解析 JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # JSON 解析失败，尝试修复
            data = self._repair_vision_json(text)
            if data is None:
                # 解析失败 → 返回原始文本，LLM 自行提取
                return None, None, text
        
        # 3. 检查 found 字段
        found = data.get("found", False)
        
        if not found:
            # found=false: 返回 desc 文本（模型列举了多个候选）
            desc = data.get("desc", "")
            return None, None, desc
        
        # 4. found=true: 提取 x/y 坐标
        raw_x = data.get("x")
        raw_y = data.get("y")
        
        if raw_x is None or raw_y is None:
            desc = data.get("desc", "")
            return None, None, desc if desc else text
        
        # 处理 x 可能是字符串且包含逗号的情况（如 "561,98" -> x=561, y=98）
        if isinstance(raw_x, str) and "," in raw_x:
            parts = raw_x.split(",")
            try:
                pixel_x = int(parts[0].strip())
                pixel_y = int(parts[1].strip()) if len(parts) > 1 else int(raw_y)
                return pixel_x, pixel_y, None
            except (ValueError, IndexError):
                pass
        
        # 处理 x/y 可能是 float（如 636.0）
        try:
            pixel_x = int(float(raw_x))
            pixel_y = int(float(raw_y))
            return pixel_x, pixel_y, None
        except (ValueError, TypeError):
            desc = data.get("desc", "")
            return None, None, desc if desc else text
    
    def _repair_vision_json(self, text: str) -> Optional[dict]:
        """尝试修复 UI-TARS 返回的破损 JSON
        
        修复场景：
        - "x": 665,,  ->  "x": 665
        - "x": 665,   ->  "x": 665  (尾随逗号)
        - 部分字段缺失
        
        Args:
            text: 需要修复的 JSON 文本
        
        Returns:
            修复后的字典，修复失败返回 None
        """
        # 1. 修复重复逗号:  665,,  ->  665
        text = re.sub(r',\s*,', ',', text)
        
        # 2. 修复对象内尾随逗号:  "x": 665, }  ->  "x": 665 }
        text = re.sub(r',\s*}', '}', text)
        
        # 3. 再次尝试解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    
    def _normalize_point_format(self, text: str) -> str:
        """标准化坐标格式
        
        将视觉模型返回的多种坐标格式统一转换为 <point>x y</point> 格式
        支持的输入格式：
        - <point x1="157" y1="44"> -> <point>157 44</point>
        - <point x1="157" y1="44" alt="..."> -> <point>157 44</point>
        - <points x1='X,Y' alt='...'> -> <point>X Y</point>      (UI-TARS 特有)
        - <point>x1='X,Y'</point> -> <point>X Y</point>          (UI-TARS 特有)
        - <point>x1(X,Y)</point> -> <point>X Y</point>           (UI-TARS 特有)
        - <point>(X,Y)</point> -> <point>X Y</point>             (UI-TARS 特有)
        - (X,Y) -> <point>X Y</point>                            (UI-TARS 特有，裸括号)
        - <point>157 44</point> -> 保持不变
        
        Args:
            text: 包含坐标的文本
        
        Returns:
            标准化后的文本
        """
        changed = False
        
        # 1. 匹配 <point x1="X" y1="Y"> 格式（HTML 属性格式）
        pattern1 = r'<point\s+x1="(\d+)"\s+y1="(\d+)"[^>]*>'
        def replace_point1(match):
            nonlocal changed
            changed = True
            return f'<point>{match.group(1)} {match.group(2)}</point>'
        text = re.sub(pattern1, replace_point1, text)
        
        # 2. 匹配 <points x1='X,Y' alt='...'> 或 <points x1="X,Y" alt="..."> 格式（UI-TARS 特有，x1 逗号分隔，支持单引号/双引号）
        pattern2 = r"<points\s+x1=['\"](\d+),(\d+)['\"][^>]*>"
        def replace_points(match):
            nonlocal changed
            changed = True
            return f'<point>{match.group(1)} {match.group(2)}</point>'
        text = re.sub(pattern2, replace_points, text)
        
        # 3. 匹配 <point>x1='X,Y'</point> 格式（UI-TARS 特有，坐标在标签文本中）
        pattern3 = r"<point>x1='(\d+),(\d+)'"
        def replace_point_text_quote(match):
            nonlocal changed
            changed = True
            return f'<point>{match.group(1)} {match.group(2)}'
        text = re.sub(pattern3, replace_point_text_quote, text)
        
        # 4. 匹配 <point>x1(X,Y)</point> 格式（UI-TARS 特有，括号格式）
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
        # 只匹配行首或空白符后面的括号坐标
        if not changed:
            pattern6 = r'(?:^|\s)\((\d+),(\d+)\)(?:\s|$)'
            def replace_bare_bracket(match):
                nonlocal changed
                changed = True
                return f' <point>{match.group(1)} {match.group(2)}</point> '
            text = re.sub(pattern6, replace_bare_bracket, text)
        
        # 如果有变化，记录日志
        if changed:
            logger.info(f"[Vision] 坐标格式已标准化")
        
        return text
    
    def _parse_pixel_coordinates(self, text: str) -> tuple:
        """从文本中解析像素坐标
        
        从 UI-TARS 返回的文本中提取 <point>x y</point> 格式的像素坐标
        
        Args:
            text: 包含坐标的文本
        
        Returns:
            (pixel_x, pixel_y) 或 (None, None) 如果未找到坐标
        """
        # 匹配 <point>x y</point> 或 <point X Y...> 格式
        # 标准化后格式: <point>692 104</point> -> 尾随 < 来自 </point>
        # 未标准化格式: <point 692 104...</point> -> 尾随空格
        match = re.search(r'<point[>\s]+(\d+)\s+(\d+)(?:[<\s/]|$)', text)
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
    
    def _get_verification_model_name(self) -> str:
        """获取验证模型名称（使用校准模型）"""
        if self.config.calibration_model:
            return self.config.calibration_model
        return self.config.general_model
    
    async def _get_accessibility_tree(self) -> dict:
        """获取无障碍树"""
        try:
            return await self.client.accessibility_tree(max_depth=10)
        except Exception as e:
            logger.warning(f"[Accessibility] 获取失败: {e}")
            return {}
    
    async def _get_global_info_struct(self) -> Optional[GlobalInfo]:
        """获取结构化的全局动态信息"""
        try:
            tree = await self.client.accessibility_tree(max_depth=10)
            return self._accessibility_parser.parse(tree, None, None)
        except Exception as e:
            logger.warning(f"[全局信息] 结构化数据获取失败: {e}")
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
            logger.warning(f"[全局信息] 获取失败: {e}")
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
            logger.warning(f"[全局信息] 生成失败: {e}")
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
        
        logger.debug(f"[Context] 裁剪到最近 {keep_pairs} 轮对话（{len(conversation_msgs)} 条消息）")
        
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
            logger.warning(f"[Accessibility] 获取深度{max_depth}树失败: {e}")
            return {}