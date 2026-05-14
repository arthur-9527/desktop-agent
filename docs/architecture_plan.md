# DeskAgent 架构改造计划

## 核心能力层

| 层 | 说明 | 实现 |
|----|------|------|
| 无障碍树引擎 | 维护全局动态状态表 | `accessibility_parser.py` |
| 原子操作接口 | 通过 HTTP API 控制远程设备 | `agentdesk_client.py` |
| 视觉定位 | UI-TARS 多模态模型，按需获取坐标/桌面信息 | 按需调用 |
| 平台快捷键映射 | win/cmd/meta 自动转换 | `action_executor.py` KeyMapper |

---

## 三模型架构

| 角色 | 模型类型 | 用途 | 调用频率 |
|------|---------|------|---------|
| **Planner** | 通用 LLM (推理能力强) | 主循环决策：状态表+历史 → 规划下一步动作 | 每轮 |
| **Grounding (UI-TARS)** | 视觉定位专用模型 | Planner 从状态表找不到目标时，通过截图定位/分析 | 按需 |
| **Calibrator** | 通用 LLM (可与 Planner 同模型，独立实例) | 每 N 步独立审视执行历史，校准方向，打破循环 | 每 N 步 |

配置结构：

```
[Planner]      llm_base_url / llm_api_key / general_model
[Grounding]    vision_base_url / vision_api_key / vision_model
[Calibrator]   calibration_base_url / calibration_api_key / calibration_model
               (未配置时默认复用 Planner 配置)
```

---

## 主循环流程

```
Step 0: 初始化
  └─ 获取完整无障碍树 → 保存 raw_tree_before
     → 生成全局状态表 → 给 Planner 看

Step 1: Planner 决策
  └─ Input: system_prompt(含操作空间) + 全局状态表 + 执行历史 + 用户任务
  └─ Output: JSON 动作

Step 2: 判断动作类型
  ├─ use_vision_prompt = null → Step 3 执行操作
  └─ use_vision_prompt ≠ null → Step 2a 视觉定位
       └─ 截图 → UI-TARS(prompt) → 获取相关信息 + 总结描述当前截图中的详细信息
       └─ UI-TARS 结果注入上下文 (不执行任何操作)
       └─ 回到 Step 1 (Planner 基于新信息重新决策)

Step 3: 执行操作
  └─ action 为 finished/fail → 结束
  └─ 其他 → HTTP 原子操作

Step 4: 验证 (树对比)
  └─ 重新获取完整无障碍树 → raw_tree_after
  └─ diff_trees(raw_tree_before, raw_tree_after) → 纯代码比较
     ├─ 成功 → 记录 "[操作成功] ..." → 写入执行历史
     └─ 失败 → 截图 → UI-TARS 视觉分析
              ├─ 视觉确认成功 → 记录 → 写入执行历史
              └─ 视觉确认失败 → 记录 "[操作失败] 原因+桌面状态" → 写入执行历史

Step 5: 校准检查 (可选)
  └─ 当前步数 % calibration_interval == 0
     → Calibration LLM 独立审视执行历史摘要 + 当前任务
     → 输出校准分析 → 注入上下文

Step 6: 循环
  └─ raw_tree_after → raw_tree_before (更新基准)
  └─ 回到 Step 1，直到 Planner 输出 finished/fail
```

关键设计：
- **UI-TARS 是纯信息获取工具**，不执行任何操作。获取到的坐标/信息推入上下文后，由 Planner 重新决策。
- **Planner 始终是唯一决策者**，UI-TARS 只是它的"眼睛"。

---

## Planner 输出格式

统一 JSON 格式，一行一个动作：

```json
// 从状态表获取坐标 → 直接操作
{"use_vision_prompt": null, "action": "click(point='<point>500 300</point>')"}

// 需要先通过 UI-TARS 获取坐标 → 回到 Planner 重新决策
{"use_vision_prompt": "右下角确认对话框中蓝色确定按钮，位于取消按钮左侧", "action": "click"}

// 快捷键
{"use_vision_prompt": null, "action": "hotkey(key='ctrl c')"}

// 输入文本
{"use_vision_prompt": null, "action": "type(content='hello')"}

// 等待
{"use_vision_prompt": null, "action": "wait()"}

// 滚动
{"use_vision_prompt": null, "action": "scroll(point='<point>500 400</point>', direction='down')"}

// 任务完成
{"use_vision_prompt": null, "action": "finished(content='文件已保存')"}

// 任务失败
{"use_vision_prompt": null, "action": "failed(content='未找到目标应用')"}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `use_vision_prompt` | string\|null | null=直接执行action；有内容=先调UI-TARS获取信息再回Planner |
| `action` | string | 复用现有 UI-TARS 动作格式，可直接被 `ActionExecutor.parse()` 解析 |

### use_vision_prompt 编写原则

Planner 生成时应包含：
1. 目标元素的**空间位置**（哪个窗口/对话框内，屏幕区域）
2. 目标元素的**视觉特征**（颜色、形状、文字标签）
3. 与**周围元素的关系**（在 X 左侧、在 Y 上方）

---

## 操作空间 (Planner System Prompt 结构)

```
## 全局状态表
{{动态注入，每步更新}}

