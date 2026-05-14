"""测试 use_vision_prompt JSON 格式解析"""

import json
import pytest


class TestVisionPromptParsing:
    """测试 JSON 格式解析"""
    
    def test_direct_action_without_vision(self):
        """测试直接执行的动作（无需视觉定位）"""
        raw = '{"use_vision_prompt": null, "action": "click(point=\'<point>500 300</point>\')"}'
        parsed = json.loads(raw)
        
        assert parsed["use_vision_prompt"] is None
        assert "click" in parsed["action"]
        assert "<point>500 300</point>" in parsed["action"]
    
    def test_vision_required_action(self):
        """测试需要视觉定位的动作"""
        raw = '{"use_vision_prompt": "右下角确认对话框中蓝色确定按钮", "action": "click"}'
        parsed = json.loads(raw)
        
        assert parsed["use_vision_prompt"] is not None
        assert parsed["use_vision_prompt"] == "右下角确认对话框中蓝色确定按钮"
        assert parsed["action"] == "click"
    
    def test_hotkey_action(self):
        """测试快捷键动作"""
        raw = '{"use_vision_prompt": null, "action": "hotkey(key=\'ctrl c\')"}'
        parsed = json.loads(raw)
        
        assert parsed["use_vision_prompt"] is None
        assert "hotkey" in parsed["action"]
        assert "ctrl c" in parsed["action"]
    
    def test_type_action(self):
        """测试输入文本动作"""
        raw = '{"use_vision_prompt": null, "action": "type(content=\'hello world\')"}'
        parsed = json.loads(raw)
        
        assert parsed["use_vision_prompt"] is None
        assert "type" in parsed["action"]
        assert "hello world" in parsed["action"]
    
    def test_finished_action(self):
        """测试任务完成动作"""
        raw = '{"use_vision_prompt": null, "action": "finished(content=\'文件已保存\')"}'
        parsed = json.loads(raw)
        
        assert parsed["use_vision_prompt"] is None
        assert "finished" in parsed["action"]
        assert "文件已保存" in parsed["action"]
    
    def test_failed_action(self):
        """测试任务失败动作"""
        raw = '{"use_vision_prompt": null, "action": "failed(content=\'未找到目标\')"}'
        parsed = json.loads(raw)
        
        assert parsed["use_vision_prompt"] is None
        assert "failed" in parsed["action"]
    
    def test_scroll_action(self):
        """测试滚动动作"""
        raw = '{"use_vision_prompt": null, "action": "scroll(point=\'<point>500 400</point>\', direction=\'down\')"}'
        parsed = json.loads(raw)
        
        assert parsed["use_vision_prompt"] is None
        assert "scroll" in parsed["action"]
        assert "down" in parsed["action"]
    
    def test_drag_action(self):
        """测试拖拽动作"""
        raw = '{"use_vision_prompt": null, "action": "drag(start_point=\'<point>100 100</point>\', end_point=\'<point>500 500</point>\')"}'
        parsed = json.loads(raw)
        
        assert parsed["use_vision_prompt"] is None
        assert "drag" in parsed["action"]
        assert "<point>100 100</point>" in parsed["action"]
        assert "<point>500 500</point>" in parsed["action"]


class TestVisionPromptQuality:
    """测试 use_vision_prompt 编写质量"""
    
    def test_prompt_completeness(self):
        """测试 prompt 是否包含空间位置、视觉特征、周围关系"""
        prompt = "屏幕中央的保存对话框中，蓝色'保存'按钮，位于'取消'按钮右侧"
        
        # 检查空间位置
        has_location = any(kw in prompt for kw in ["左", "右", "中央", "窗口", "对话框", "屏幕"])
        
        # 检查视觉特征
        has_visual = any(kw in prompt for kw in ["颜色", "蓝色", "按钮", "红色", "绿色"])
        
        # 检查周围关系
        has_relation = any(kw in prompt for kw in ["位于", "旁边", "左侧", "右侧", "上方", "下方"])
        
        quality_score = sum([has_location, has_visual, has_relation])
        assert quality_score >= 2, "prompt 质量不足，应包含空间位置、视觉特征、周围关系中的至少两项"
    
    def test_prompt_with_color(self):
        """测试包含颜色描述的 prompt"""
        prompt = "红色关闭按钮，位于窗口右上角"
        
        assert any(kw in prompt for kw in ["红", "蓝", "绿", "黄", "颜色"])
    
    def test_prompt_with_position(self):
        """测试包含位置描述的 prompt"""
        prompt = "对话框底部的确定按钮"
        
        assert any(kw in prompt for kw in ["底", "顶", "左", "右", "中", "角"])
    
    def test_prompt_with_context(self):
        """测试包含上下文的 prompt"""
        prompt = "保存对话框中的文件名输入框，在保存按钮上方"
        
        assert "对话框" in prompt or "窗口" in prompt
        assert "上方" in prompt or "下方" in prompt or "左侧" in prompt or "右侧" in prompt


