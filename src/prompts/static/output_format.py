"""输出格式定义 - 静态提示词"""


OUTPUT_FORMAT = """## 输出格式

每一步输出一个 JSON 对象，格式如下：

```json
{{
  "thought": "分析当前状态...",
  "plan_status": {{
    "steps": ["步骤1", "步骤2", "步骤3"],
    "current": 1,
    "completed": [0]
  }},
  "use_vision_prompt": null,
  "action": "click(point='<point>500 300</point>')",
  "verification": {{
    "method": "accessibility",
    "prompt": "验证浏览器窗口是否已打开"
  }}
}}
```

## 字段说明

### thought
- **类型**: string
- **说明**: 分析当前状态，说明当前进度、目标和下一步计划
- **要求**: 用中文回答

### plan_status
- **类型**: object
- **说明**: 执行计划状态
- **字段**:
  - `steps`: 当前执行计划的所有步骤列表
  - `current`: 当前正在执行的步骤索引（从 0 开始）
  - `completed`: 已完成的步骤索引列表

### use_vision_prompt
- **类型**: string | null
- **说明**: 是否需要视觉定位
- **取值**:
  - `null`: 不需要视觉定位，直接从全局信息表获取坐标执行 action
  - `string`: 需要视觉定位，描述你要找的目标元素
- **描述要求**（当不为 null 时）:
  1. **空间位置**: 目标元素所在位置（哪个窗口/对话框、屏幕区域）
  2. **视觉特征**: 目标元素的外观（颜色、形状、文字标签）
  3. **周围关系**: 与其他元素的关系（在 X 左侧、在 Y 上方）

### action
- **类型**: string
- **说明**: 要执行的动作
- **格式**: 动作名称 + 括号内参数，如 `click(point='<point>500 300</point>')`
- **注意**: 当 `use_vision_prompt` 不为 null 时，action 只需指定动作类型（如 "click"），坐标由视觉模型返回

### verification
- **类型**: object
- **说明**: 操作验证配置
- **字段**:
  - `method`: 验证方式，可选值 `accessibility` | `visual` | `mixed`
  - `prompt`: 验证标准描述（visual/mixed 时必填，accessibility 时建议填写）

## 示例输出

### 示例1：直接执行（无障碍树验证）
```json
{{
  "thought": "当前有浏览器窗口，需要点击地址栏输入网址",
  "plan_status": {{
    "steps": ["点击地址栏", "输入网址", "按回车"],
    "current": 0,
    "completed": []
  }},
  "use_vision_prompt": null,
  "action": "click(point='<point>400 100</point>')",
  "verification": {{
    "method": "accessibility",
    "prompt": "地址栏是否获得焦点"
  }}
}}
```

### 示例2：需要视觉定位
```json
{{
  "thought": "设置窗口中找不到保存按钮，需要视觉定位",
  "plan_status": {{
    "steps": ["找到保存按钮", "点击保存", "等待完成"],
    "current": 0,
    "completed": []
  }},
  "use_vision_prompt": "设置窗口底部的蓝色保存按钮，位于取消按钮左侧",
  "action": "click",
  "verification": {{
    "method": "visual",
    "prompt": "验证保存成功的提示是否出现"
  }}
}}
```

### 示例3：使用快捷键（无障碍树验证）
```json
{{
  "thought": "需要打开文件对话框",
  "plan_status": {{
    "steps": ["打开文件对话框", "选择文件", "打开"],
    "current": 0,
    "completed": []
  }},
  "use_vision_prompt": null,
  "action": "hotkey(key='ctrl o')",
  "verification": {{
    "method": "accessibility",
    "prompt": "文件打开对话框是否出现"
  }}
}}
```

### 示例4：任务完成
```json
{{
  "thought": "任务已完成，浏览器已成功打开并加载目标网页",
  "plan_status": {{
    "steps": ["双击浏览器图标", "等待启动", "验证窗口"],
    "current": 3,
    "completed": [0, 1, 2]
  }},
  "use_vision_prompt": null,
  "action": "finished(content='浏览器已打开并成功加载网页')",
  "verification": {{
    "method": "accessibility",
    "prompt": ""
  }}
}}
```
"""


__all__ = ["OUTPUT_FORMAT"]