## 可用动作
你可以输出 JSON 格式的动作。action 字段支持以下类型：

click(point='<point>x y</point>')         # 左键点击指定坐标
left_double(point='<point>x y</point>')   # 双击
right_single(point='<point>x y</point>')  # 右键点击
move(point='<point>x y</point>')          # 移动鼠标
drag(start_point='<point>x1 y1</point>', end_point='<point>x2 y2</point>')  # 拖拽
scroll(point='<point>x y</point>', direction='down/up/left/right')  # 滚动
hotkey(key='ctrl c')                      # 快捷键
type(content='xxx')                       # 输入文本
wait()                                    # 等待 5s
finished(content='原因')                   # 任务完成
failed(content='原因')                     # 任务失败

当你从全局状态表中找不到目标元素坐标时，设置 use_vision_prompt 请求视觉定位。
use_vision_prompt 不为 null 时，操作不会立即执行，UI-TARS 会返回坐标信息供你下次决策。

## 执行规则
1. 优先从全局状态表查找坐标
2. 每一步只输出一个 JSON，不要输出额外文字
3. 动作执行后系统返回验证结果，根据结果决定下一步
4. 确认任务完成后输出 finished
```

---

## 树对比验证 (diff_trees)

对比两份原始无障碍树数据，纯代码执行，无额外 LLM 调用。

检查维度：

- **窗口变化**: 新窗口出现 / 窗口关闭
- **焦点变化**: 焦点元素是否迁移到预期目标
- **弹窗/对话框**: 是否有新的 Dialog/Alert 角色出现
- **元素属性**: 目标元素的 name / role 是否改变
- **桌面结构**: 窗口数量、任务栏状态

放在 `accessibility_parser.py` 中：`diff_trees(before: dict, after: dict) -> DiffResult`

---

## 周期性校准 (Calibration)

参数：`calibration_interval: int = 5` (0 表示关闭)

触发条件：当前步数 > 1 且 步数 % calibration_interval == 0

Calibration LLM 输入：
- 用户原始任务
- 执行历史摘要（最近 N 步的成功/失败记录）
- 当前全局状态表

Calibration LLM 输出：
- 当前进度判断
- 是否偏离目标
- 建议调整方向

输出注入到 Planner 的下一步上下文中。

---

## 上下文管理

每步执行历史记录格式：

```
Step 1: action=click(point='<point>500 300</point>') → [成功] 窗口 'Visual Studio Code' 已打开
Step 2: action=click → [视觉定位] UI-TARS 找到确定按钮坐标 (600, 400)
Step 3: action=click(point='<point>600 400</point>') → [失败] 无 UI 变化, 桌面状态: 3窗口均未变化
Step 4: action=click(point='<point>600 400</point>') → [成功] 确认对话框已关闭
```

滑动窗口：保留最近 `context_window_size` 步的完整上下文，旧记录保留摘要。

---

## Metrics 记录系统

新增 `src/metrics.py` 模块，用于记录任务执行的各项指标。

### 数据结构

```python
@dataclass
class StepMetric:
    """单步指标"""
    step: int
    action: str
    action_type: str
    use_vision: bool  # 是否调用了视觉模型
    
    # 耗时统计 (毫秒)
    planning_time_ms: int = 0       # Planner 耗时
    vision_time_ms: int = 0         # 视觉模型耗时
    execution_time_ms: int = 0      # 动作执行耗时
    verification_time_ms: int = 0   # 树对比验证耗时
    
    # 结果
    success: bool = False
    tree_changed: bool = False
    error: Optional[str] = None

@dataclass
class RunMetrics:
    """单次任务运行指标"""
    task: str
    start_time: datetime
    end_time: Optional[datetime]
    
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
    
    steps: List[StepMetric]