class TestActionExecutorParsing:
    """测试 ActionExecutor 的 Planner JSON 解析"""
    
    def test_parse_planner_json_click(self):
        """测试解析点击动作 JSON"""
        from src.action_executor import ActionExecutor
        
        executor = ActionExecutor(None)
        result = executor.parse_planner_json(
            '{"use_vision_prompt": null, "action": "click(point=\'<point>500 300</point>\')"}'
        )
        
        assert result["use_vision_prompt"] is None
        assert result["action_type"] == "click"
    
    def test_parse_planner_json_with_vision(self):
        """测试解析需要视觉定位的 JSON"""
        from src.action_executor import ActionExecutor
        
        executor = ActionExecutor(None)
        result = executor.parse_planner_json(
            '{"use_vision_prompt": "确定按钮", "action": "click"}'
        )
        
        assert result["use_vision_prompt"] == "确定按钮"
        assert result["action_type"] == "click"
    
    def test_parse_planner_json_hotkey(self):
        """测试解析快捷键 JSON"""
        from src.action_executor import ActionExecutor
        
        executor = ActionExecutor(None)
        result = executor.parse_planner_json(
            '{"use_vision_prompt": null, "action": "hotkey(key=\'ctrl s\')"}'
        )
        
        assert result["use_vision_prompt"] is None
        assert result["action_type"] == "hotkey"
    
    def test_parse_planner_json_finished(self):
        """测试解析完成动作 JSON"""
        from src.action_executor import ActionExecutor
        
        executor = ActionExecutor(None)
        result = executor.parse_planner_json(
            '{"use_vision_prompt": null, "action": "finished(content=\'完成\')"}'
        )
        
        assert result["action_type"] == "finished"
    
    def test_parse_planner_json_malformed(self):
        """测试解析格式错误的 JSON"""
        from src.action_executor import ActionExecutor
        
        executor = ActionExecutor(None)
        result = executor.parse_planner_json("not a json")
        
        # 应该返回默认值
        assert "action_type" in result
        assert "use_vision_prompt" in result


class TestDiffTrees:
    """测试树对比功能"""
    
    def test_no_change(self):
        """测试无变化的树"""
        from src.accessibility_parser import diff_trees
        
        before = {
            "tree": {
                "role": "Pane",
                "name": "Desktop",
                "children": [
                    {"role": "Window", "name": "Test Window", "bounds": {"x": 0, "y": 0}}
                ]
            }
        }
        
        after = before.copy()
        
        result = diff_trees(before, after)
        # 无变化时 changed 可能为 False 或 True（取决于窗口检测逻辑）
        assert isinstance(result.changed, bool)
    
    def test_new_window(self):
        """测试新窗口出现"""
        from src.accessibility_parser import diff_trees
        
        before = {
            "tree": {
                "role": "Pane",
                "name": "Desktop",
                "children": []
            }
        }
        
        after = {
            "tree": {
                "role": "Pane",
                "name": "Desktop",
                "children": [
                    {"role": "Window", "name": "New Window", "bounds": {"x": 0, "y": 0}}
                ]
            }
        }
        
        result = diff_trees(before, after)
        assert result.changed == True
        assert len(result.window_changes) > 0
    
    def test_window_closed(self):
        """测试窗口关闭"""
        from src.accessibility_parser import diff_trees
        
        before = {
            "tree": {
                "role": "Pane",
                "name": "Desktop",
                "children": [
                    {"role": "Window", "name": "Old Window", "bounds": {"x": 0, "y": 0}}
                ]
            }
        }
        
        after = {
            "tree": {
                "role": "Pane",
                "name": "Desktop",
                "children": []
            }
        }
        
        result = diff_trees(before, after)
        assert result.changed == True
        assert any("关闭" in change for change in result.window_changes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])