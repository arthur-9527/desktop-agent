"""工具函数模块"""

from openai import AsyncOpenAI
from .agentdesk_client import AgentDeskClient
from .config import Config


async def check_services(client: AgentDeskClient, model: AsyncOpenAI, config: Config) -> bool:
    """检查服务状态

    Args:
        client: AgentDesk 客户端
        model: OpenAI 兼容的模型客户端
        config: 配置对象

    Returns:
        True 如果所有服务正常，False 否则
    """
    print("=" * 50)
    print("检查服务状态...")

    # 检查 AgentDesk
    print(f"\n1. AgentDesk ({config.agentdesk_host}:{config.agentdesk_port})")
    if await client.health_check():
        print("   ✓ AgentDesk 连接正常")
        try:
            screen = await client.screen_info()
            print(f"   屏幕: {screen.get('width')}x{screen.get('height')} (scale: {screen.get('scaleFactor')})")
        except Exception:
            pass  # 屏幕信息获取失败不影响
    else:
        print("   ✗ AgentDesk 连接失败")
        return False

    # 检查 UI-TARS 模型
    print(f"\n2. UI-TARS 模型 ({config.vision_base_url})")
    try:
        models = await model.models.list()
        model_names = [m.id for m in models.data]
        print(f"   ✓ 模型服务正常，可用模型: {model_names}")
        if config.vision_model not in model_names:
            print(f"   ! 警告: 配置的模型 '{config.vision_model}' 不在可用模型列表中")
    except Exception as e:
        print(f"   ✗ 模型服务连接失败: {e}")
        return False

    return True