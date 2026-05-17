"""可用动作列表 - 静态提示词"""


AVAILABLE_ACTIONS = """## 可用动作

### 鼠标动作
| 动作 | 格式 | 说明 |
|------|------|------|
| click | `click(point='<point>x y</point>')` | 左键点击 |
| left_double | `left_double(point='<point>x y</point>')` | 双击 |
| right_single | `right_single(point='<point>x y</point>')` | 右键点击 |
| move | `move(point='<point>x y</point>')` | 移动鼠标 |
| drag | `drag(start_point='<point>x1 y1</point>', end_point='<point>x2 y2</point>')` | 拖拽 |
| scroll | `scroll(point='<point>x y</point>', direction='down/up/left/right')` | 滚动 |

### 键盘动作
| 动作 | 格式 | 说明 |
|------|------|------|
| hotkey | `hotkey(key='ctrl c')` | 快捷键，按键用空格分隔 |
| type | `type(content='xxx', mode='replace', press_enter=false)` | 输入文本，mode: replace/append，press_enter: 输入完成后是否按回车 |
| check_input | `check_input()` | 检查当前焦点输入框内容 |

### 系统动作
| 动作 | 格式 | 说明 |
|------|------|------|
| wait | `wait()` | 等待 5 秒，可以用于获取更多当前界面信息 |
| finished | `finished(content='原因')` | 任务完成 |
| failed | `failed(content='原因')` | 任务失败 |

## 动作示例

直接操作（坐标来自全局信息表）：
```json
{{
  "thought": "双击桌面浏览器图标",
  "plan_status": {{"steps": ["双击浏览器", "等待启动", "验证窗口"], "current": 0, "completed": []}},
  "use_vision_prompt": null,
  "action": "left_double(point='<point>500 300</point>')",
  "verification": {{"method": "accessibility", "prompt": "浏览器窗口是否已打开"}}
}}
```

视觉定位（全局信息表找不到时）：
```json
{{
  "thought": "需要视觉定位保存按钮",
  "plan_status": {{"steps": ["找到保存按钮", "点击保存", "等待完成"], "current": 0, "completed": []}},
  "use_vision_prompt": "设置窗口底部的绿色保存按钮，在取消按钮左侧",
  "action": "click",
  "verification": {{"method": "visual", "prompt": "保存成功提示是否出现"}}
}}
```
"""


__all__ = ["AVAILABLE_ACTIONS"]