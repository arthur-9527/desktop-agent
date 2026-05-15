"""可用动作列表 - 静态提示词"""


AVAILABLE_ACTIONS = """## 可用动作

你可以输出 JSON 格式的动作。action 字段支持以下类型：

### 鼠标动作
| 动作 | 格式 | 说明 |
|------|------|------|
| click | `click(point='<point>x y</point>')` | 左键点击指定坐标 |
| left_double | `left_double(point='<point>x y</point>')` | 双击指定坐标 |
| right_single | `right_single(point='<point>x y</point>')` | 右键点击指定坐标 |
| move | `move(point='<point>x y</point>')` | 移动鼠标到指定位置 |
| drag | `drag(start_point='<point>x1 y1</point>', end_point='<point>x2 y2</point>')` | 拖拽操作 |
| scroll | `scroll(point='<point>x y</point>', direction='down/up/left/right')` | 滚动（需先移动鼠标） |

### 键盘动作
| 动作 | 格式 | 说明 |
|------|------|------|
| hotkey | `hotkey(key='ctrl c')` | 快捷键，按键用空格分隔 |
| type | `type(content='xxx', mode='replace')` | 输入文本，mode: replace(替换)/append(追加) |
| check_input | `check_input()` | 检查当前焦点输入框的内容 |

### 系统动作
| 动作 | 格式 | 说明 |
|------|------|------|
| wait | `wait()` | 等待 5 秒 |
| finished | `finished(content='原因')` | 任务完成 |
| failed | `failed(content='原因')` | 任务失败 |

## 动作示例

从状态表获取坐标 → 直接操作：
```json
{{
  "thought": "桌面有浏览器图标，直接双击打开",
  "plan_status": {{
    "steps": ["双击浏览器图标", "等待浏览器启动", "验证浏览器窗口"],
    "current": 0,
    "completed": []
  }},
  "use_vision_prompt": null,
  "action": "left_double(point='<point>500 300</point>')",
  "verification": {{
    "method": "accessibility",
    "prompt": "验证浏览器窗口是否已打开"
  }}
}}
```

需要视觉定位：
```json
{{
  "thought": "在设置窗口中找不到保存按钮，需要视觉定位",
  "plan_status": {{
    "steps": ["找到保存按钮", "点击保存", "等待保存完成"],
    "current": 0,
    "completed": []
  }},
  "use_vision_prompt": "绿色的保存按钮，位于设置窗口底部，在取消按钮左侧",
  "action": "click",
  "verification": {{
    "method": "visual",
    "prompt": "验证保存成功的提示是否出现"
  }}
}}
```
"""


__all__ = ["AVAILABLE_ACTIONS"]