```

### 输出示例

```json
{
  "task": "打开浏览器并搜索天气",
  "success": true,
  "total_steps": 8,
  "success_rate": "7/8",
  "total_time_s": 45.2,
  "model_calls": {
    "planner": 8,
    "vision": 2,
    "calibrator": 1
  },
  "avg_step_time_ms": 5650
}
```

### 集成方式

在 `agent_loop.py` 中：
1. 任务开始时创建 `RunMetrics` 实例
2. 每步执行时创建 `StepMetric`，记录各阶段耗时
3. 任务结束时调用 `finalize()` 并输出报告

---

## 测试用例

### use_vision_prompt 格式测试

新增 `test_vision_prompt.py`，测试 JSON 格式解析：

```python
class TestVisionPromptParsing:
    """测试 JSON 格式解析"""
    
    def test_direct_action_without_vision(self):
        """测试直接执行的动作（无需视觉定位）"""
        raw = '{"use_vision_prompt": null, "action": "click(point=\'<point>500 300</point>\')"}'
        parsed = json.loads(raw)
        assert parsed["use_vision_prompt"] is None
        assert "click" in parsed["action"]
    
    def test_vision_required_action(self):
        """测试需要视觉定位的动作"""
        raw = '{"use_vision_prompt": "右下角确认对话框中蓝色确定按钮", "action": "click"}'
        parsed = json.loads(raw)
        assert parsed["use_vision_prompt"] is not None
```

### use_vision_prompt 质量测试

测试 prompt 是否包含必要的定位信息：

```python
class TestVisionPromptQuality:
    """测试 use_vision_prompt 编写质量"""
    
    def test_prompt_completeness(self):
        """测试 prompt 是否包含空间位置、视觉特征、周围关系"""
        prompt = "屏幕中央的保存对话框中，蓝色'保存'按钮，位于'取消'按钮右侧"
        
        has_location = any(kw in prompt for kw in ["左", "右", "中央", "窗口"])
        has_visual = any(kw in prompt for kw in ["颜色", "蓝色", "按钮"])
        has_relation = any(kw in prompt for kw in ["位于", "旁边", "左侧"])
        
        quality_score = sum([has_location, has_visual, has_relation])
        assert quality_score >= 2, "prompt 质量不足"
```

### 场景测试

新增 `test_scenarios.py`，模拟真实任务流程：

```python
SCENARIOS = [
    {
        "name": "保存文件",
        "steps": [
            {"use_vision_prompt": null, "action": "hotkey(key='ctrl s')"},
            {"use_vision_prompt": "保存对话框中的文件名输入框", "action": "click"},
            {"use_vision_prompt": null, "action": "type(content='report.pdf')"},
            {"use_vision_prompt": "保存按钮，通常在对话框底部右侧", "action": "click"},
            {"use_vision_prompt": null, "action": "finished(content='文件已保存')"},
        ]
    },
    {
        "name": "打开浏览器",
        "steps": [
            {"use_vision_prompt": null, "action": "hotkey(key='win')"},
            {"use_vision_prompt": "开始菜单中的浏览器图标", "action": "click"},
            {"use_vision_prompt": null, "action": "finished(content='浏览器已打开')"},
        ]
    }
]
```

---

## 改动文件清单

| 文件 | 改动 |
|------|------|
| `src/prompts.py` | 重构：Planner system prompt（操作空间 + 全局状态表占位 + 规则） |
| `src/agent_loop.py` | 核心重构：三模型调用 + use_vision_prompt 分流 + 树对比验证 + 周期性校准 + Metrics 集成 |
| `src/accessibility_parser.py` | 新增 `diff_trees(before, after)` 树对比函数 |
| `src/action_executor.py` | 动作解析适配 JSON 外层包装，action 字段复用现有格式 |
| `src/config.py` | 新增 Calibrator 模型配置（可选，默认复用 Planner） |
| `src/metrics.py` | **新增**：Metrics 记录模块，包含 `StepMetric` 和 `RunMetrics` 数据结构 |
| `test_vision_prompt.py` | **新增**：use_vision_prompt 格式解析测试、质量测试 |
| `test_scenarios.py` | **新增**：场景测试，模拟真实任务流程 |

---

## 实施顺序

建议按以下顺序实施：

1. **Phase 1**: 配置层改造 (`config.py`) - 新增 Calibrator 模型配置
2. **Phase 2**: 树对比功能 (`accessibility_parser.py`) - 实现 `diff_trees()`
3. **Phase 3**: Metrics 模块 (`metrics.py`) - 新增指标记录功能
4. **Phase 4**: Prompt 重构 (`prompts.py`) - 新的操作空间 + 状态表占位
5. **Phase 5**: 核心循环重构 (`agent_loop.py`) - 三模型调用 + 分流逻辑 + Metrics 集成
6. **Phase 6**: 动作解析适配 (`action_executor.py`) - JSON 外层包装
7. **Phase 7**: 测试用例 (`test_vision_prompt.py`, `test_scenarios.py`) - 验证新功能
