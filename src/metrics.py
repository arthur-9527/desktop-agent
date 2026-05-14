"""Metrics 记录模块 - 记录任务执行的各项指标"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import time


@dataclass
class StepMetric:
    """单步指标"""
    step: int
    action: str
    action_type: str
    use_vision: bool = False  # 是否调用了视觉模型
    
    # 耗时统计 (毫秒)
    planning_time_ms: int = 0       # Planner 耗时
    vision_time_ms: int = 0         # 视觉模型耗时
    execution_time_ms: int = 0      # 动作执行耗时
    verification_time_ms: int = 0   # 树对比验证耗时
    
    # 结果
    success: bool = False
    tree_changed: bool = False
    error: Optional[str] = None
    
    def total_time_ms(self) -> int:
        """计算总耗时"""
        return (
            self.planning_time_ms + 
            self.vision_time_ms + 
            self.execution_time_ms + 
            self.verification_time_ms
        )


@dataclass
class RunMetrics:
    """单次任务运行指标"""
    task: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # 汇总统计
    total_steps: int = 0
    success: bool = False
    
    # 模型调用统计
    planner_calls: int = 0
    vision_calls: int = 0
    calibrator_calls: int = 0
    
    # 耗时统计 (毫秒)
    total_time_ms: int = 0
    planner_time_ms: int = 0
    vision_time_ms: int = 0
    calibrator_time_ms: int = 0
    execution_time_ms: int = 0
    verification_time_ms: int = 0
    
    steps: List[StepMetric] = field(default_factory=list)
    
    def add_step(self, step: StepMetric):
        """添加步骤指标"""
        self.steps.append(step)
        self.total_steps = len(self.steps)
        
        # 更新统计
        self.planner_time_ms += step.planning_time_ms
        self.vision_time_ms += step.vision_time_ms
        self.execution_time_ms += step.execution_time_ms
        self.verification_time_ms += step.verification_time_ms
        
        if step.use_vision:
            self.vision_calls += 1
    
    def finalize(self, success: bool = False):
        """完成记录"""
        self.end_time = datetime.now()
        self.success = success
        
        if self.start_time and self.end_time:
            self.total_time_ms = int(
                (self.end_time - self.start_time).total_seconds() * 1000
            )
        
        self.planner_calls = len(self.steps)
    
    def success_rate(self) -> str:
        """计算成功率"""
        if not self.steps:
            return "0/0"
        success_count = sum(1 for s in self.steps if s.success)
        return f"{success_count}/{len(self.steps)}"
    
    def avg_step_time_ms(self) -> int:
        """计算平均步骤耗时"""
        if not self.steps:
            return 0
        return self.total_time_ms // len(self.steps)
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "task": self.task,
            "success": self.success,
            "total_steps": self.total_steps,
            "success_rate": self.success_rate(),
            "total_time_s": round(self.total_time_ms / 1000, 1),
            "model_calls": {
                "planner": self.planner_calls,
                "vision": self.vision_calls,
                "calibrator": self.calibrator_calls,
            },
            "avg_step_time_ms": self.avg_step_time_ms(),
        }
    
    def report(self) -> str:
        """生成文本报告"""
        lines = [
            "=" * 50,
            "任务执行报告",
            "=" * 50,
            f"任务: {self.task}",
            f"状态: {'成功 ✓' if self.success else '失败 ✗'}",
            f"总步骤: {self.total_steps}",
            f"成功率: {self.success_rate()}",
            f"总耗时: {round(self.total_time_ms / 1000, 1)}s",
            "",
            "模型调用:",
            f"  - Planner: {self.planner_calls} 次",
            f"  - Vision: {self.vision_calls} 次",
            f"  - Calibrator: {self.calibrator_calls} 次",
            "",
            "耗时分布:",
            f"  - Planner: {round(self.planner_time_ms / 1000, 1)}s",
            f"  - Vision: {round(self.vision_time_ms / 1000, 1)}s",
            f"  - Calibrator: {round(self.calibrator_time_ms / 1000, 1)}s",
            f"  - Execution: {round(self.execution_time_ms / 1000, 1)}s",
            f"  - Verification: {round(self.verification_time_ms / 1000, 1)}s",
            "",
        ]
        
        # 步骤详情
        if self.steps:
            lines.append("步骤详情:")
            for step in self.steps:
                status = "✓" if step.success else "✗"
                vision_tag = "[Vision]" if step.use_vision else ""
                lines.append(
                    f"  Step {step.step}: {step.action_type} {status} "
                    f"{step.total_time_ms()}ms {vision_tag}"
                )
                if step.error:
                    lines.append(f"    错误: {step.error}")
        
        lines.append("=" * 50)
        return "\n".join(lines)


class MetricsTimer:
    """计时器辅助类"""
    
    def __init__(self):
        self._start: Optional[float] = None
    
    def start(self):
        """开始计时"""
        self._start = time.time()
    
    def elapsed_ms(self) -> int:
        """获取已用时间（毫秒）"""
        if self._start is None:
            return 0
        return int((time.time() - self._start) * 1000)
    
    def stop(self) -> int:
        """停止计时并返回耗时（毫秒）"""
        elapsed = self.elapsed_ms()
        self._start = None
        return elapsed