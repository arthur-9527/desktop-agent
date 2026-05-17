"""输出格式定义 - 静态提示词"""


OUTPUT_FORMAT = """## 输出格式

每步输出一个 JSON：

```json
{{
  "thought": "中文分析当前状态和下一步动作",
  "use_vision_prompt": null,
  "action": "click(point='<point>x y</point>')",
  "verification": {{
    "method": "accessibility",
    "prompt": "验证标准描述"
  }}
}}
```

### 字段说明
- **thought** (string): 分析当前状态，中文
- **use_vision_prompt** (string|null): null=从全局信息表获取坐标; string=描述要找的目标(位置+外观+周围关系)，由视觉模型定位
- **action** (string): 动作指令。有 use_vision_prompt 时只需写动作类型如 "click"，坐标由视觉模型返回
- **verification** (object): `method` 可选 accessibility/visual/mixed; `prompt` 验证标准(具体明确)
"""


__all__ = ["OUTPUT_FORMAT"]