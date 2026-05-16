"""
端到端集成测试 - 场景测试
==========================

测试完整的任务执行流程，覆盖 Planner → Executor → Observer 的全链路。
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.desktoptools import DesktopClient
from src.agent_loop import DeskAgent, ExecutionHistory, ExecutionPlan
from src.action_executor import ActionExecutor, KeyMapper
from src.config import Config


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """创建测试配置"""
    config = MagicMock(spec=Config)
    config.max_iterations = 10
    config.context_window_size = 5
    config.debug = False
    config.general_model = "test-model"
    config.vision_model = "test-vision-model"
    return config


@pytest.fixture
def mock_desktop_client():
    """创建模拟的 DesktopClient"""
    client = AsyncMock(spec=DesktopClient)
    
    # 模拟基本方法
    client.health_check.return_value = True
    client.screen_info.return_value = {"width": 1920, "height": 1080, "scaleFactor": 1.0}
    client.screenshot.return_value = {
        "base64": "test_base64_data",
        "width": 1024,
        "height": 768,
        "grid_info": None
    }
    client.accessibility_tree.return_value = {
        "tree": {
            "role": "Window",
            "name": "Test Window",
            "children": []
        }
    }
    client.accessibility_focused.return_value = {"element": {}}
    client.mouse_position.return_value = {"x": 500, "y": 500}
    
    return client


@pytest.fixture
def mock_planner_model():
    """创建模拟的 Planner LLM"""
    model = AsyncMock()
    
    # 模拟Planner输出序列
    responses = [
        # 第1步: 点击按钮
        {
            "use_vision_prompt": None,
            "action": "click(point='<point>500 300</point>')",
            "plan_status": {
                "steps": ["打开应用", "点击按钮", "验证结果"],
                "current": 1,
                "completed": [0]
            }
        },
        # 第2步: 输入文本
        {
            "use_vision_prompt": None,
            "action": "type(content='test input')",
            "verification": {"method": "visual", "prompt": "文本已输入"}
        },
        # 第3步: 完成任务
        {
            "use_vision_prompt": None,
            "action": "finished(content='任务完成')"
        }
    ]
    
    async def create_side_effect(**kwargs):
        response = responses.pop(0) if responses else {"action": "finished(content='Done')}"}
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(response)
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150
        return mock_response
    
    model.chat.completions.create.side_effect = create_side_effect
    return model


@pytest.fixture
def mock_vision_model():
    """创建模拟的 Vision 模型 (UI-TARS)"""
    model = AsyncMock()
    
    async def create_side_effect(**kwargs):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        # 模拟视觉定位返回坐标
        mock_response.choices[0].message.content = "找到目标元素在 <point>500 300</point>"
        return mock_response
    
    model.chat.completions.create.side_effect = create_side_effect
    return model


@pytest.fixture
async def desk_agent(mock_desktop_client, mock_planner_model, mock_vision_model, mock_config):
    """创建测试用的 DeskAgent 实例"""
    agent = DeskAgent(
        agentdesk=mock_desktop_client,
        vision_model=mock_vision_model,
        planner_model=mock_planner_model,
        calibrator_model=None,
        config=mock_config
    )
    return agent


# ============================================================================
# 场景测试
# ============================================================================

class TestBasicScenarios:
    """基础场景测试"""
    
    @pytest.mark.asyncio
    async def test_simple_click_task(self, desk_agent, mock_desktop_client):
        """测试简单的点击任务"""
        agent = await desk_agent
        
        result = await agent.run("点击屏幕中央按钮")
        
        assert result["success"] is True
        assert "完成" in result["message"] or "Done" in result["message"]
        assert result["steps"] >= 1
        
        # 验证点击被调用
        mock_desktop_client.mouse_click.assert_called()
    
    @pytest.mark.asyncio
    async def test_type_text_task(self, desk_agent, mock_desktop_client):
        """测试输入文本任务"""
        agent = await desk_agent
        
        result = await agent.run("在搜索框输入文本")
        
        assert result["success"] is True
        # 验证键盘输入被调用
        mock_desktop_client.keyboard_type.assert_called()
    
    @pytest.mark.asyncio
    async def test_hotkey_task(self, desk_agent, mock_desktop_client):
        """测试快捷键任务"""
        agent = await desk_agent
        
        result = await agent.run("复制选中的内容")
        
        assert result["success"] is True
        # 验证快捷键被调用
        mock_desktop_client.keyboard_hotkey.assert_called()


class TestVisionGroundingScenarios:
    """视觉定位场景测试"""
    
    @pytest.mark.asyncio
    async def test_vision_grounding_success(self, mock_desktop_client, mock_config):
        """测试视觉定位成功场景"""
        # 配置Planner返回需要视觉定位
        planner_model = AsyncMock()
        
        responses = [
            {"use_vision_prompt": "找到搜索框", "action": "wait()"},
            {"use_vision_prompt": None, "action": "click(point='<point>500 300</point>')"},
            {"use_vision_prompt": None, "action": "finished(content='完成')"}
        ]
        
        async def create_side_effect(**kwargs):
            response = responses.pop(0)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(response)
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            return mock_response
        
        planner_model.chat.completions.create.side_effect = create_side_effect
        
        # 配置视觉模型返回坐标
        vision_model = AsyncMock()
        
        async def vision_create(**kwargs):
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "搜索框在 <point x1='500' y1='300'></point>"
            return mock_response
        
        vision_model.chat.completions.create.side_effect = vision_create
        
        agent = DeskAgent(
            agentdesk=mock_desktop_client,
            vision_model=vision_model,
            planner_model=planner_model,
            calibrator_model=None,
            config=mock_config
        )
        
        result = await agent.run("点击搜索框")
        
        assert result["success"] is True
        # 验证视觉定位被调用
        vision_model.chat.completions.create.assert_called()
        # 验证点击被调用
        mock_desktop_client.mouse_click.assert_called()
    
    @pytest.mark.asyncio
    async def test_vision_grounding_failure_recovery(self, mock_desktop_client, mock_config):
        """测试视觉定位失败后的恢复策略"""
        planner_model = AsyncMock()
        
        responses = [
            {"use_vision_prompt": "找到不存在的元素", "action": "wait()"},
            {"use_vision_prompt": None, "action": "scroll(direction='down')"},
            {"use_vision_prompt": "找到不存在的元素", "action": "wait()"},
            {"use_vision_prompt": None, "action": "finished(content='无法找到元素')"}
        ]
        
        response_iter = iter(responses)
        
        async def create_side_effect(**kwargs):
            response = next(response_iter)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(response)
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            return mock_response
        
        planner_model.chat.completions.create.side_effect = create_side_effect
        
        # 视觉模型返回None（模拟失败）
        vision_model = AsyncMock()
        vision_model.chat.completions.create.side_effect = Exception("Vision failed")
        
        agent = DeskAgent(
            agentdesk=mock_desktop_client,
            vision_model=vision_model,
            planner_model=planner_model,
            calibrator_model=None,
            config=mock_config
        )
        
        result = await agent.run("寻找不存在的元素")
        
        # 任务应该完成，即使视觉定位失败
        assert result["success"] is True
        # 验证视觉定位被尝试
        assert vision_model.chat.completions.create.call_count >= 1


class TestScrollScenarios:
    """滚动操作场景测试"""
    
    @pytest.mark.asyncio
    async def test_scroll_with_coordinates(self, mock_desktop_client, mock_planner_model, mock_config):
        """测试带坐标的滚动（先移动再滚动）"""
        # 修改Planner返回scroll动作
        responses = [
            {"use_vision_prompt": None, "action": "scroll(point='<point>500 400</point>', direction='down')"},
            {"use_vision_prompt": None, "action": "finished(content='完成')"}
        ]
        
        response_iter = iter(responses)
        
        async def create_side_effect(**kwargs):
            response = next(response_iter)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(response)
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            return mock_response
        
        mock_planner_model.chat.completions.create.side_effect = create_side_effect
        
        agent = DeskAgent(
            agentdesk=mock_desktop_client,
            vision_model=AsyncMock(),
            planner_model=mock_planner_model,
            calibrator_model=None,
            config=mock_config
        )
        
        result = await agent.run("在列表区域向下滚动")
        
        assert result["success"] is True
        # 验证先移动鼠标再滚动
        mock_desktop_client.mouse_move.assert_called()
        mock_desktop_client.mouse_scroll.assert_called()
    
    @pytest.mark.asyncio
    async def test_scroll_without_coordinates(self, mock_desktop_client, mock_planner_model, mock_config):
        """测试不带坐标的滚动（直接在当前位置滚动）"""
        responses = [
            {"use_vision_prompt": None, "action": "scroll(direction='up')"},
            {"use_vision_prompt": None, "action": "finished(content='完成')"}
        ]
        
        response_iter = iter(responses)
        
        async def create_side_effect(**kwargs):
            response = next(response_iter)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(response)
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            return mock_response
        
        mock_planner_model.chat.completions.create.side_effect = create_side_effect
        
        agent = DeskAgent(
            agentdesk=mock_desktop_client,
            vision_model=AsyncMock(),
            planner_model=mock_planner_model,
            calibrator_model=None,
            config=mock_config
        )
        
        result = await agent.run("向上滚动页面")
        
        assert result["success"] is True
        # 验证直接滚动，没有移动鼠标
        mock_desktop_client.mouse_move.assert_not_called()
        mock_desktop_client.mouse_scroll.assert_called()


class TestErrorRecoveryScenarios:
    """错误恢复场景测试"""
    
    @pytest.mark.asyncio
    async def test_planner_json_parse_failure(self, mock_desktop_client, mock_config):
        """测试Planner JSON解析失败后的恢复"""
        planner_model = AsyncMock()
        
        responses = [
            "invalid json",  # 第1步: 无效JSON
            '{"action": "wait()"}',  # 第2步: 有效但简单
            '{"use_vision_prompt": null, "action": "finished(content=\\"完成\\")"}'  # 第3步: 完成
        ]
        
        response_iter = iter(responses)
        
        async def create_side_effect(**kwargs):
            content = next(response_iter)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = content
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            return mock_response
        
        planner_model.chat.completions.create.side_effect = create_side_effect
        
        agent = DeskAgent(
            agentdesk=mock_desktop_client,
            vision_model=AsyncMock(),
            planner_model=planner_model,
            calibrator_model=None,
            config=mock_config
        )
        
        result = await agent.run("测试错误恢复")
        
        # 任务应该完成，即使第1步解析失败
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_action_execution_failure(self, mock_desktop_client, mock_config):
        """测试动作执行失败后的恢复"""
        # 模拟点击失败
        mock_desktop_client.mouse_click.side_effect = [
            Exception("Click failed"),  # 第1次失败
            None  # 第2次成功
        ]
        
        planner_model = AsyncMock()
        
        responses = [
            {"use_vision_prompt": None, "action": "click(point='<point>500 300</point>')"},
            {"use_vision_prompt": None, "action": "click(point='<point>500 300</point>')"},
            {"use_vision_prompt": None, "action": "finished(content='完成')"}
        ]
        
        response_iter = iter(responses)
        
        async def create_side_effect(**kwargs):
            response = next(response_iter)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(response)
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            return mock_response
        
        planner_model.chat.completions.create.side_effect = create_side_effect
        
        agent = DeskAgent(
            agentdesk=mock_desktop_client,
            vision_model=AsyncMock(),
            planner_model=planner_model,
            calibrator_model=None,
            config=mock_config
        )
        
        result = await agent.run("测试执行失败恢复")
        
        # 任务应该完成，即使第1次点击失败
        assert result["success"] is True


class TestMultiStepScenarios:
    """多步骤任务场景测试"""
    
    @pytest.mark.asyncio
    async def test_multi_step_task(self, mock_desktop_client, mock_config):
        """测试复杂的多步骤任务"""
        planner_model = AsyncMock()
        
        responses = [
            {
                "use_vision_prompt": None,
                "action": "click(point='<point>100 100</point>')",
                "plan_status": {
                    "steps": ["打开菜单", "选择选项", "确认操作", "验证结果"],
                    "current": 1,
                    "completed": [0]
                },
                "verification": {"method": "visual", "prompt": "菜单已打开"}
            },
            {
                "use_vision_prompt": None,
                "action": "click(point='<point>200 200</point>')",
                "plan_status": {
                    "steps": ["打开菜单", "选择选项", "确认操作", "验证结果"],
                    "current": 2,
                    "completed": [0, 1]
                },
                "verification": {"method": "visual", "prompt": "选项已选中"}
            },
            {
                "use_vision_prompt": None,
                "action": "hotkey(key='enter')",
                "plan_status": {
                    "steps": ["打开菜单", "选择选项", "确认操作", "验证结果"],
                    "current": 3,
                    "completed": [0, 1, 2]
                },
                "verification": {"method": "visual", "prompt": "操作已确认"}
            },
            {
                "use_vision_prompt": None,
                "action": "finished(content='多步骤任务完成')",
                "plan_status": {
                    "steps": ["打开菜单", "选择选项", "确认操作", "验证结果"],
                    "current": 4,
                    "completed": [0, 1, 2, 3]
                }
            }
        ]
        
        response_iter = iter(responses)
        
        async def create_side_effect(**kwargs):
            response = next(response_iter)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = json.dumps(response)
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            return mock_response
        
        planner_model.chat.completions.create.side_effect = create_side_effect
        
        agent = DeskAgent(
            agentdesk=mock_desktop_client,
            vision_model=AsyncMock(),
            planner_model=planner_model,
            calibrator_model=None,
            config=mock_config
        )
        
        result = await agent.run("执行多步骤操作")
        
        assert result["success"] is True
        assert result["steps"] == 4  # 4个步骤
        # 验证多个动作被调用
        assert mock_desktop_client.mouse_click.call_count == 2
        mock_desktop_client.keyboard_hotkey.assert_called_once()


# ============================================================================
# 工具类测试
# ============================================================================

class TestKeyMapper:
    """按键映射器测试"""
    
    def test_windows_mapping(self):
        """测试Windows按键映射"""
        mapper = KeyMapper("Windows")
        
        assert mapper.normalize("ctrl") == "ControlLeft"
        assert mapper.normalize("win") == "LeftWin"
        assert mapper.normalize("c") == "C"
        assert mapper.normalize("f1") == "F1"
    
    def test_macos_mapping(self):
        """测试macOS按键映射"""
        mapper = KeyMapper("macOS")
        
        assert mapper.normalize("ctrl") == "ControlLeft"
        assert mapper.normalize("cmd") == "LeftCmd"
        assert mapper.normalize("option") == "AltLeft"
    
    def test_linux_mapping(self):
        """测试Linux按键映射"""
        mapper = KeyMapper("Linux")
        
        assert mapper.normalize("ctrl") == "ControlLeft"
        assert mapper.normalize("super") == "MetaLeft"
    
    def test_batch_normalize(self):
        """测试批量按键映射"""
        mapper = KeyMapper("Windows")
        
        keys = ["ctrl", "c"]
        normalized = mapper.normalize_keys(keys)
        
        assert normalized == ["ControlLeft", "C"]


class TestExecutionPlan:
    """执行计划管理测试"""
    
    def test_plan_creation(self):
        """测试计划创建"""
        plan = ExecutionPlan(["步骤1", "步骤2", "步骤3"])
        
        assert len(plan.steps) == 3
        assert plan.current == 0
        assert not plan.is_complete()
    
    def test_plan_progression(self):
        """测试计划推进"""
        plan = ExecutionPlan(["步骤1", "步骤2", "步骤3"])
        
        step1 = plan.next_step()
        assert step1 == "步骤1"
        assert plan.current == 1
        assert 0 in plan.completed
        
        step2 = plan.next_step()
        assert step2 == "步骤2"
        assert plan.current == 2
        
        step3 = plan.next_step()
        assert step3 == "步骤3"
        assert plan.is_complete()
    
    def test_plan_update(self):
        """测试计划更新"""
        plan = ExecutionPlan(["步骤1", "步骤2"])
        
        plan.next_step()  # 完成步骤1
        
        # 更新计划
        plan.update(["新步骤1", "新步骤2", "新步骤3"])
        
        assert len(plan.steps) == 3
        assert plan.current == 1  # 保持当前位置
        assert plan.completed == []  # 已完成的被清除（因为步骤变了）


class TestExecutionHistory:
    """执行历史管理测试"""
    
    def test_history_add(self):
        """测试添加历史记录"""
        history = ExecutionHistory(max_entries=5)
        
        history.add("步骤1完成")
        history.add("步骤2完成")
        
        assert len(history.entries) == 2
        assert "步骤1完成" in history.format()
    
    def test_history_sliding_window(self):
        """测试历史滑动窗口"""
        history = ExecutionHistory(max_entries=3)
        
        history.add("步骤1")
        history.add("步骤2")
        history.add("步骤3")
        history.add("步骤4")  # 应该移除步骤1
        
        assert len(history.entries) == 3
        assert "步骤1" not in history.format()
        assert "步骤4" in history.format()
    
    def test_history_summary(self):
        """测试历史摘要"""
        history = ExecutionHistory()
        
        for i in range(10):
            history.add(f"步骤{i}")
        
        summary = history.summary(last_n=3)
        
        assert "步骤7" in summary
        assert "步骤8" in summary
        assert "步骤9" in summary
        assert "步骤0" not in summary


# ============================================================================
# 主函数
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])