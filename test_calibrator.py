#!/usr/bin/env python3
"""测试 kimi-k2.5 作为 Calibrator 的脚本"""

import asyncio
import json
import sys
from openai import AsyncOpenAI

# Calibrator 提示词模板
CALIBRATOR_PROMPT = """你是一个任务执行校准器。你的职责是审视执行历史，判断任务是否偏离目标，并提供调整建议。

## 原始任务
{task}

## 执行历史摘要
{history_summary}

## 当前全局状态
{global_info}

## 当前执行计划
{execution_plan}

## 请回答以下问题

1. **进度判断**: 当前进度如何？完成了多少？
2. **偏离检测**: 执行是否偏离了原始任务目标？
3. **建议调整**: 如果偏离，应该如何调整？

## 输出格式

请以简洁的中文回答，不超过 200 字。格式如下：

```
进度: [进度描述]
偏离: [是/否，原因]
更新计划: [是/否]
新计划: [如果需要更新，给出新计划步骤，否则留空]
建议: [调整建议]
```
"""

# 测试用例配置
TEST_CASES = [
    {
        "name": "测试1: 正常进度",
        "task": "在桌面上打开浏览器并搜索'python'",
        "history_summary": "- 步骤1: 双击浏览器图标\n- 步骤2: 浏览器启动成功\n- 步骤3: 在搜索框输入'python'\n- 步骤4: 点击搜索按钮",
        "global_info": "当前窗口: 浏览器\n活动标签: Google搜索\n搜索框: 已聚焦\n输入状态: English",
        "execution_plan": "### 当前执行计划\n\n▶ 步骤1: 打开浏览器\n✓ 步骤2: 搜索python\n→ 步骤3: 点击第一个搜索结果\n→ 步骤4: 验证搜索结果"
    },
    {
        "name": "测试2: 执行偏离",
        "task": "在桌面上创建一个新的文本文件并重命名为'报告.txt'",
        "history_summary": "- 步骤1: 右键点击桌面\n- 步骤2: 选择'新建'->'文本文档'\n- 步骤3: 尝试重命名文件\n- 步骤4: 错误地删除了文件",
        "global_info": "当前窗口: 桌面\n文件数量: 0\n桌面状态: 空",
        "execution_plan": "### 当前执行计划\n\n✓ 步骤1: 右键点击桌面\n✓ 步骤2: 选择新建文本文档\n▶ 步骤3: 重命名文件\n→ 步骤4: 验证文件名称"
    },
    {
        "name": "测试3: 任务完成",
        "task": "在桌面上打开记事本并输入'Hello World'",
        "history_summary": "- 步骤1: 双击记事本图标\n- 步骤2: 记事本打开成功\n- 步骤3: 在记事本中输入'Hello World'\n- 步骤4: 保存文件",
        "global_info": "当前窗口: 记事本\n活动状态: 已聚焦\n输入状态: English\n文件状态: 已保存",
        "execution_plan": "### 当前执行计划\n\n✓ 步骤1: 打开记事本\n✓ 步骤2: 输入文字\n✓ 步骤3: 保存文件\n计划状态: 已完成"
    }
]

async def test_calibrator(test_case: dict) -> dict:
    """测试单个用例"""
    print(f"\n{'='*60}")
    print(f"测试: {test_case['name']}")
    print(f"{'='*60}")
    
    # 构建 prompt
    prompt = CALIBRATOR_PROMPT.format(
        task=test_case["task"],
        history_summary=test_case["history_summary"],
        global_info=test_case["global_info"],
        execution_plan=test_case["execution_plan"]
    )
    
    # 创建 OpenAI 客户端
    client = AsyncOpenAI(
        base_url="http://121.41.171.73:4000/v1",
        api_key="sk-dummy"
    )
    
    # 调用 API
    try:
        response = await client.chat.completions.create(
            model="kimi-k2.5",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.3,
        )
        
        result = response.choices[0].message.content or ""
        print(f"\n【模型回复】:")
        print(result)
        
        # 验证格式
        issues = validate_format(result)
        
        return {
            "success": len(issues) == 0,
            "result": result,
            "issues": issues,
            "usage": response.usage
        }
        
    except Exception as e:
        print(f"\n【错误】: {e}")
        return {
            "success": False,
            "result": None,
            "issues": [f"API调用失败: {e}"],
            "usage": None
        }

def validate_format(result: str) -> list:
    """验证输出格式"""
    issues = []
    
    if result is None:
        return ["输出为空"]
    
    # 检查必需字段
    required_fields = ["进度:", "偏离:", "更新计划:", "新计划:", "建议:"]
    for field in required_fields:
        if field not in result:
            issues.append(f"缺少字段: {field}")
    
    # 检查偏离字段格式
    if "偏离:" in result:
        deviation = result.split("偏离:")[1].split("\n")[0].strip()
        if "是" not in deviation and "否" not in deviation:
            issues.append(f"偏离字段格式错误: '{deviation}'，应包含'是'或'否'")
    
    # 检查更新计划字段格式
    if "更新计划:" in result:
        update = result.split("更新计划:")[1].split("\n")[0].strip()
        if "是" not in update and "否" not in update:
            issues.append(f"更新计划字段格式错误: '{update}'，应包含'是'或'否'")
    
    return issues

async def main():
    """主函数"""
    print("=" * 60)
    print("kimi-k2.5 作为 Calibrator 测试")
    print("=" * 60)
    print(f"\n配置:")
    print(f"  Model: kimi-k2.5")
    print(f"  URL: http://121.41.171.73:4000/v1")
    print(f"  API Key: sk-dummy")
    print(f"\n测试用例数: {len(TEST_CASES)}")
    
    results = []
    for test_case in TEST_CASES:
        result = await test_calibrator(test_case)
        results.append(result)
    
    # 汇总结果
    print(f"\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    
    for i, result in enumerate(results, 1):
        status = "✓ 通过" if result["success"] else "✗ 失败"
        print(f"\n测试{i}: {status}")
        if result["issues"]:
            print(f"  问题:")
            for issue in result["issues"]:
                print(f"    - {issue}")
        if result["usage"]:
            print(f"  消耗: {result['usage'].prompt_tokens} tokens (输入), {result['usage'].completion_tokens} tokens (输出)")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 kimi-k2.5 可以用作 Calibrator！")
    else:
        print("\n⚠️  kimi-k2.5 部分测试未通过，需要检查格式兼容性。")

if __name__ == "__main__":
    asyncio.run(main())